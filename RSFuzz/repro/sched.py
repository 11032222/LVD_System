# -*- coding: utf-8 -*-
"""[AI-MOD 2026-11-05] 三算法统一批量调度器。

设计要点（对应论文 §IV-B 与 Linux 报告的工程经验）：
  1. 每任务独立工作目录 + 独立输出目录，避免相对路径互相覆盖；
  2. 每个任务固定种子，基线/SA/MA 用同一批种子，才能做同种子配对 McNemar 检验；
  3. 单任务硬超时，防止个别用例挂死（论文判据之外的保护措施，不影响统计口径）；
  4. 断点续跑：已有 result.json 的任务自动跳过。

用法示例:
  python sched.py --algo a1 --seeds 1-100 --strategies 0,2,3 --workers 12
  python sched.py --algo a2 --seeds 1-100 --strategies 0,2,3 --workers 8
  python sched.py --algo a3 --seeds 1-100 --strategies 0,2,3 --workers 10
"""
import argparse
import csv
import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
PY = r"D:\Anaconda_envs\envs\py3.10\python.exe"
MATLAB = r"D:\matlab2024b\bin\matlab.exe"

ALGO_CFG = {
    "a1": {"timeout": 2400, "driver": os.path.join(HERE, "run_a1.py")},
    "a2": {"timeout": 1800, "driver": os.path.join(ROOT, "Pietro", "run_a2.m")},
    "a3": {"timeout": 1200, "driver": os.path.join(ROOT, "Howard", "src", "run_a3.m")},
}
MODE_NAME = {0: "na", 2: "sa", 3: "ma"}
# [AI-MOD 2026-11-09] 论文 Table II 每种算法都有 3 个规模档；两环境统一取“最小+最大”两档。
# 目录按 s<size> 分层，避免同一 seed 的不同规模互相覆盖（旧数据留在原路径不动）。
ALGO_SIZES = {"a1": [4, 8], "a2": [10, 20], "a3": [6, 10]}
SIZE = None    # [AI-MOD] 由 --size 注入；None = 取该算法最小档（等价于旧行为）
A3LINK = "0"   # A3 攻击链开关：0=上游原样（消融），1=按论文让攻击机进入集群势场
MAXIT = "0"    # [AI-MOD] 迭代/步数上限；"0"=用被测程序默认值（A3 上游 150）
MAXT = "0"     # [AI-MOD] A2 仿真时长上限（秒）；"0"=用上游配置的 t_end
COLLIDE = "0"  # [AI-MOD] A2 判据③（机间碰撞）开关：0=关闭（见 A2_Fuzzing.m 中的说明）
# [AI-MOD 2026-11-12] 数据采集开关：1=被测程序每步写 $RSFUZZ_OUT/trace/*.jsonl（回放帧 + 鲁棒度曲线）；
# 0=不采集（默认，行为与原版逐位一致）。采集只读状态、不参与任何计算与判定。
TRACE = "0"

# [AI-MOD 2026-11-05] 并发启动的多个 MATLAB 实例会争用同一个 preferences 目录，
# 随机触发 "Fatal Startup Error: System Error: File system inconsistency" 并直接退出码 1。
# 这里给每个并发槽位（线程）分配独立 MATLAB_PREFDIR，实测 4 并发全部正常。
_PREF_LOCK = threading.Lock()
_PREF_SLOT = {}
_PREF_NEXT = [0]
_PROC_TAG = os.urandom(4).hex()   # [AI-MOD] 进程随机标签：Windows 会复用 PID，仅靠 PID 会继承上一次的坏目录
_START_LOCK = threading.Lock()   # [AI-MOD] MATLAB 启动串行化（见 run_one）
# [AI-MOD 2026-11-10] 原为 15 s，用于错开多个 matlab.exe 的启动时刻、规避
# "Fatal Startup Error: File system inconsistency"。根因查明是残留孤儿引擎（见下方说明），
# 修复后实测 6 并发 12/12、10 并发 20/20 全部成功且 0 残留，故该间隔不再需要。
# 保留 _START_LOCK 只是把"创建进程"这一步用微秒级串行保护一下，没有实际等待。
START_GAP = 0.0


# [AI-MOD 2026-11-10] MATLAB 并行启动失败的真正根因（2026-11-10 实测确认）：
#   1. `bin\matlab.exe` 只是启动器，真正的引擎是子进程 `bin\win64\MATLAB.exe`。
#   2. `-batch` 实例经常在**脚本跑完之后卡在退出阶段**：实测任务 2.4 s 就写完 result.json，
#      而进程 300 s 仍未退出（CPU 不再增长、常驻 ~580 MB）。
#   3. 旧代码用 subprocess.run(timeout=...)，超时只会 kill 启动器，引擎变成孤儿并
#      占住启动期锁；累积几具之后，后续任何启动都报
#      "Fatal Startup Error: System Error: File system inconsistency"。
#   实测对照：6 并发 × 12 个真实 A3 任务，12/12 都在 2.8 s 内写完了 result.json；
#   清空全部残留进程后，串行 16/16、6 并发 12/12 启动均正常。
# 因此正确做法不是"限制并发"，而是：
#   (a) 不等进程退出，result.json 一出现就杀**整棵进程树**；
#   (b) 每批开始前清理上一批残留的 -batch 实例。
def kill_tree(pid):
    """杀掉 pid 及其全部子进程（Windows 下必须用 /T，否则引擎会残留）。"""
    try:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                       capture_output=True, timeout=30)
    except Exception:
        pass


def reap_stale_matlab():
    """清理上一批调度残留的 MATLAB -batch 实例。

    只杀命令行里带本仓库路径或 run_a2/run_a3 的进程，避免误杀用户自己打开的 MATLAB。
    """
    ps = ("Get-CimInstance Win32_Process -Filter \"Name='MATLAB.exe'\" | "
          "Where-Object { $_.CommandLine -like '*run_a2*' -or "
          "$_.CommandLine -like '*run_a3*' -or "
          "$_.CommandLine -like '*RSFuzz*' } | "
          "Select-Object -ExpandProperty ProcessId")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                             capture_output=True, text=True, timeout=60)
        pids = [x.strip() for x in (out.stdout or "").split() if x.strip().isdigit()]
        for pid in pids:
            kill_tree(pid)
        if pids:
            print("[sched] 清理残留 MATLAB 实例 %d 个" % len(pids), flush=True)
    except Exception:
        pass


def _read_tail(path, n=800):
    """读日志文件末尾 n 字节（用于识别 Fatal Startup Error）。"""
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - n))
            return f.read().decode("utf-8", "ignore")
    except Exception:
        return ""


def _result_ready(res_file):
    """result.json 已完整落盘（能解析成 JSON）。

    [AI-MOD 2026-11-10] 只看文件是否存在有风险：MATLAB 可能刚 fopen 还没写完就被杀掉，
    留下半截 JSON 让后续分析全部崩掉。因此要求能被 json.load 成功解析。
    """
    try:
        with open(res_file, "r", encoding="utf-8") as f:
            json.load(f)
        return True
    except Exception:
        return False


def _write_timeout(res_file, algo, strategy, seed, t0):
    """超时按论文判据属于“任务未完成”，记为失败，便于统计但不掩盖原因。"""
    rec = {"algo": algo.upper(), "strategy": strategy, "seed": seed,
           "failed": True, "message": "wall-clock timeout", "iterations": None,
           "wall_s": round(time.time() - t0, 2), "error": "TASK_TIMEOUT"}
    with open(res_file, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False)


def _matlab_watch(cmd, env, res_file, timeout, log_path):
    """[AI-MOD 2026-11-10] 启动 MATLAB 并轮询 result.json，落盘即杀整棵进程树。

    返回 (rc, timed_out)。rc 仅用于失败诊断，判成功一律以 result.json 为准。
    关键点：**不等进程自然退出**。本次实测 MATLAB -batch 跑完脚本后会卡在退出阶段
    （任务 2.4 s 写完 result.json，进程 300 s 仍不退），必须靠 result.json 判定完成。
    """
    # 输出重定向到文件而不是 PIPE：避免子进程输出把管道写满后互相等待（死锁）。
    logf = open(log_path, "wb")
    p = None
    try:
        try:
            p = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT,
                                 env=env, cwd=ROOT)
        except Exception as e:
            return None, False, "POPEN_FAIL: %s" % e
        deadline = time.time() + timeout
        first_seen = None
        while True:
            now = time.time()
            if os.path.exists(res_file):
                if _result_ready(res_file):
                    return p.poll(), False, ""
                # 文件已出现但还没写完：最多再等 30 s，防止半截 JSON 被当成结果
                if first_seen is None:
                    first_seen = now
                elif now - first_seen > 30.0:
                    return p.poll(), False, ""
            elif p.poll() is not None:
                # 进程自己退了（正常退出或启动失败），交给调用方看 result.json / 日志
                return p.returncode, False, ""
            if now > deadline:
                return -9, True, ""
            time.sleep(0.2)
    finally:
        # 无论何种出口（成功、失败、异常）都杀整棵树，杜绝引擎变孤儿占住启动锁
        if p is not None:
            kill_tree(p.pid)
        logf.close()


def prefdir_for_current_thread(renew=False):
    tid = threading.get_ident()
    with _PREF_LOCK:
        if renew:
            # [AI-MOD 2026-11-05] 启动失败后必须换一个全新目录：MATLAB 中途崩溃会在
            # prefdir 里留下锁文件/半成品，同一目录再启动会一直报 File system inconsistency。
            _PREF_SLOT[tid] = _PREF_NEXT[0]
            _PREF_NEXT[0] += 1
        elif tid not in _PREF_SLOT:
            _PREF_SLOT[tid] = _PREF_NEXT[0]
            _PREF_NEXT[0] += 1
        slot = _PREF_SLOT[tid]
    # [AI-MOD 2026-11-05] 目录名必须带本调度器进程的 PID + 随机标签：同时启动多个 sched.py
    # （例如 A1 与 A2 并行）时，各进程的线程槽都从 w00 开始，会踩到同一个 prefs 目录；
    # 而 Windows 复用 PID 时，光有 PID 仍可能继承上一次崩溃留下的坏目录。
    d = os.path.join(HERE, "prefs", "p%d_%s_w%02d" % (os.getpid(), _PROC_TAG, slot))
    os.makedirs(d, exist_ok=True)
    return d


def parse_seeds(text):
    seeds = []
    for part in text.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-")
            seeds.extend(range(int(a), int(b) + 1))
        elif part:
            seeds.append(int(part))
    return seeds


def task_paths(algo, strategy, seed):
    mode = MODE_NAME[strategy]
    if algo == "a3" and A3LINK == "1" and strategy != 0:
        mode = mode + "_link1"
    # [AI-MOD 2026-11-09] 按规模分目录：runs/<algo>/s<size>/<mode>/<seed>
    size = SIZE or ALGO_SIZES[algo][0]
    # out = os.path.join(HERE, "runs", algo, mode, str(seed))          # 上游/旧路径
    out = os.path.join(HERE, "runs", algo, "s%d" % size, mode, str(seed))
    # work = os.path.join(HERE, "work", algo, "%s_%d" % (mode, seed))   # 上游/旧路径
    work = os.path.join(HERE, "work", algo, "%s_s%d_%d" % (mode, size, seed))
    return out, work


def build_cmd(algo, strategy, seed):
    out, work = task_paths(algo, strategy, seed)
    os.makedirs(out, exist_ok=True)
    os.makedirs(work, exist_ok=True)
    size = SIZE or ALGO_SIZES[algo][0]
    if algo == "a1":
        # [AI-MOD 2026-11-12] 采集开关：A1 在 run_a1.py 里读 RSFUZZ_TRACE 包装攻击策略，
        # 不设置时 trace_a1 完全不生效（零开销）。
        env = os.environ.copy()
        env["RSFUZZ_TRACE"] = TRACE
        env["RSFUZZ_OUT"] = out
        # [AI-MOD 2026-11-09] 规模档注入：论文 A1 为 4/6/8 机，这里按档位传 --robots
        return [PY, ALGO_CFG["a1"]["driver"], "--strategy", str(strategy), "--seed", str(seed),
                "--robots", str(size),
                "--tag", "a1_%s_%d" % (MODE_NAME[strategy], seed),
                "--work", work, "--out", out], out, env
    env = os.environ.copy()
    env["MATLAB_PREFDIR"] = prefdir_for_current_thread()  # [AI-MOD] 见函数说明：隔离 MATLAB 偏好目录
    env["RSFUZZ_SEED"] = str(seed)
    env["RSFUZZ_MODE"] = MODE_NAME[strategy]
    env["RSFUZZ_WORK"] = work
    env["RSFUZZ_OUT"] = out
    env["RSFUZZ_DRAW"] = "0"          # 批量实验统一关闭绘图
    # env["RSFUZZ_ND"] = {0: "6", 2: "6", 3: "6"}[strategy]  # 上游：A3 固定 6 机
    # [AI-MOD 2026-11-09] 论文 A3 规模档 6/8/10；A2 规模档 10/15/20 走 RSFUZZ_N
    env["RSFUZZ_ND"] = str(size)
    env["RSFUZZ_N"] = str(size)
    # 无攻击基线必须关掉攻击链，否则攻击机停在势场里会污染基线
    env["RSFUZZ_A3_LINK"] = "0" if strategy == 0 else A3LINK
    if MAXIT != "0":
        env["RSFUZZ_MAXIT"] = MAXIT   # [AI-MOD] 论文判据①：超时阈值 = 2×实测 CTime
    if MAXT != "0":
        env["RSFUZZ_MAXT"] = MAXT     # [AI-MOD] A2 判据①：仿真时长上限 = 2×实测 CTime
    env["RSFUZZ_COLLIDE"] = COLLIDE   # [AI-MOD] A2 判据③ 开关
    env["RSFUZZ_TRACE"] = TRACE       # [AI-MOD 2026-11-12] 数据采集开关（见 rsfuzz_trace.m）
    drv = ALGO_CFG[algo]["driver"]
    drv_dir = os.path.dirname(drv).replace("\\", "/")
    drv_fun = os.path.splitext(os.path.basename(drv))[0]
    # [AI-MOD 2026-11-05] MATLAB 默认会按物理核数开多线程 BLAS，在 8 路并发下会占满整机，
    # 把同机并行的 A1 Python 任务挤到 0.3 核。被测代码是标量循环，多线程无收益，
    # 因此强制单线程执行，提升整体吞吐。
    return [MATLAB, "-singleCompThread", "-batch", "addpath('%s'); %s" % (drv_dir, drv_fun)], out, env


def run_one(algo, strategy, seed):
    out, _ = task_paths(algo, strategy, seed)
    res_file = os.path.join(out, "result.json")
    if os.path.exists(res_file):
        return "skip", seed, strategy, 0.0, ""
    built = build_cmd(algo, strategy, seed)
    cmd, out = built[0], built[1]
    env = built[2] if len(built) > 2 else None
    t0 = time.time()
    rc, tail = 0, ""
    # [AI-MOD 2026-11-05] MATLAB 并发启动（≥5 个同时）偶发
    #   Fatal Startup Error: System Error: File system inconsistency
    # 即使每个并发槽位已分配独立 MATLAB_PREFDIR 仍会出现（实测 3~4 个并发稳定、5 个起批量失败）。
    # 这属于 MATLAB 启动期的环境冲突，不是被测程序的失败，因此重试 3 次并逐次退避，
    # 避免把启动故障误记成任务失败（会污染失败率统计）。
    for attempt in range(3):
        # [AI-MOD 2026-11-05] 串行化 MATLAB 启动：多个 matlab.exe 同一瞬间启动时，即使
        # MATLAB_PREFDIR 各不相同，仍会批量报 "Fatal Startup Error: System Error:
        # File system inconsistency"（实测 4 并发必现、2 并发正常，且与被测程序无关）。
        # 这里用全局锁把启动时刻错开 START_GAP 秒，任务本身仍并行执行。
        if algo != "a1":
            with _START_LOCK:
                time.sleep(START_GAP)
        if algo == "a1":
            # A1 是纯 Python 驱动，不会卡退出，保留原来的阻塞式调用
            try:
                p = subprocess.run(cmd, capture_output=True, timeout=ALGO_CFG[algo]["timeout"],
                                   env=env, cwd=ROOT)
                rc = p.returncode
                tail = (p.stdout or b"")[-400:].decode("utf-8", "ignore") + \
                       (p.stderr or b"")[-400:].decode("utf-8", "ignore")
            except subprocess.TimeoutExpired:
                rc, tail = -9, "TASK_TIMEOUT"
                _write_timeout(res_file, algo, strategy, seed, t0)
                break
        else:
            # [AI-MOD 2026-11-10] A2/A3 改用「轮询 result.json + 落盘即杀进程树」：
            # MATLAB -batch 跑完脚本后会卡在退出阶段（实测 2.4 s 就写完 result.json，
            # 进程 300 s 仍不退），旧的 subprocess.run 只能等超时，超时又只杀启动器，
            # 引擎变孤儿后占住启动锁，累积几次后所有新启动都报 Fatal Startup Error。
            log_path = os.path.join(out, "matlab.log")
            rc, timed_out, err = _matlab_watch(cmd, env, res_file,
                                               ALGO_CFG[algo]["timeout"], log_path)
            tail = _read_tail(log_path)
            if err:
                tail += "\n" + err
            if timed_out:
                rc, tail = -9, "TASK_TIMEOUT"
                _write_timeout(res_file, algo, strategy, seed, t0)
                break
        if "Fatal Startup Error" not in tail:
            break
        # [AI-MOD 2026-11-05] 启动失败后换一个全新的 MATLAB_PREFDIR 再重试：
        # 崩溃的实例会把锁文件/半成品留在自己的 prefdir 里，原地重试必然继续失败。
        if attempt < 2 and algo != "a1" and env is not None:
            env["MATLAB_PREFDIR"] = prefdir_for_current_thread(renew=True)
        time.sleep(5.0 * (attempt + 1))
    status = "ok" if os.path.exists(res_file) else "fail(rc=%s)" % rc
    return status, seed, strategy, round(time.time() - t0, 1), tail.strip()[-300:]


def summarize(algo, strategies, seeds):
    path = os.path.join(HERE, "runs", algo, "summary_%s.csv" % algo)
    rows = []
    for strategy in strategies:
        for seed in seeds:
            out, _ = task_paths(algo, strategy, seed)
            rf = os.path.join(out, "result.json")
            if not os.path.exists(rf):
                continue
            with open(rf, encoding="utf-8") as f:
                rec = json.load(f)
            rows.append({
                "algo": algo.upper(), "mode": os.path.basename(os.path.dirname(out)), "seed": seed,
                "failed": rec.get("failed"), "iterations": rec.get("iterations"),
                "wall_s": rec.get("wall_s"), "message": str(rec.get("message", ""))[:120],
                "error": str(rec.get("error", ""))[:120],
            })
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["algo", "mode", "seed", "failed", "iterations",
                                          "wall_s", "message", "error"])
        w.writeheader()
        w.writerows(rows)
    return path, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--algo", required=True, choices=["a1", "a2", "a3"])
    ap.add_argument("--seeds", default="1-100")
    ap.add_argument("--strategies", default="0,2,3")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--size", type=int, default=0,
                    help="规模档：论文 A1=4/8、A2=10/20、A3=6/10；0=该算法最小档")
    ap.add_argument("--timeout", type=int, default=0)
    ap.add_argument("--a3link", default="0",
                    help="A3: 1=攻击机进入集群势场(论文语义), 0=上游原样(消融)")
    ap.add_argument("--maxit", type=int, default=0,
                    help="迭代/步数上限（论文判据①的超时阈值）；0=用被测程序默认值")
    ap.add_argument("--maxt", type=float, default=0,
                    help="A2 仿真时长上限(秒)，即论文判据①的 2×CTime；0=用上游 t_end")
    ap.add_argument("--collide", default="0",
                    help="A2 判据③机间碰撞开关：1=开启（上游 countMatrix 0.5m），0=关闭")
    ap.add_argument("--trace", default="0",
                    help="数据采集开关：1=每步写 trace/*.jsonl（回放+鲁棒度），0=不采集（默认）")
    args = ap.parse_args()

    global A3LINK, MAXIT, MAXT, COLLIDE, SIZE, TRACE
    SIZE = None
    if args.size:
        if args.size not in ALGO_SIZES[args.algo]:
            raise SystemExit("[sched] --size %d 不是 %s 的论文档位 %s"
                             % (args.size, args.algo, ALGO_SIZES[args.algo]))
        SIZE = args.size
    A3LINK = str(args.a3link)
    MAXIT = str(args.maxit)
    MAXT = str(args.maxt)
    COLLIDE = str(args.collide)
    TRACE = str(args.trace)

    if args.timeout:
        ALGO_CFG[args.algo]["timeout"] = args.timeout
    seeds = parse_seeds(args.seeds)
    strategies = [int(x) for x in args.strategies.split(",")]
    tasks = [(s, sd) for sd in seeds for s in strategies]
    print("[sched] algo=%s size=%d tasks=%d workers=%d timeout=%ds" %
          (args.algo, SIZE or ALGO_SIZES[args.algo][0], len(tasks), args.workers,
           ALGO_CFG[args.algo]["timeout"]))

    # [AI-MOD 2026-11-10] 每批开始前清理上一批（或被中断的上一轮）残留的 MATLAB -batch 实例。
    # 残留引擎会占住启动期锁，是 "Fatal Startup Error: File system inconsistency" 的直接来源。
    if args.algo != "a1":
        reap_stale_matlab()

    done = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(run_one, args.algo, s, sd): (s, sd) for s, sd in tasks}
        for fut in as_completed(futs):
            status, seed, strategy, wall, tail = fut.result()
            done += 1
            print("[%d/%d] %s %s seed=%d %.1fs %s %s" %
                  (done, len(tasks), args.algo, MODE_NAME[strategy], seed, wall, status,
                   "" if status in ("ok", "skip") else tail), flush=True)

    path, rows = summarize(args.algo, strategies, seeds)
    n = len(rows)
    print("[sched] finished %d tasks in %.1f min -> %s" % (n, (time.time() - t0) / 60, path))
    for strategy in strategies:
        sub = [r for r in rows if r["mode"] in (MODE_NAME[strategy],
                                                MODE_NAME[strategy] + "_link1")]
        if sub:
            fail = sum(1 for r in sub if r["failed"])
            print("  %s: n=%d failure=%.1f%%" % (MODE_NAME[strategy], len(sub),
                                                 100.0 * fail / len(sub)))


if __name__ == "__main__":
    main()
