"""[AI-MOD 2026-11-12] 运行产物 → MySQL 导入器（RSFuzz 测试管理平台）。

职责：扫描 `RSFuzz/repro/runs/<algo>/s<size>/<mode>/<seed>/`，把 result.json 与
trace/*.jsonl 结构化后写入 001_schema.sql 定义的表。

设计约束：
  1. 幂等：task_run.replay_key 唯一，重复导入直接跳过（--dry-run 可先预览）；
  2. 采集缺失可接受：没有 trace 目录时 trace_state='none'，只是不建回放帧；
  3. 只读原始产物：不改 runs/ 下任何文件，artifact 表只登记相对路径 + sha256 + 字节数；
  4. 口令只来自 app/.env 或环境变量（见 app/core/config.py），不出现在代码与命令行。

用法（在 ex/app 下）：
  python -m app.etl.importer --dry-run
  python -m app.etl.importer --algo a2 --maxt 60 --collide 0
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

_APP_DIR = Path(__file__).resolve().parents[2]      # ex/app
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

import pymysql
from pymysql.cursors import DictCursor

from app.core.config import WORKSPACE_ROOT, Settings, load_settings

ALGO_NAME = {"a1": "Adaptive Swarm", "a2": "Pietro", "a3": "Howard"}
RUNS_ROOT = WORKSPACE_ROOT / "RSFuzz" / "repro" / "runs"
PIETRO_DIR = WORKSPACE_ROOT / "RSFuzz" / "Pietro"
SCHEMA_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# 通用小工具
# ---------------------------------------------------------------------------
def dumps(obj) -> str:
    """规范化 JSON：排序键 + 紧凑分隔符，保证同一语义得到同一哈希。"""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_obj(obj) -> str:
    return sha256_text(dumps(obj))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def num(v):
    """把 .mat / JSON 里的元素转成 float；空、NaN、不可转换都返回 None。"""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


# ---------------------------------------------------------------------------
# 扫描运行目录
# ---------------------------------------------------------------------------
@dataclass
class RunRef:
    algo_key: str     # a1/a2/a3
    algo: str         # Adaptive Swarm / Pietro / Howard
    size: int
    mode: str         # na/sa/ma
    variant: str      # 目录名后缀（如 ma_link1），无则 ''
    seed: int
    path: Path
    result: dict


def scan_runs(root: Path, algos: set[str], sizes: set[int] | None, modes: set[str] | None,
              seeds: set[int] | None = None) -> list[RunRef]:
    refs: list[RunRef] = []
    if not root.is_dir():
        return refs
    for algo_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        if algo_dir.name not in ALGO_NAME or (algos and algo_dir.name not in algos):
            continue
        for size_dir in sorted(p for p in algo_dir.iterdir() if p.is_dir()):
            m = re.fullmatch(r"s(\d+)", size_dir.name)
            if not m:
                continue
            size = int(m.group(1))
            if sizes and size not in sizes:
                continue
            for mode_dir in sorted(p for p in size_dir.iterdir() if p.is_dir()):
                mode, _, suffix = mode_dir.name.partition("_")
                if mode not in ("na", "sa", "ma") or (modes and mode not in modes):
                    continue
                for seed_dir in sorted(p for p in mode_dir.iterdir() if p.is_dir()):
                    if not seed_dir.name.isdigit():
                        continue
                    seed = int(seed_dir.name)
                    if seeds and seed not in seeds:
                        continue
                    rp = seed_dir / "result.json"
                    if not rp.is_file():
                        continue
                    try:
                        result = json.loads(rp.read_text(encoding="utf-8"))
                    except json.JSONDecodeError:
                        continue
                    refs.append(RunRef(algo_dir.name, ALGO_NAME[algo_dir.name], size,
                                       mode, suffix, seed, seed_dir, result))
    return refs


# ---------------------------------------------------------------------------
# 场景几何：Pietro 从 .mat 读真实障碍/目标（回放渲染需要），其他算法留空待补
# ---------------------------------------------------------------------------
def _pair_pts(xs, ys) -> list[list[float]]:
    pts = []
    for x, y in zip(xs, ys):
        fx, fy = num(x), num(y)
        if fx is None or fy is None:
            continue
        pts.append([round(fx, 6), round(fy, 6)])
    # MATLAB 地图把多边形首尾重复了一个点，落库前去重
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts.pop()
    return pts


def pietro_geometry(map_name: str):
    """返回 (map_size, obstacles, targets)。读不到时返回 (25.0, [], [])。"""
    import numpy as np
    import scipy.io as sio

    map_size = 25.0
    cfg = PIETRO_DIR / ("%s_simulation_config.m" % map_name)
    if cfg.is_file():
        mm = re.search(r"^\s*map_size\s*=\s*([0-9.]+)\s*;",
                       cfg.read_text(encoding="utf-8", errors="ignore"), re.M)
        if mm:
            map_size = float(mm.group(1))

    obstacles: list[dict] = []
    obs_file = PIETRO_DIR / ("%s_obstacles.mat" % map_name)
    if obs_file.is_file():
        # 布局与 MATLAB 一致：cell 的第 2k-1 / 2k 列是第 k 个多边形的 x / y 顶点向量
        arr = np.asarray(sio.loadmat(str(obs_file), squeeze_me=True)["obstacles"], dtype=object)
        if arr.ndim == 2:
            for k in range(arr.shape[1] // 2):
                pts = _pair_pts(arr[0, 2 * k], arr[0, 2 * k + 1])
                if len(pts) >= 3:
                    obstacles.append({"kind": "polygon", "pts": pts})

    targets: list[list[float]] = []
    tgt_file = PIETRO_DIR / ("%s_targets.mat" % map_name)
    if tgt_file.is_file():
        t = sio.loadmat(str(tgt_file), squeeze_me=True)["targets"]
        targets = [[round(float(x), 6), round(float(y), 6)] for x, y in zip(t[0], t[1])]
    return map_size, obstacles, targets


def read_trace(run_dir: Path):
    """读 trace/*.jsonl。返回 (frames, iters, 是否存在 trace 目录)。"""
    trace_dir = run_dir / "trace"
    frames, iters = [], []
    fpath = trace_dir / "frame.jsonl"
    if fpath.is_file():
        for line in fpath.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                frames.append(json.loads(line))
    ipath = trace_dir / "iter.jsonl"
    if ipath.is_file():
        for line in ipath.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                rec = json.loads(line)
                if num(rec.get("rob")) is not None:   # robustness NOT NULL
                    iters.append(rec)
    return frames, iters, trace_dir.is_dir()


# ---------------------------------------------------------------------------
# 场景 / 判据 / 批次：按唯一键做 get-or-create
# ---------------------------------------------------------------------------
def build_scenario(ref: RunRef, frames) -> dict:
    """构造 scenario 行。scene_hash 只覆盖几何，便于"同图不同批次"复用同一场景。"""
    map_name = ref.result.get("map") or "default"
    dim = 3 if ref.algo_key == "a3" else 2
    bounds = None
    map_json = ref.path / "map.json"          # A1/A3 采集时由 write_map 写出
    if ref.algo_key == "a2":
        map_size, obstacles, targets = pietro_geometry(map_name)
        bounds = {"x": [0.0, float(map_size)], "y": [0.0, float(map_size)]}
    elif map_json.is_file():
        # [AI-MOD 2026-11-12] A1：障碍多边形/起终点取自 map.json（targets 缺省时退化为单个 goal）
        # [AI-MOD 2026-11-12] A3：球形障碍 + 三轴边界 + 每机终点，同样取自 map.json
        geo = json.loads(map_json.read_text(encoding="utf-8"))
        obstacles = geo.get("obstacles", [])
        if geo.get("targets"):
            targets = geo["targets"]
        else:
            targets = [geo["goal"]] if geo.get("goal") else []
        bounds = geo.get("bounds")
        map_size = max(bounds["x"][1] - bounds["x"][0], bounds["y"][1] - bounds["y"][0])
    else:
        # 采集缺失时的兜底：先用首帧位姿的外接框占位，保证可回放
        obstacles, targets, map_size = [], [], None
        if frames:
            xs = [a["p"][0] for a in frames[0]["agents"]]
            ys = [a["p"][1] for a in frames[0]["agents"]]
            map_size = math.ceil(max(max(xs), max(ys))) if xs and ys else None

    size = float(map_size) if map_size else 1.0
    if bounds is None:
        bounds = {"x": [0.0, size], "y": [0.0, size]}
        if dim == 3:
            bounds["z"] = [0.0, size]
    geometry = {"dim": dim, "bounds": bounds, "obstacles": obstacles, "targets": targets}
    scene_hash = sha256_obj(geometry)

    init_positions = []
    if frames:
        init_positions = [a["p"] for a in frames[0]["agents"] if a.get("k") == "uav"]
    if not init_positions:
        init_positions = [[size / 2] * dim for _ in range(ref.size)]

    return {
        "algo": ref.algo,
        "swarm_size": ref.size,
        "slug": "%s-s%d" % (map_name, ref.size),
        "name": "%s / %s / %d 机" % (ref.algo, map_name, ref.size),
        "scene_hash": scene_hash,
        "dim": dim,
        "bounds": dumps(bounds),
        "obstacles": dumps(obstacles),
        "targets": dumps(targets),
        "init_positions": dumps(init_positions),
    }


def build_criteria(ref: RunRef, cfg: dict) -> dict:
    """按算法/模式生成判据参数。params_hash 覆盖全部字段，天然去重。

    注意 params 里必须带算法名：三套系统的阈值口径完全不同（A1 机间 0.07 m、
    A2 countMatrix 0.5 m、A3 用 Monitor 球体判定），否则不同算法会撞到同一个哈希。
    """
    is_a2 = ref.algo_key == "a2"
    is_a1 = ref.algo_key == "a1"
    params = {
        "algo": ref.algo,
        "obstacle_dist_thr": None,                     # A2 用多边形内点判定撞障碍，不设距离阈值
        # A1: fuzz.py uav_crash_check 的机间阈值 0.07 m；A2: countMatrix 的 0.5 m 箱式阈值；A3: 待核对
        "drone_dist_thr": 0.07 if is_a1 else (0.5 if is_a2 else None),
        "timeout_multiplier": 2.0,                     # 论文判据①：2×CTime
        "enable_obstacle": 1,
        "enable_collision": int(cfg["collide"]),
        "enable_timeout": 1,
        "candidate_count": 20,                         # SA/MA 每轮 20 个候选
        "reach_radius": 1.0 if (is_a2 and ref.mode == "sa") else None,  # A2 attack_agent_v；MA 是瞬移
        "sample_sigma": None,
        "max_iterations": 300 if is_a1 else None,      # A1 abort_detection: self.time > 300
        "max_sim_time": cfg["maxt"] if is_a2 else None,
        "extra": {"attack_agent_v": 1.0, "mode": ref.mode} if is_a2 else {"mode": ref.mode},
    }
    params_hash = sha256_obj(params)
    paper_like = cfg["maxt"] is None and bool(cfg["collide"])
    return {
        "name": "%s-%s-c%s" % (ref.algo_key, ref.mode, params_hash[:8]),
        "params_hash": params_hash,
        "profile_kind": "paper" if paper_like else "custom",
        "description": "importer 自动生成（%s / %s / maxt=%s / collide=%s）"
                       % (ref.algo, ref.mode, cfg["maxt"], cfg["collide"]),
        "params": params,
    }


# ---------------------------------------------------------------------------
# 失败判定
# ---------------------------------------------------------------------------
def classify_failure(result: dict) -> tuple[str | None, int | None]:
    """返回 (failure_type, criterion)。判据编号对应论文 §IV-B ①②③。

    A2/A3 把原因写进 result.error（撞向障碍物/撞向边界/碰撞），
    A1 只有 result.message（"攻击成功，无人机碰撞到墙壁"），所以两处都要查。
    """
    text = "%s %s" % (result.get("error") or "", result.get("message") or "")
    if "撞向障碍物" in text or "墙壁" in text or "障碍" in text:
        return "obstacle", 2
    if "撞向边界" in text or "边界" in text:
        return "boundary", 2
    if "碰撞" in text:
        return "drone_collision", 3
    if result.get("timeout") or "超时" in text:
        return "timeout", 1
    if result.get("crashed"):
        return "custom", None
    return None, None


def analyze_last_frame(frame: dict, obstacles: list[dict]):
    """从最后一帧算失败现场：机间最近距离/碰撞对、到障碍最近距离。"""
    uavs = [a for a in frame.get("agents", []) if a.get("k") == "uav"]
    min_drone, pair, pairs = None, (None, None), []
    for i in range(len(uavs)):
        for j in range(i + 1, len(uavs)):
            dx = uavs[i]["p"][0] - uavs[j]["p"][0]
            dy = uavs[i]["p"][1] - uavs[j]["p"][1]
            d = math.hypot(dx, dy)
            min_drone = d if min_drone is None else min(min_drone, d)
            if abs(dx) <= 0.5 and abs(dy) <= 0.5:
                pairs.append([uavs[i]["id"], uavs[j]["id"]])
        if pairs:
            pair = (pairs[0][0], pairs[0][1])
            break

    min_obst, nearest = None, None
    try:
        from shapely.geometry import Point, Polygon
        for a in uavs:
            p = Point(a["p"][0], a["p"][1])
            for ob in obstacles:
                d = p.distance(Polygon(ob["pts"]))
                if min_obst is None or d < min_obst:
                    min_obst, nearest = d, a["id"]
    except Exception:
        pass

    pos = None
    if pair[0] is not None:
        a = next(x for x in uavs if x["id"] == pair[0])
        pos = a["p"]
    return {
        "min_drone_dist": min_drone,
        "min_obst_dist": min_obst,
        "nearest_agent": nearest,
        "pair": pair,
        "pairs": pairs,
        "position": pos,
    }


# ---------------------------------------------------------------------------
# 入库
# ---------------------------------------------------------------------------
def get_or_create(cur, table: str, unique: dict, row: dict) -> int:
    where = " AND ".join("%s = %%s" % k for k in unique)
    cur.execute("SELECT id FROM %s WHERE %s LIMIT 1" % (table, where), list(unique.values()))
    hit = cur.fetchone()
    if hit:
        return int(hit["id"])
    cols = list(row.keys())
    sql = "INSERT INTO %s (%s) VALUES (%s)" % (table, ", ".join(cols), ", ".join(["%s"] * len(cols)))
    cur.execute(sql, [row[c] for c in cols])
    return int(cur.lastrowid)


ARTIFACT_KINDS = {"result.json": "result_json", "matlab.log": "log",
                  "frame.jsonl": "trace_jsonl", "iter.jsonl": "iteration_log"}


def insert_artifacts(cur, task_run_id: int, run_dir: Path, path_root: Path):
    for f in sorted(run_dir.rglob("*")):
        if not f.is_file():
            continue
        kind = ARTIFACT_KINDS.get(f.name)
        if kind is None:
            continue
        rel = f.relative_to(path_root).as_posix()
        cur.execute(
            "INSERT INTO artifact (task_run_id, kind, rel_path, sha256, bytes, mime) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (task_run_id, kind, rel, sha256_file(f), f.stat().st_size, None))


def import_run(conn, settings: Settings, ref: RunRef, cfg: dict, path_root: Path, dry: bool) -> str:
    frames, iters, has_trace = read_trace(ref.path)
    scenario = build_scenario(ref, frames)
    criteria = build_criteria(ref, cfg)
    result = ref.result

    replay_key = sha256_obj({
        "algo": ref.algo,
        "swarm_size": ref.size,
        "slug": scenario["slug"],
        "mode": ref.mode,
        "variant": ref.variant,
        "seed": ref.seed,
        "criteria": criteria["params_hash"],
    })

    with conn.cursor() as cur:
        cur.execute("SELECT id FROM task_run WHERE replay_key = %s", (replay_key,))
        if cur.fetchone():
            return "skip"

        if dry:
            return "dry"

        cur.execute("SELECT id FROM scenario WHERE algo = %s AND scene_hash = %s",
                    (scenario["algo"], scenario["scene_hash"]))
        hit = cur.fetchone()
        if hit:
            scenario_id = int(hit["id"])
        else:
            scenario_id = get_or_create(
                cur, "scenario",
                {"algo": scenario["algo"], "scene_hash": scenario["scene_hash"]},
                {**{k: v for k, v in scenario.items() if k not in ("targets",)},
                 "goal": dumps({"targets": json.loads(scenario["targets"])})})

        criteria_id = get_or_create(
            cur, "criteria_profile", {"params_hash": criteria["params_hash"]},
            # algo 只参与 params_hash 计算，criteria_profile 表里没有这一列
            {k: v for k, v in criteria["params"].items() if k != "algo"} | {
                "extra": dumps(criteria["params"]["extra"]) if criteria["params"]["extra"] else None,
                "name": criteria["name"], "params_hash": criteria["params_hash"],
                "profile_kind": criteria["profile_kind"], "description": criteria["description"]})

        batch_key = sha256_obj({"import": ref.algo, "swarm_size": ref.size,
                                "criteria": criteria["params_hash"]})
        batch_id = get_or_create(
            cur, "batch", {"batch_key": batch_key},
            {"batch_key": batch_key, "algo": ref.algo, "swarm_size": ref.size,
             "modes": dumps([ref.mode]), "seed_from": ref.seed, "seed_to": ref.seed,
             "scheduler": "sched.py",
             "config_snapshot": dumps({"importer": "app/app/etl/importer.py",
                                       "schema": SCHEMA_VERSION, "maxt": cfg["maxt"],
                                       "collide": cfg["collide"]}),
             "status": "done"})

        ftype, crit = classify_failure(result)
        err_text = result.get("error") or ""
        steps = num(result.get("steps")) or num(result.get("iterations"))   # A1 只有 iterations
        agent_n = result.get("n") or result.get("robots")                    # A1 的字段名是 robots
        sim_t = num(result.get("sim_time"))
        if has_trace and frames:
            trace_state = "full" if (steps is None or len(frames) >= int(steps)) else "partial"
        else:
            trace_state = "none"

        cur.execute(
            "INSERT INTO task_run (batch_id, scenario_id, criteria_id, algo, mode, variant, seed, "
            "swarm_size, replay_key, status, failed, failure_type, failure_label, failure_criterion, "
            "crashed, timed_out, arrived, iterations, sim_time, wall_s, agent_total, error_message, "
            "result_json, trace_state) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (batch_id, scenario_id, criteria_id, ref.algo, ref.mode, ref.variant, ref.seed,
             ref.size, replay_key, "ok", int(bool(result.get("failed"))), ftype,
             err_text[:64] or None, crit,
             int(bool(result.get("crashed"))), int(bool(result.get("timeout"))),
             int(bool(result.get("arrived"))), len(iters) if iters else None,
             sim_t, float(result.get("wall_s") or 0.0),
             agent_n, err_text[:512] or None,
             dumps(result), trace_state))
        task_run_id = int(cur.lastrowid)

        if ftype and crit is not None and frames:
            info = analyze_last_frame(frames[-1], json.loads(scenario["obstacles"]))
            # agent_a/agent_b 只在判据③（机间碰撞）时有意义；超时/撞障碍只保留几何信息
            is_collision = (crit == 3)
            cur.execute(
                "INSERT INTO failure_event (task_run_id, criterion, step, sim_time, agent_a, agent_b, "
                "position, min_obst_dist, min_drone_dist, detail) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (task_run_id, crit, int(steps or 0), sim_t,
                 info["pair"][0] if is_collision else None,
                 info["pair"][1] if is_collision else None,
                 dumps(info["position"]) if info["position"] else None,
                 info["min_obst_dist"], info["min_drone_dist"],
                 dumps({"type": ftype, "error": result.get("error") or "",
                        "collision_pairs": info["pairs"],
                        "nearest_agent": info["nearest_agent"]})))

        if frames:
            cur.executemany(
                "INSERT INTO trace_frame (task_run_id, step, sim_time, agents) VALUES (%s,%s,%s,%s)",
                [(task_run_id, int(f["step"]), num(f.get("t")), dumps(f["agents"])) for f in frames])

        if iters:
            cur.executemany(
                "INSERT INTO iteration_metric (task_run_id, iter, sim_time, attacker_pos, robustness, "
                "candidates, extra) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                [(task_run_id, i, num(it.get("t")), dumps(it["pos"]), num(it["rob"]),
                  ref.result.get("candidates") or 20,
                  dumps({"step": int(it["step"])})) for i, it in enumerate(iters)])

        insert_artifacts(cur, task_run_id, ref.path, path_root)
    conn.commit()
    return "insert"


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="把 RSFuzz 运行产物导入 MySQL")
    ap.add_argument("--root", default=str(RUNS_ROOT), help="runs 根目录")
    ap.add_argument("--algo", default="all", help="a1/a2/a3，逗号分隔；all=全部")
    ap.add_argument("--size", default="", help="集群规模，逗号分隔；空=全部")
    ap.add_argument("--mode", default="", help="na/sa/ma，逗号分隔；空=全部")
    ap.add_argument("--seed", default="", help="种子号，逗号分隔；空=全部（用于只导新跑的那几个）")
    ap.add_argument("--maxt", type=float, default=0.0, help="A2 判据①的仿真时长上限（0=未截短）")
    ap.add_argument("--collide", default="0", help="A2 判据③开关（1=开启）")
    ap.add_argument("--path-root", default=str(WORKSPACE_ROOT), help="artifact.rel_path 的相对基准")
    ap.add_argument("--env-file", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    algos = set() if args.algo == "all" else {a.strip() for a in args.algo.split(",") if a.strip()}
    sizes = {int(x) for x in args.size.split(",") if x.strip()} or None
    modes = {x.strip() for x in args.mode.split(",") if x.strip()} or None
    cfg = {"maxt": args.maxt or None, "collide": args.collide == "1"}

    seeds = {int(x) for x in args.seed.split(",") if x.strip()} or None
    settings = load_settings(args.env_file)
    refs = scan_runs(Path(args.root), algos, sizes, modes, seeds)
    print("[import] %s 本次可选 %d 个任务（%s）" % (settings.dsn(), len(refs), args.root))
    if not refs:
        return 0

    conn = pymysql.connect(host=settings.db_host, port=settings.db_port, user=settings.db_user,
                           password=settings.db_password, database=settings.db_name,
                           charset="utf8mb4", cursorclass=DictCursor, autocommit=False)
    stats = {"insert": 0, "skip": 0, "dry": 0}
    t0 = time.time()
    with conn.cursor() as cur:
        cur.execute("INSERT INTO import_log (source_root, status) VALUES (%s,'running')",
                    (str(Path(args.root).resolve()),))
        log_id = int(cur.lastrowid)
    conn.commit()

    for i, ref in enumerate(refs, 1):
        try:
            act = import_run(conn, settings, ref, cfg, Path(args.path_root), args.dry_run)
        except Exception as exc:                      # 单任务失败不中断整批
            conn.rollback()
            act = "error"
            print("[%d/%d] %s %s s%d seed=%d -> 失败: %s"
                  % (i, len(refs), ref.algo_key, ref.mode, ref.size, ref.seed, exc))
        stats[act] = stats.get(act, 0) + 1
        if act != "error":
            print("[%d/%d] %s %s s%d seed=%d -> %s"
                  % (i, len(refs), ref.algo_key, ref.mode, ref.size, ref.seed, act))

    with conn.cursor() as cur:
        cur.execute("UPDATE import_log SET finished_at = CURRENT_TIMESTAMP(3), file_count = %s, "
                    "inserted = %s, skipped = %s, status = %s, note = %s WHERE id = %s",
                    (len(refs), stats["insert"], stats["skip"] + stats["dry"],
                     "ok" if not stats.get("error") else "partial",
                     "dry-run" if args.dry_run else None, log_id))
    conn.commit()
    conn.close()
    print("[import] 完成 insert=%d skip=%d dry=%d error=%d 用时 %.1fs"
          % (stats["insert"], stats["skip"], stats["dry"], stats.get("error", 0),
             time.time() - t0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
