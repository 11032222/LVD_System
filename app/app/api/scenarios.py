"""[AI-MOD 2026-11-12] 场景接口：内置场景查询 + 自定义场景落库。

自定义场景只接受结构化几何（几何 JSON），不接收上传文件；
scene_hash 与 importer 使用同一套归一化规则，保证同一张地图不会重复入库。
"""
from __future__ import annotations

import hashlib
import json

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.common import ALGO_KEYS, fmt_dt
from app.db import jdumps, jloads, query_all, query_one, transaction

router = APIRouter(prefix="/api", tags=["scenarios"])


def _sha256(obj) -> str:
    return hashlib.sha256(jdumps(obj).encode("utf-8")).hexdigest()


def _scene_geometry(dim: int, bounds: dict, obstacles: list, targets: list) -> dict:
    return {"dim": dim, "bounds": bounds, "obstacles": obstacles, "targets": targets}


class ScenarioIn(BaseModel):
    algo: str
    swarm_size: int = Field(ge=1, le=64)
    name: str | None = None
    dim: int = Field(default=2, ge=2, le=3)
    bounds: dict
    obstacles: list = []
    start_pose: list | None = None
    targets: list = []
    init_positions: list | None = None


def _to_floats(seq, n: int, what: str) -> list[float]:
    if not isinstance(seq, (list, tuple)) or len(seq) != n:
        raise HTTPException(400, f"{what} 需要 {n} 个数值")
    out = []
    for v in seq:
        if not isinstance(v, (int, float)):
            raise HTTPException(400, f"{what} 含非数值元素")
        out.append(float(v))
    return out


def _validate(payload: ScenarioIn) -> tuple[dict, list, list]:
    if payload.algo not in ALGO_KEYS:
        raise HTTPException(400, f"未知算法：{payload.algo}")
    dim = 2 if payload.algo != "Howard" else 3
    if payload.dim != dim:
        raise HTTPException(400, f"{payload.algo} 只支持 {dim} 维场景")

    axes = ["x", "y"] if dim == 2 else ["x", "y", "z"]
    bounds: dict[str, list[float]] = {}
    for ax in axes:
        raw = (payload.bounds or {}).get(ax)
        lo, hi = _to_floats(raw, 2, f"bounds.{ax}")
        if not lo < hi:
            raise HTTPException(400, f"bounds.{ax} 的 min 必须小于 max")
        if hi - lo < 1:
            raise HTTPException(400, f"bounds.{ax} 跨度至少 1")
        bounds[ax] = [lo, hi]

    def in_bounds(p: list[float], eps: float = 1e-6) -> bool:
        return all(bounds[ax][0] - eps <= p[i] <= bounds[ax][1] + eps for i, ax in enumerate(axes))

    obstacles: list[dict] = []
    for idx, ob in enumerate(payload.obstacles or []):
        kind = ob.get("kind")
        if dim == 2:
            if kind != "polygon":
                raise HTTPException(400, f"障碍 #{idx}：二维场景只支持 polygon")
            pts = [_to_floats(p, 2, f"障碍 #{idx} 顶点") for p in (ob.get("pts") or [])]
            if len(pts) < 3:
                raise HTTPException(400, f"障碍 #{idx}：多边形至少 3 个顶点")
            if any(not in_bounds(p) for p in pts):
                raise HTTPException(400, f"障碍 #{idx}：顶点超出边界")
            obstacles.append({"kind": "polygon", "pts": pts})
        else:
            if kind != "sphere":
                raise HTTPException(400, f"障碍 #{idx}：三维场景只支持 sphere")
            c = _to_floats(ob.get("c"), 3, f"障碍 #{idx} 球心")
            r = ob.get("r")
            if not isinstance(r, (int, float)) or r <= 0:
                raise HTTPException(400, f"障碍 #{idx}：半径必须为正")
            if not in_bounds(c):
                raise HTTPException(400, f"障碍 #{idx}：球心超出边界")
            obstacles.append({"kind": "sphere", "c": c, "r": float(r)})

    targets = [_to_floats(t, dim, "目标点") for t in (payload.targets or [])]
    if any(not in_bounds(t) for t in targets):
        raise HTTPException(400, "目标点超出边界")
    return bounds, obstacles, targets


def _grid_positions(bounds: dict, n: int, dim: int) -> list[list[float]]:
    """无初始位姿时生成一个紧凑编队：沿 x 排开，y/z 取中心。"""
    axes = ["x", "y"] if dim == 2 else ["x", "y", "z"]
    center = [(bounds[ax][0] + bounds[ax][1]) / 2 for ax in axes]
    span = min(bounds["x"][1] - bounds["x"][0], bounds["y"][1] - bounds["y"][0]) * 0.1
    step = span / max(1, n - 1) if n > 1 else 0.0
    out = []
    for i in range(n):
        p = list(center)
        p[0] = center[0] - span / 2 + i * step
        out.append([round(v, 4) for v in p])
    return out


@router.get("/scenarios")
def list_scenarios(
    algo: str | None = Query(default=None),
    dim: int | None = Query(default=None),
    swarm_size: int | None = Query(default=None),
) -> dict:
    where, args = [], []
    if algo:
        where.append("algo = %s")
        args.append(algo)
    if dim:
        where.append("dim = %s")
        args.append(int(dim))
    if swarm_size:
        where.append("swarm_size = %s")
        args.append(int(swarm_size))
    base = """
        SELECT id, algo, swarm_size, slug, name, dim, source_type, is_public,
               JSON_LENGTH(obstacles) AS obstacle_count, bounds, goal, created_at
        FROM scenario
    """
    if where:
        base += " WHERE " + " AND ".join(where)
    base += " ORDER BY source_type = 'builtin' DESC, algo, swarm_size, id"
    rows = query_all(base, args)
    items = []
    for r in rows:
        items.append(
            {
                "id": r["id"],
                "algo": r["algo"],
                "swarm_size": r["swarm_size"],
                "slug": r["slug"],
                "name": r["name"],
                "dim": r["dim"],
                "source_type": r["source_type"],
                "obstacle_count": int(r.get("obstacle_count") or 0),
                "bounds": jloads(r.get("bounds"), {}),
                "targets": jloads(r.get("goal"), {}).get("targets", [])
                if isinstance(jloads(r.get("goal"), {}), dict)
                else [],
                "created_at": fmt_dt(r.get("created_at")),
            }
        )
    return {"items": items, "total": len(items)}


@router.get("/scenarios/{scenario_id}")
def get_scenario(scenario_id: int) -> dict:
    row = query_one("SELECT * FROM scenario WHERE id = %s", [scenario_id])
    if not row:
        raise HTTPException(404, "场景不存在")
    goal = jloads(row.get("goal"), {})
    return {
        "id": row["id"],
        "algo": row["algo"],
        "algo_key": ALGO_KEYS.get(row["algo"], ""),
        "swarm_size": row["swarm_size"],
        "slug": row["slug"],
        "name": row["name"],
        "dim": row["dim"],
        "source_type": row["source_type"],
        "map_format": row["map_format"],
        "bounds": jloads(row["bounds"], {}),
        "obstacles": jloads(row["obstacles"], []),
        "start_pose": jloads(row.get("start_pose")),
        "goal": goal,
        "targets": goal.get("targets", []) if isinstance(goal, dict) else [],
        "waypoints": jloads(row.get("waypoints")),
        "init_positions": jloads(row.get("init_positions"), []),
        "overrides": jloads(row.get("overrides")),
        "created_at": fmt_dt(row.get("created_at")),
    }


@router.post("/scenarios")
def create_scenario(payload: ScenarioIn) -> dict:
    bounds, obstacles, targets = _validate(payload)
    geometry = _scene_geometry(payload.dim, bounds, obstacles, targets)
    scene_hash = _sha256(geometry)
    existing = query_one("SELECT id FROM scenario WHERE algo = %s AND scene_hash = %s",
                         [payload.algo, scene_hash])
    if existing:
        return {"id": existing["id"], "created": False, "scene_hash": scene_hash}

    slug_base = "custom-%s" % scene_hash[:8]
    slug = slug_base
    suffix = 1
    while query_one("SELECT id FROM scenario WHERE algo = %s AND slug = %s", [payload.algo, slug]):
        suffix += 1
        slug = "%s-%d" % (slug_base, suffix)

    positions = payload.init_positions
    if not positions:
        positions = _grid_positions(bounds, payload.swarm_size, payload.dim)
    else:
        positions = [_to_floats(p, payload.dim, "初始位姿") for p in positions]
        if len(positions) != payload.swarm_size:
            raise HTTPException(400, "初始位姿数量与集群规模不一致")

    name = payload.name or "自定义 %s / %d 机" % (payload.algo, payload.swarm_size)
    goal = {"targets": targets, "primary": targets[0] if targets else None}
    with transaction() as cur:
        cur.execute(
            """
            INSERT INTO scenario
              (algo, swarm_size, slug, name, scene_hash, dim, bounds, obstacles,
               start_pose, goal, waypoints, init_positions, source_type, map_format,
               is_public, created_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'custom_generated','geometry_json',1,%s)
            """,
            [
                payload.algo, payload.swarm_size, slug, name, scene_hash, payload.dim,
                jdumps(bounds), jdumps(obstacles),
                jdumps(payload.start_pose) if payload.start_pose else None,
                jdumps(goal), jdumps({"mode": "independent"}), jdumps(positions),
                "web-console",
            ],
        )
        new_id = cur.lastrowid
    return {"id": new_id, "created": True, "scene_hash": scene_hash, "slug": slug}
