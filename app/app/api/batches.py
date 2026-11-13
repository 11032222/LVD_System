"""[AI-MOD 2026-11-12] 批次接口：查询、批次分析统计、控制台提交。"""
from __future__ import annotations

import hashlib
import math
import random
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.common import (
    ALGO_KEYS,
    CRITERIA_LABELS,
    FAILURE_TYPES,
    failure_label,
    fmt_dt,
    page_args,
    paged,
    run_brief,
)
from app.db import jdumps, jloads, query_all, query_one, transaction

router = APIRouter(prefix="/api", tags=["batches"])

MODE_STRATEGY = {"na": 0, "sa": 2, "ma": 3}


def _batch_brief(row: dict) -> dict:
    tasks = int(row.get("tasks") or 0)
    failed = int(row.get("failed") or 0)
    return {
        "id": row["id"],
        "batch_key": row["batch_key"],
        "algo": row["algo"],
        "algo_key": ALGO_KEYS.get(row["algo"], ""),
        "swarm_size": row["swarm_size"],
        "modes": jloads(row.get("modes"), []),
        "seed_from": row["seed_from"],
        "seed_to": row["seed_to"],
        "status": row["status"],
        "scheduler": row.get("scheduler"),
        "started_at": fmt_dt(row.get("started_at")),
        "finished_at": fmt_dt(row.get("finished_at")),
        "note": row.get("note"),
        "tasks": tasks,
        "failed": failed,
        "failure_rate": round(failed / tasks, 4) if tasks else 0.0,
        "config_snapshot": jloads(row.get("config_snapshot")),
    }


@router.get("/batches")
def list_batches(
    algo: str | None = Query(default=None),
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    page: int = Query(default=1),
    page_size: int = Query(default=20),
) -> dict:
    page, page_size = page_args(page, page_size)
    where: list[str] = []
    args: list[Any] = []
    if algo:
        where.append("b.algo = %s")
        args.append(algo)
    if status:
        where.append("b.status = %s")
        args.append(status)
    if q:
        where.append("(b.batch_key LIKE %s OR b.note LIKE %s OR CAST(b.id AS CHAR) = %s)")
        args += ["%" + q + "%", "%" + q + "%", q]

    cond = ("WHERE " + " AND ".join(where)) if where else ""
    total_row = query_one(f"SELECT COUNT(*) AS n FROM batch b {cond}", args)
    total = int(total_row["n"]) if total_row else 0

    rows = query_all(
        f"""
        SELECT b.*, COUNT(r.id) AS tasks, COALESCE(SUM(r.failed), 0) AS failed
        FROM batch b
        LEFT JOIN task_run r ON r.batch_id = b.id
        {cond}
        GROUP BY b.id
        ORDER BY b.started_at DESC, b.id DESC
        LIMIT %s OFFSET %s
        """,
        args + [page_size, (page - 1) * page_size],
    )
    items = []
    for r in rows:
        b = _batch_brief(r)
        names = query_all(
            "SELECT DISTINCT algo, swarm_size FROM task_run WHERE batch_id = %s", [r["id"]]
        )
        b["groups"] = [{"algo": x["algo"], "swarm_size": x["swarm_size"]} for x in names]
        items.append(b)
    return paged(items, total, page, page_size)


@router.get("/batches/{batch_id}")
def get_batch(batch_id: int) -> dict:
    row = query_one(
        """
        SELECT b.*, COUNT(r.id) AS tasks, COALESCE(SUM(r.failed), 0) AS failed
        FROM batch b LEFT JOIN task_run r ON r.batch_id = b.id
        WHERE b.id = %s GROUP BY b.id
        """,
        [batch_id],
    )
    if not row:
        raise HTTPException(404, "批次不存在")

    runs = query_all(
        """
        SELECT r.*, s.name AS scenario_name FROM task_run r
        LEFT JOIN scenario s ON s.id = r.scenario_id
        WHERE r.batch_id = %s ORDER BY r.mode, r.seed, r.id
        """,
        [batch_id],
    )
    briefs = [run_brief(r) for r in runs]

    # 判据 / 场景快照：同批次内一般是同一套，去重后全部展示，便于核对参数
    crit_ids = sorted({r["criteria_id"] for r in runs})
    scen_ids = sorted({r["scenario_id"] for r in runs})
    criteria = []
    if crit_ids:
        placeholders = ",".join(["%s"] * len(crit_ids))
        for c in query_all(f"SELECT * FROM criteria_profile WHERE id IN ({placeholders})", crit_ids):
            criteria.append(_criteria_view(c, count=sum(1 for r in runs if r["criteria_id"] == c["id"])))
    scenarios = []
    scenario_info = []
    if scen_ids:
        placeholders = ",".join(["%s"] * len(scen_ids))
        for s in query_all(
            f"""SELECT id, algo, swarm_size, slug, name, dim, source_type, bounds,
                       JSON_LENGTH(obstacles) AS obstacle_count, created_at
                FROM scenario WHERE id IN ({placeholders})""",
            scen_ids,
        ):
            scenarios.append(
                {
                    "id": s["id"],
                    "name": s["name"],
                    "slug": s["slug"],
                    "algo": s["algo"],
                    "swarm_size": s["swarm_size"],
                    "dim": s["dim"],
                    "source_type": s["source_type"],
                    "bounds": jloads(s.get("bounds"), {}),
                    "obstacle_count": int(s.get("obstacle_count") or 0),
                    "created_at": fmt_dt(s.get("created_at")),
                    "used_by": sum(1 for r in runs if r["scenario_id"] == s["id"]),
                }
            )
            # 场景几何给批次页的小地图预览用（数据量很小）
            detail = query_one("SELECT obstacles, goal, init_positions FROM scenario WHERE id = %s", [s["id"]])
            scenario_info.append(
                {
                    "id": s["id"],
                    "dim": s["dim"],
                    "bounds": jloads(s.get("bounds"), {}),
                    "obstacles": jloads(detail.get("obstacles"), []),
                    "targets": (jloads(detail.get("goal"), {}) or {}).get("targets", []),
                    "init_positions": jloads(detail.get("init_positions"), []),
                }
            )

    tasks = int(row.get("tasks") or 0)
    failed = int(row.get("failed") or 0)
    total_wall = sum(float(r.get("wall_s") or 0) for r in runs)

    # 失败类型分布（含成功任务，便于对比 NA/SA/MA）
    ft_map: dict[str, int] = {}
    for r in runs:
        key = "none" if not r["failed"] else (r.get("failure_type") or "custom")
        ft_map[key] = ft_map.get(key, 0) + 1
    failure_dist = [
        {
            "type": k,
            "label": failure_label(k) if k != "none" else "未复现失败",
            "count": v,
            "color": FAILURE_TYPES.get(k, {}).get("color", "#9aa4b2"),
        }
        for k, v in sorted(ft_map.items(), key=lambda kv: -kv[1])
    ]

    mode_dist = query_all(
        """
        SELECT mode, COUNT(*) AS total, SUM(failed) AS failed, AVG(COALESCE(iterations,0)) AS avg_iter,
               AVG(wall_s) AS avg_wall
        FROM task_run WHERE batch_id = %s GROUP BY mode ORDER BY mode
        """,
        [batch_id],
    )
    for m in mode_dist:
        m["total"] = int(m["total"])
        m["failed"] = int(m["failed"] or 0)
        m["failure_rate"] = round(m["failed"] / m["total"], 4) if m["total"] else 0.0
        m["avg_iter"] = round(float(m.get("avg_iter") or 0), 1)
        m["avg_wall"] = round(float(m.get("avg_wall") or 0), 1)

    crit_dist = [
        {
            "criterion": int(k),
            "label": CRITERIA_LABELS.get(int(k), "判据 %s" % k),
            "count": v,
        }
        for k, v in sorted(
            {
                int(r["failure_criterion"]): sum(
                    1 for x in runs if x["failure_criterion"] == r["failure_criterion"]
                )
                for r in runs
                if r["failure_criterion"]
            }.items()
        )
    ]

    iterations = [int(r["iterations"]) for r in runs if r.get("iterations") is not None]
    wall_list = [float(r["wall_s"]) for r in runs if r.get("wall_s") is not None]

    return {
        "batch": _batch_brief(row),
        "tasks": briefs,
        "criteria": criteria,
        "scenarios": scenarios,
        "scenario_geometry": scenario_info,
        "stats": {
            "tasks": tasks,
            "failed": failed,
            "failure_rate": round(failed / tasks, 4) if tasks else 0.0,
            "total_wall_s": round(total_wall, 1),
            "avg_wall_s": round(total_wall / tasks, 1) if tasks else 0.0,
            "avg_iterations": round(sum(iterations) / len(iterations), 1) if iterations else None,
            "max_iterations": max(iterations) if iterations else None,
            "modes": mode_dist,
            "failure_dist": failure_dist,
            "criterion_dist": crit_dist,
            "iteration_hist": _histogram(iterations, bins=8),
            "wall_hist": _histogram(wall_list, bins=8),
            "seeds": sorted({int(r["seed"]) for r in runs}),
        },
    }


def _criteria_view(row: dict, count: int | None = None) -> dict:
    view = {
        "id": row["id"],
        "name": row["name"],
        "profile_kind": row["profile_kind"],
        "description": row.get("description"),
        "obstacle_dist_thr": row.get("obstacle_dist_thr"),
        "drone_dist_thr": row.get("drone_dist_thr"),
        "timeout_multiplier": row.get("timeout_multiplier"),
        "enable_obstacle": int(row.get("enable_obstacle") or 0),
        "enable_collision": int(row.get("enable_collision") or 0),
        "enable_timeout": int(row.get("enable_timeout") or 0),
        "candidate_count": row.get("candidate_count"),
        "reach_radius": row.get("reach_radius"),
        "sample_sigma": row.get("sample_sigma"),
        "max_iterations": row.get("max_iterations"),
        "max_sim_time": row.get("max_sim_time"),
        "extra": jloads(row.get("extra")),
    }
    if count is not None:
        view["used_by"] = count
    return view


def _histogram(values: list[float], bins: int = 8) -> list[dict]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if math.isclose(lo, hi):
        return [{"from": round(lo, 2), "to": round(hi, 2), "count": len(values)}]
    width = (hi - lo) / bins
    counts = [0] * bins
    for v in values:
        idx = min(bins - 1, int((v - lo) / width))
        counts[idx] += 1
    return [
        {"from": round(lo + i * width, 2), "to": round(lo + (i + 1) * width, 2), "count": counts[i]}
        for i in range(bins)
    ]


# ---------------------------------------------------------------------------
# 控制台提交
# ---------------------------------------------------------------------------
class CriteriaIn(BaseModel):
    enable_timeout: bool = True
    timeout_multiplier: float = Field(default=2.0, gt=0)
    enable_obstacle: bool = True
    enable_collision: bool = True
    obstacle_dist_thr: float | None = None
    drone_dist_thr: float | None = None
    candidate_count: int = Field(default=20, ge=1, le=1000)
    max_iterations: int | None = None
    max_sim_time: float | None = None
    sample_sigma: float | None = None
    reach_radius: float | None = None
    extra: dict | None = None


class SeedsIn(BaseModel):
    mode: str = "range"          # range | random
    seed_from: int = 1
    seed_to: int = 10
    count: int | None = None


class BatchIn(BaseModel):
    algo: str
    swarm_size: int = Field(ge=1, le=64)
    modes: list[str] = ["sa"]
    scenario_ids: list[int] = []
    criteria: CriteriaIn = CriteriaIn()
    seeds: SeedsIn = SeedsIn()
    workers: int = Field(default=8, ge=1, le=64)
    task_timeout: int | None = None
    trace: bool = True
    note: str | None = None


def _resolve_seeds(seeds: SeedsIn) -> tuple[list[int], str]:
    if seeds.seed_from > seeds.seed_to:
        raise HTTPException(400, "种子区间起点不能大于终点")
    if seeds.mode == "random":
        n = seeds.count or 0
        if n <= 0:
            raise HTTPException(400, "随机种子数量必须大于 0")
        span = seeds.seed_to - seeds.seed_from + 1
        if n > span:
            raise HTTPException(400, "随机数量超过区间容量")
        picked = sorted(random.sample(range(seeds.seed_from, seeds.seed_to + 1), n))
        return picked, "已从 [%d, %d] 随机抽取 %d 个种子：%s" % (
            seeds.seed_from, seeds.seed_to, n, ",".join(map(str, picked))
        )
    return list(range(seeds.seed_from, seeds.seed_to + 1)), "%d 个连续种子" % (
        seeds.seed_to - seeds.seed_from + 1
    )


@router.post("/batches")
def create_batch(payload: BatchIn) -> dict:
    if payload.algo not in ALGO_KEYS:
        raise HTTPException(400, f"未知算法：{payload.algo}")
    modes = [m for m in payload.modes if m in MODE_STRATEGY]
    if not modes:
        raise HTTPException(400, "至少选择一种测试模式")

    seeds, seed_note = _resolve_seeds(payload.seeds)
    scen_rows: list[dict] = []
    if payload.scenario_ids:
        placeholders = ",".join(["%s"] * len(payload.scenario_ids))
        scen_rows = query_all(
            f"SELECT id, name, algo, swarm_size FROM scenario WHERE id IN ({placeholders})",
            payload.scenario_ids,
        )
        if len(scen_rows) != len(set(payload.scenario_ids)):
            raise HTTPException(400, "存在无效的场景 ID")
        wrong = [s["name"] for s in scen_rows if s["algo"] != payload.algo]
        if wrong:
            raise HTTPException(400, "场景与算法不匹配：%s" % "、".join(wrong))
    else:
        scen_rows = query_all(
            "SELECT id, name, algo, swarm_size FROM scenario WHERE algo = %s AND dim = %s "
            "ORDER BY source_type = 'builtin' DESC, id LIMIT 1",
            [payload.algo, 3 if payload.algo == "Howard" else 2],
        )
    if not scen_rows:
        raise HTTPException(400, "没有可用场景，请先在场景设置中创建")

    crit = payload.criteria
    crit_params = {
        "algo": payload.algo,
        "obstacle_dist_thr": crit.obstacle_dist_thr if crit.enable_obstacle else None,
        "drone_dist_thr": crit.drone_dist_thr if crit.enable_collision else None,
        "timeout_multiplier": crit.timeout_multiplier,
        "enable_obstacle": int(crit.enable_obstacle),
        "enable_collision": int(crit.enable_collision),
        "enable_timeout": int(crit.enable_timeout),
        "candidate_count": crit.candidate_count,
        "max_iterations": crit.max_iterations,
        "max_sim_time": crit.max_sim_time,
        "sample_sigma": crit.sample_sigma,
        "reach_radius": crit.reach_radius,
        "extra": crit.extra or {},
    }
    crit_hash = hashlib.sha256(jdumps(crit_params).encode("utf-8")).hexdigest()
    crit_name = "web-%s-%s" % (payload.algo[:4].lower(), crit_hash[:8])

    planned = len(seeds) * len(modes)
    snapshot = {
        "source": "web-console",
        "schema": "1.0.0",
        "algo": payload.algo,
        "swarm_size": payload.swarm_size,
        "modes": modes,
        "scenario_ids": [s["id"] for s in scen_rows],
        "scenarios": scen_rows,
        "criteria": crit_params,
        "criteria_hash": crit_hash,
        "seed_mode": payload.seeds.mode,
        "seed_note": seed_note,
        "seeds": seeds,
        "workers": payload.workers,
        "task_timeout": payload.task_timeout,
        "trace": payload.trace,
        "planned_tasks": planned,
    }
    batch_key = hashlib.sha256(jdumps(snapshot).encode("utf-8")).hexdigest()
    existing = query_one("SELECT id FROM batch WHERE batch_key = %s", [batch_key])
    if existing:
        return {
            "batch_id": existing["id"],
            "created": False,
            "planned_tasks": planned,
            "seeds": seeds,
            "message": "相同配置的批次已存在，直接复用",
            "command": _command(payload, seeds, modes),
        }

    algo_key = ALGO_KEYS[payload.algo]
    with transaction() as cur:
        cur.execute(
            """
            INSERT INTO criteria_profile
              (name, params_hash, profile_kind, is_default, description, obstacle_dist_thr,
               drone_dist_thr, timeout_multiplier, enable_obstacle, enable_collision,
               enable_timeout, candidate_count, reach_radius, sample_sigma, max_iterations,
               max_sim_time, extra)
            VALUES (%s,%s,'custom',0,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE name = name
            """,
            [
                crit_name, crit_hash, "控制台提交（%s / %s）" % (payload.algo, ",".join(modes)),
                crit.obstacle_dist_thr if crit.enable_obstacle else None,
                crit.drone_dist_thr if crit.enable_collision else None,
                crit.timeout_multiplier, int(crit.enable_obstacle), int(crit.enable_collision),
                int(crit.enable_timeout), crit.candidate_count, crit.reach_radius,
                crit.sample_sigma, crit.max_iterations, crit.max_sim_time, jdumps(crit.extra or {}),
            ],
        )
        cur.execute(
            """
            INSERT INTO batch
              (batch_key, algo, swarm_size, modes, seed_from, seed_to, scheduler, host,
               status, config_snapshot, note)
            VALUES (%s,%s,%s,%s,%s,%s,'sched.py',%s,'running',%s,%s)
            """,
            [
                batch_key, payload.algo, payload.swarm_size, jdumps(modes),
                min(seeds), max(seeds), None, jdumps(snapshot),
                payload.note or "控制台提交，待调度器执行",
            ],
        )
        batch_id = cur.lastrowid

    return {
        "batch_id": batch_id,
        "created": True,
        "algo_key": algo_key,
        "planned_tasks": planned,
        "seeds": seeds,
        "criteria_id": query_one("SELECT id FROM criteria_profile WHERE params_hash = %s",
                                 [crit_hash])["id"],
        "message": "批次已登记，调度器开始执行后会自动导入任务结果",
        "command": _command(payload, seeds, modes),
    }


def _command(payload: BatchIn, seeds: list[int], modes: list[str]) -> str:
    algo_key = ALGO_KEYS[payload.algo]
    seed_arg = "%d-%d" % (min(seeds), max(seeds)) if len(seeds) > 1 else str(seeds[0])
    strategies = ",".join(str(MODE_STRATEGY[m]) for m in sorted(modes, key=MODE_STRATEGY.get))
    return (
        "python sched.py --algo {algo} --size {size} --seeds {seeds} "
        "--strategies {strategies} --workers {workers}"
    ).format(algo=algo_key, size=payload.swarm_size, seeds=seed_arg,
             strategies=strategies, workers=payload.workers)
