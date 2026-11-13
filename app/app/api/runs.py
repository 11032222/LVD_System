"""[AI-MOD 2026-11-12] 单任务接口：详情、分块取帧、鲁棒度序列、失败事件。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

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
from app.db import jloads, query_all, query_one

router = APIRouter(prefix="/api", tags=["runs"])


def _run_row(run_id: int) -> dict:
    row = query_one(
        """
        SELECT r.*, s.name AS scenario_name, b.batch_key
        FROM task_run r
        JOIN batch b ON b.id = r.batch_id
        LEFT JOIN scenario s ON s.id = r.scenario_id
        WHERE r.id = %s
        """,
        [run_id],
    )
    if not row:
        raise HTTPException(404, "任务不存在")
    return row


@router.get("/runs")
def list_runs(
    batch_id: int | None = Query(default=None),
    algo: str | None = Query(default=None),
    mode: str | None = Query(default=None),
    failed: int | None = Query(default=None),
    seed: int | None = Query(default=None),
    page: int = Query(default=1),
    page_size: int = Query(default=50),
) -> dict:
    page, page_size = page_args(page, page_size)
    where, args = [], []
    if batch_id:
        where.append("r.batch_id = %s")
        args.append(batch_id)
    if algo:
        where.append("r.algo = %s")
        args.append(algo)
    if mode:
        where.append("r.mode = %s")
        args.append(mode)
    if failed is not None:
        where.append("r.failed = %s")
        args.append(int(failed))
    if seed is not None:
        where.append("r.seed = %s")
        args.append(seed)
    cond = ("WHERE " + " AND ".join(where)) if where else ""

    total_row = query_one(f"SELECT COUNT(*) AS n FROM task_run r {cond}", args)
    total = int(total_row["n"]) if total_row else 0
    rows = query_all(
        f"""
        SELECT r.*, s.name AS scenario_name, b.batch_key
        FROM task_run r
        JOIN batch b ON b.id = r.batch_id
        LEFT JOIN scenario s ON s.id = r.scenario_id
        {cond}
        ORDER BY r.created_at DESC, r.id DESC
        LIMIT %s OFFSET %s
        """,
        args + [page_size, (page - 1) * page_size],
    )
    return paged([run_brief(r) for r in rows], total, page, page_size)


@router.get("/runs/{run_id}")
def get_run(run_id: int) -> dict:
    row = _run_row(run_id)
    scen = query_one("SELECT * FROM scenario WHERE id = %s", [row["scenario_id"]])
    crit = query_one("SELECT * FROM criteria_profile WHERE id = %s", [row["criteria_id"]])
    batch = query_one("SELECT * FROM batch WHERE id = %s", [row["batch_id"]])

    frame_range = query_one(
        "SELECT COUNT(*) AS n, MIN(step) AS s0, MAX(step) AS s1 FROM trace_frame WHERE task_run_id = %s",
        [run_id],
    ) or {}
    goal = jloads(scen.get("goal"), {}) if scen else {}
    events = _events(run_id)

    return {
        "run": run_brief(row),
        "result": jloads(row.get("result_json")),
        "error_message": row.get("error_message"),
        "wall_s": row.get("wall_s"),
        "criteria": {
            "id": crit["id"],
            "name": crit["name"],
            "timeout_multiplier": crit["timeout_multiplier"],
            "enable_timeout": int(crit["enable_timeout"]),
            "enable_obstacle": int(crit["enable_obstacle"]),
            "enable_collision": int(crit["enable_collision"]),
            "obstacle_dist_thr": crit["obstacle_dist_thr"],
            "drone_dist_thr": crit["drone_dist_thr"],
            "candidate_count": crit["candidate_count"],
            "max_iterations": crit["max_iterations"],
            "max_sim_time": crit["max_sim_time"],
            "reach_radius": crit["reach_radius"],
            "sample_sigma": crit["sample_sigma"],
            "extra": jloads(crit.get("extra")),
        } if crit else None,
        "batch": {
            "id": batch["id"],
            "batch_key": batch["batch_key"],
            "algo": batch["algo"],
            "swarm_size": batch["swarm_size"],
            "modes": jloads(batch.get("modes"), []),
            "started_at": fmt_dt(batch.get("started_at")),
        } if batch else None,
        "scenario": {
            "id": scen["id"],
            "name": scen["name"],
            "slug": scen["slug"],
            "dim": scen["dim"],
            "swarm_size": scen["swarm_size"],
            "source_type": scen["source_type"],
            "bounds": jloads(scen["bounds"], {}),
            "obstacles": jloads(scen["obstacles"], []),
            "targets": goal.get("targets", []) if isinstance(goal, dict) else [],
            "init_positions": jloads(scen["init_positions"], []),
            "start_pose": jloads(scen.get("start_pose")),
            "waypoints": jloads(scen.get("waypoints")),
        } if scen else None,
        "frames": {
            "count": int(frame_range.get("n") or 0),
            "step_from": frame_range.get("s0"),
            "step_to": frame_range.get("s1"),
        },
        "events": events,
        "failure": {
            "type": row.get("failure_type"),
            "label": row.get("failure_label") or failure_label(row.get("failure_type")),
            "criterion": row.get("failure_criterion"),
            "criterion_label": CRITERIA_LABELS.get(row.get("failure_criterion") or 0),
            "color": FAILURE_TYPES.get(row.get("failure_type") or "", {}).get("color", "#9aa4b2"),
        },
    }


@router.get("/runs/{run_id}/frames")
def get_frames(
    run_id: int,
    from_step: int = Query(default=0, alias="from"),
    to: int | None = Query(default=None),
    stride: int = Query(default=1, ge=1, le=50),
) -> dict:
    range_row = query_one(
        "SELECT MIN(step) AS s0, MAX(step) AS s1 FROM trace_frame WHERE task_run_id = %s", [run_id]
    ) or {}
    if range_row.get("s1") is None:
        return {"frames": [], "from": None, "to": None, "total": 0, "step": 0}
    s0 = int(range_row["s0"])
    s1 = int(range_row["s1"])
    start = max(s0, int(from_step))
    end = min(s1, int(to) if to is not None else s1)
    rows = query_all(
        """
        SELECT step, sim_time, agents FROM trace_frame
        WHERE task_run_id = %s AND step BETWEEN %s AND %s AND (step - %s) %% %s = 0
        ORDER BY step
        """,
        [run_id, start, end, start, stride],
    )
    frames = [
        {"step": r["step"], "sim_time": r["sim_time"], "agents": jloads(r["agents"], [])}
        for r in rows
    ]
    return {
        "frames": frames,
        "from": start,
        "to": end,
        "step": stride,
        "total": len(frames),
        "range": {"step_from": s0, "step_to": s1},
    }


@router.get("/runs/{run_id}/metrics")
def get_metrics(run_id: int) -> dict:
    rows = query_all(
        """
        SELECT iter, sim_time, attacker_pos, robustness, victim_agent, candidates,
               chosen_rank, extra
        FROM iteration_metric WHERE task_run_id = %s ORDER BY iter
        """,
        [run_id],
    )
    items = [
        {
            "iter": r["iter"],
            "sim_time": r["sim_time"],
            "attacker": jloads(r["attacker_pos"], []),
            "robustness": r["robustness"],
            "victim_agent": r["victim_agent"],
            "candidates": r["candidates"],
            "extra": jloads(r.get("extra")),
        }
        for r in rows
    ]
    values = [x["robustness"] for x in items]
    return {
        "items": items,
        "count": len(items),
        "min": min(values) if values else None,
        "max": max(values) if values else None,
        "avg": round(sum(values) / len(values), 4) if values else None,
    }


@router.get("/runs/{run_id}/events")
def get_events(run_id: int) -> dict:
    return {"items": _events(run_id)}


def _events(run_id: int) -> list[dict]:
    """失败事件 + 位置补齐：库里 position 可为空，用 nearest_agent 在该帧的位置代替。"""
    rows = query_all("SELECT * FROM failure_event WHERE task_run_id = %s ORDER BY step", [run_id])
    frames: dict[int, list[dict]] = {}
    for r in rows:
        if r.get("position") is None and r.get("step") is not None:
            f = query_one(
                "SELECT agents FROM trace_frame WHERE task_run_id = %s AND step = %s",
                [run_id, r["step"]],
            )
            if f:
                frames[r["step"]] = jloads(f["agents"], [])

    out = []
    for r in rows:
        detail = jloads(r.get("detail"), {}) or {}
        pos = jloads(r.get("position"))
        nearest = detail.get("nearest_agent")
        if pos is None and r["step"] in frames:
            for a in frames[r["step"]]:
                if nearest is not None and a.get("id") == nearest:
                    pos = a.get("p")
                    break
            if pos is None and frames[r["step"]]:
                pos = frames[r["step"]][0].get("p")
        out.append(
            {
                "id": r["id"],
                "criterion": r["criterion"],
                "criterion_label": CRITERIA_LABELS.get(r["criterion"], "判据 %s" % r["criterion"]),
                "step": r["step"],
                "sim_time": r["sim_time"],
                "position": pos,
                "nearest_agent": nearest,
                "min_obst_dist": r.get("min_obst_dist"),
                "min_drone_dist": r.get("min_drone_dist"),
                "type": detail.get("type") or ("criterion_%s" % r["criterion"]),
                "label": failure_label(detail.get("type")),
                "error": detail.get("error"),
                "collision_pairs": detail.get("collision_pairs", []),
                "detail": detail,
            }
        )
    return out
