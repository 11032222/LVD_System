"""[AI-MOD 2026-11-12] 首页数据概览。"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.common import ALGO_KEYS, FAILURE_TYPES, failure_label, fmt_dt, run_brief
from app.db import query_all, query_one

router = APIRouter(prefix="/api", tags=["overview"])


@router.get("/overview")
def overview() -> dict:
    counts = query_one(
        """
        SELECT
          (SELECT COUNT(*) FROM batch)        AS batches,
          (SELECT COUNT(*) FROM batch WHERE status = 'running') AS running_batches,
          (SELECT COUNT(*) FROM task_run)     AS runs,
          (SELECT COUNT(*) FROM task_run WHERE failed = 1)      AS failed,
          (SELECT COUNT(*) FROM trace_frame)  AS frames,
          (SELECT COUNT(*) FROM iteration_metric) AS iterations,
          (SELECT COUNT(*) FROM scenario)     AS scenarios,
          (SELECT COALESCE(SUM(wall_s), 0) FROM task_run) AS wall_s
        """
    ) or {}

    runs = int(counts.get("runs") or 0)
    failed = int(counts.get("failed") or 0)
    counts["failure_rate"] = round(failed / runs, 4) if runs else 0.0
    counts["wall_s"] = round(float(counts.get("wall_s") or 0), 1)

    algos = query_all(
        """
        SELECT algo,
               COUNT(*)          AS runs,
               SUM(failed)       AS failed,
               GROUP_CONCAT(DISTINCT swarm_size ORDER BY swarm_size) AS sizes,
               GROUP_CONCAT(DISTINCT mode ORDER BY mode)             AS modes,
               MAX(created_at)   AS last_at,
               SUM(COALESCE(iterations, 0)) AS iterations
        FROM task_run
        GROUP BY algo
        """
    )
    for a in algos:
        n = int(a["runs"] or 0)
        f = int(a["failed"] or 0)
        a["runs"], a["failed"] = n, f
        a["failure_rate"] = round(f / n, 4) if n else 0.0
        a["algo_key"] = ALGO_KEYS.get(a["algo"], "")
        a["sizes"] = [int(x) for x in (a["sizes"] or "").split(",") if x]
        a["modes"] = [x for x in (a["modes"] or "").split(",") if x]
        a["last_at"] = fmt_dt(a.get("last_at"))
        a["iterations"] = int(a.get("iterations") or 0)
    algos.sort(key=lambda x: list(ALGO_KEYS).index(x["algo"]) if x["algo"] in ALGO_KEYS else 99)

    ft_rows = query_all(
        """
        SELECT COALESCE(failure_type, 'none') AS type, COUNT(*) AS count
        FROM task_run WHERE failed = 1
        GROUP BY COALESCE(failure_type, 'none')
        ORDER BY count DESC
        """
    )
    failure_types = [
        {
            "type": r["type"],
            "label": failure_label(r["type"]),
            "count": int(r["count"]),
            "color": FAILURE_TYPES.get(r["type"], {}).get("color", "#9aa4b2"),
        }
        for r in ft_rows
    ]

    activity = query_all(
        """
        SELECT DATE(created_at) AS day, COUNT(*) AS runs, SUM(failed) AS failed
        FROM task_run
        GROUP BY DATE(created_at)
        ORDER BY day DESC
        LIMIT 14
        """
    )
    activity = [
        {"day": fmt_dt(r["day"]), "runs": int(r["runs"]), "failed": int(r["failed"] or 0)}
        for r in reversed(activity)
    ]

    recent = query_all(
        """
        SELECT r.id, r.batch_id, r.algo, r.mode, r.variant, r.seed, r.swarm_size, r.status,
               r.failed, r.failure_type, r.failure_label, r.failure_criterion, r.iterations,
               r.sim_time, r.wall_s, r.trace_state, r.created_at, r.scenario_id,
               s.name AS scenario_name, b.batch_key
        FROM task_run r
        JOIN batch b    ON b.id = r.batch_id
        LEFT JOIN scenario s ON s.id = r.scenario_id
        ORDER BY r.created_at DESC, r.id DESC
        LIMIT 6
        """
    )

    return {
        "counts": counts,
        "algos": algos,
        "failure_types": failure_types,
        "activity": activity,
        "recent_runs": [run_brief(r) for r in recent],
    }
