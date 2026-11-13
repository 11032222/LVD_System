"""[AI-MOD 2026-11-12] 算法与判据元信息：前端表单的默认值来源。"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.common import ALGO_KEYS, CRITERIA_LABELS, FAILURE_TYPES, MODE_LABELS

router = APIRouter(prefix="/api", tags=["meta"])

# 论文中的集群规模档位与攻击参数缺省值；自定义规模不受此限制（2–50）
ALGORITHMS = [
    {
        "key": "a1",
        "name": "Adaptive Swarm",
        "label": "自适应集群",
        "paper_sizes": [4, 8],
        "dim": 2,
        "summary": "二维自适应集群，攻击者逐步逼近并注入扰动",
        "defaults": {
            "drone_dist_thr": 0.07,
            "obstacle_dist_thr": None,
            "timeout_multiplier": 2.0,
            "candidate_count": 20,
            "sample_sigma": None,
            "reach_radius": None,
            "max_iterations": 300,
            "max_sim_time": None,
            "support_waypoints_mode": False,
            "support_attack_chain": False,
        },
        "attacker_speed": 1.0,
        "notes": "机间碰撞阈值取自 uav_crash_check 的 0.07 m",
    },
    {
        "key": "a2",
        "name": "Pietro",
        "label": "Pietro 集群",
        "paper_sizes": [10, 20],
        "dim": 2,
        "summary": "二维多边形障碍地图，countMatrix 箱式碰撞判定",
        "defaults": {
            "drone_dist_thr": 0.5,
            "obstacle_dist_thr": None,
            "timeout_multiplier": 2.0,
            "candidate_count": 20,
            "sample_sigma": None,
            "reach_radius": 0.8,
            "max_iterations": None,
            "max_sim_time": 60.0,
            "support_waypoints_mode": False,
            "support_attack_chain": False,
        },
        "attacker_speed": 1.0,
        "notes": "撞障碍由多边形内点判定，不设距离阈值；机间阈值 0.5 m",
    },
    {
        "key": "a3",
        "name": "Howard",
        "label": "Howard 集群",
        "paper_sizes": [6, 8, 10],
        "dim": 3,
        "summary": "三维球形障碍与三轴边界，支持攻击链与航点模式",
        "defaults": {
            "drone_dist_thr": None,
            "obstacle_dist_thr": None,
            "timeout_multiplier": 2.0,
            "candidate_count": 20,
            "sample_sigma": 0.8,
            "reach_radius": 1.0,
            "max_iterations": 150,
            "max_sim_time": None,
            "support_waypoints_mode": True,
            "support_attack_chain": True,
        },
        "attacker_speed": 1.0,
        "notes": "球形障碍判定由 Monitor 的碰撞球体给出",
    },
]


@router.get("/meta")
def meta() -> dict:
    return {
        "algorithms": ALGORITHMS,
        "algo_keys": ALGO_KEYS,
        "modes": [{"key": k, "label": v} for k, v in MODE_LABELS.items()],
        "criteria": [{"key": k, "label": v} for k, v in CRITERIA_LABELS.items()],
        "failure_types": [
            {"key": k, "label": v["label"], "color": v["color"]} for k, v in FAILURE_TYPES.items()
        ],
        "limits": {"custom_size_min": 2, "custom_size_max": 50, "max_candidates": 1000},
    }
