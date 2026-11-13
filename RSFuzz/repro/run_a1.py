# -*- coding: utf-8 -*-
"""[AI-MOD 2026-11-05] A1 (Adaptive Swarm) 单任务运行器。

论文依据：Table II 的每种 (方法, 规模) 需在“相同随机种子”下对比“无攻击基线”与
“SA/MA 攻击”结果（§IV-B Failure 与 Failure w/o attack 两列），因此每个任务必须
单独进程、单独工作目录、固定种子，并把结果写成机器可读的 JSON。

用法:
  python run_a1.py --strategy 2 --seed 1001 --tag a1_SA_1001 --work <工作目录> --out <输出目录>

strategy: 0=无攻击基线, 2=SA-Fuzzing, 3=MA-Fuzzing（1=仓库自带随机攻击，本文未用）
"""
import argparse
import json
import os
import random
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
# 注意：仓库目录名带空格 —— "Adaptive Swarm/adaptive_swarm/scripts/layered_planner"
LP = os.path.join(ROOT, "Adaptive Swarm", "adaptive_swarm", "scripts", "layered_planner")


def parse_result(res_file):
    """从 fuzz.recode_res 写出的 res.txt 中解析失败判据。

    论文 §IV-B 失败定义：①超时 ②撞障碍 ③机间碰撞。
    recode_res 中“攻击成功”即任务失败（撞墙/互撞/超时），"攻击失败" 即任务成功。
    """
    if not os.path.exists(res_file):
        return None, None
    with open(res_file, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read().strip()
    if not text:
        return None, None
    failed = "攻击成功" in text
    return failed, text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategy", type=int, required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--tag", type=str, required=True)
    ap.add_argument("--work", type=str, required=True)
    ap.add_argument("--out", type=str, required=True)
    ap.add_argument("--robots", type=int, default=4)  # 论文 A1 默认规模 4
    args = ap.parse_args()
    # 任务会 chdir 到独立工作目录，这里先把输出/工作目录转成绝对路径
    args.work = os.path.abspath(args.work)
    args.out = os.path.abspath(args.out)

    os.makedirs(args.out, exist_ok=True)
    os.makedirs(os.path.join(args.work, "data_collection", "attack_res"), exist_ok=True)
    os.chdir(args.work)

    os.environ.setdefault("MPLBACKEND", "Agg")
    # [AI-MOD] 批量并发时限制 BLAS/OpenMP 线程，避免 8~12 个进程互相抢占导致 6 倍减速
    for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
              "NUMEXPR_NUM_THREADS"):
        os.environ.setdefault(k, "1")
    import matplotlib
    matplotlib.use("Agg")

    for p in (ROOT, LP, os.path.join(ROOT, "tool"), HERE):
        if p not in sys.path:
            sys.path.insert(0, p)

    # 固定全部随机源，保证“同种子配对”成立（论文要求基线/攻击可逐一配对）
    random.seed(args.seed)
    try:
        import numpy as np
        np.random.seed(args.seed)
    except Exception:
        pass

    import fuzz as fz

    rec = {
        "algo": "A1", "strategy": args.strategy, "seed": args.seed,
        "tag": args.tag, "robots": args.robots, "failed": None,
        "message": "", "iterations": None, "wall_s": None, "error": "",
    }
    t0 = time.time()
    att = None
    try:
        att = fz.attack(attack_strategy=args.strategy)
        # 减量与隔离：关闭全部可视化（论文 CTime 含绘图，本机统一不含绘图，仅比较失败率）
        att.params.visualize = 0
        att.params.animate_rrt = 0
        att.params.postprocessing = 0
        att.params.savedata = 0
        att.params.num_robots = args.robots
        att.is_show_attack_point = False
        att.is_rebuild_attack_path = False
        att.is_show_rob_pic = False
        # [AI-MOD 2026-11-12] 数据采集：RSFUZZ_TRACE=1 时包装四个攻击策略方法，
        # 每轮写 trace/frame.jsonl 与 iter.jsonl（不改 fuzz.py，关闭时零开销）。
        try:
            import trace_a1
            trace_a1.install(att, args.out)
        except Exception as _e:          # 采集只是旁路数据，失败也要让仿真照常跑
            print("[trace] 采集未启用: %r" % (_e,), file=sys.stderr)
        att.start()
        rec["iterations"] = int(getattr(att, "time", -1))
        failed, text = parse_result(att.res_to_save_file_path)
        rec["failed"] = bool(failed)
        rec["message"] = (text or "")[:300]
        # 把本次任务的轨迹/攻击点文件搬到统一输出目录，便于复核
        src = att.attack_floder_path
        if os.path.isdir(src):
            dst = os.path.join(args.out, "raw")
            os.makedirs(dst, exist_ok=True)
            for name in os.listdir(src):
                try:
                    os.replace(os.path.join(src, name), os.path.join(dst, name))
                except Exception:
                    pass
    except Exception:
        rec["error"] = traceback.format_exc()[-1500:]
    rec["wall_s"] = round(time.time() - t0, 2)
    if rec["failed"] is None:
        rec["failed"] = True  # 异常/无结果按失败处理，并在 error 字段中标明

    with open(os.path.join(args.out, "result.json"), "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: rec[k] for k in ("tag", "failed", "iterations", "wall_s", "error")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
