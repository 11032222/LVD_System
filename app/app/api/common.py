"""[AI-MOD 2026-11-12] API 公共工具：分页、失败类型字典、时间格式化。"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

ALGO_KEYS = {"Adaptive Swarm": "a1", "Pietro": "a2", "Howard": "a3"}
ALGO_NAMES = {v: k for k, v in ALGO_KEYS.items()}

MODE_LABELS = {
    "na": "NA 无攻击",
    "sa": "SA 单攻击者",
    "ma": "MA 多攻击者",
}

FAILURE_TYPES = {
    "obstacle": {"label": "撞障碍", "criterion": 2, "color": "#e8833a"},
    "drone_collision": {"label": "机间碰撞", "criterion": 2, "color": "#d9534f"},
    "boundary": {"label": "集群越界", "criterion": 2, "color": "#8262c9"},
    "timeout": {"label": "任务超时", "criterion": 1, "color": "#4a6fa5"},
    "none": {"label": "未复现失败", "criterion": None, "color": "#9aa4b2"},
    "custom": {"label": "自定义判据", "criterion": 3, "color": "#38a3a5"},
}

CRITERIA_LABELS = {
    1: "① 任务超时（2×CTime）",
    2: "② 状态越界（撞障碍 / 机间碰撞）",
    3: "③ 轨迹偏离",
}


def failure_label(ftype: str | None) -> str:
    if not ftype:
        return FAILURE_TYPES["none"]["label"]
    return FAILURE_TYPES.get(ftype, {}).get("label", ftype)


def fmt_dt(value: Any) -> str | None:
    """统一成前端可直接展示的 ISO 字符串（不带时区，本地时间）。"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    return str(value)


def page_args(page: int, page_size: int) -> tuple[int, int]:
    page = max(1, int(page or 1))
    page_size = min(200, max(1, int(page_size or 20)))
    return page, page_size


def paged(items: list[dict], total: int, page: int, page_size: int) -> dict:
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if page_size else 0,
    }


def run_brief(row: dict) -> dict:
    """任务行的轻量视图：列表页与详情页共用。"""
    return {
        "id": row["id"],
        "batch_id": row["batch_id"],
        "batch_key": row.get("batch_key"),
        "algo": row["algo"],
        "algo_key": ALGO_KEYS.get(row["algo"], ""),
        "mode": row["mode"],
        "mode_label": MODE_LABELS.get(row["mode"], row["mode"]),
        "variant": row.get("variant") or "",
        "seed": row["seed"],
        "swarm_size": row["swarm_size"],
        "status": row["status"],
        "failed": int(row["failed"]),
        "failure_type": row.get("failure_type"),
        "failure_label": row.get("failure_label") or failure_label(row.get("failure_type")),
        "failure_criterion": row.get("failure_criterion"),
        "iterations": row.get("iterations"),
        "sim_time": row.get("sim_time"),
        "wall_s": row.get("wall_s"),
        "trace_state": row.get("trace_state"),
        "created_at": fmt_dt(row.get("created_at")),
        "scenario_id": row.get("scenario_id"),
        "scenario_name": row.get("scenario_name"),
    }
