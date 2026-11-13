# -*- coding: utf-8 -*-
"""[AI-MOD 2026-11-05] 汇总三算法的 result.json 并做同种子配对检验。

口径严格按论文 §IV-B：
  · Failure = 任务失败率（超时 / 撞障碍 / 机间碰撞 任一成立）
  · CTime   = 无攻击基线的平均任务完成时间
  · 同种子配对：基线与 SA/MA 使用同一 seed，用 McNemar 精确检验（二项精确检验）
输出 repro/runs/analysis.json，供报告直接引用。
"""
import json
import os
import math
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(HERE, "runs")
ALGOS = ["a1", "a2", "a3"]
MODES = ["na", "sa", "sa_link1", "ma", "ma_link1"]


def load(algo, mode):
    d = os.path.join(RUNS, algo, mode)
    out = {}
    if not os.path.isdir(d):
        return out
    for seed in os.listdir(d):
        f = os.path.join(d, seed, "result.json")
        if not os.path.isfile(f):
            continue
        try:
            with open(f, encoding="utf-8") as fh:
                rec = json.load(fh)
        except Exception:
            continue
        out[int(seed)] = rec
    return out


def binom_p(k, n):
    """McNemar 精确检验（双侧）: k = 不一致对中实验组失败、基线成功的数量, n = 不一致对总数"""
    if n == 0:
        return 1.0
    k = min(k, n - k)
    s = sum(math.comb(n, i) for i in range(0, k + 1))
    return min(1.0, 2.0 * s / (2 ** n))


def sim_time_of(rec):
    """A2/A3 直接给 sim_time；A1 只有 message 文本里的仿真结束时间，这里统一提取。"""
    v = rec.get("sim_time")
    if isinstance(v, (int, float)):
        return float(v)
    import re
    m = re.search(r"程序结束时间为:\s*([\d.]+)", str(rec.get("message", "")))
    return float(m.group(1)) if m else None


def a1_reason(rec):
    """[AI-MOD 2026-11-05] A1 的 result.json 只有 message 文本，按上游 recode_res 的措辞归类。

    上游 recode_res 的文案（"攻击成功"即任务失败）：撞墙 / 机间碰撞 / 没有到达目的地（超时）。
    批量调度器硬超时产生的记录只有 error=TASK_TIMEOUT，同样属于论文判据①。
    """
    if str(rec.get("error", "")) == "TASK_TIMEOUT":
        return "timeout"
    msg = str(rec.get("message", ""))
    if "碰撞到墙壁" in msg:
        return "wall"
    if "之间发生碰撞" in msg:
        return "collision"
    if "没有到达目的地" in msg:
        return "timeout"
    if "到达目标" in msg:
        return "ok"
    return "error"


def summarize(algo):
    res = {"algo": algo.upper(), "modes": {}}
    for mode in MODES:
        recs = load(algo, mode)
        if not recs:
            continue
        fails = sum(1 for r in recs.values() if r.get("failed"))
        walls = [r.get("wall_s") for r in recs.values() if isinstance(r.get("wall_s"), (int, float))]
        res["modes"][mode] = {
            "n": len(recs),
            "failure": round(100.0 * fails / len(recs), 2),
            "wall_median": round(sorted(walls)[len(walls) // 2], 2) if walls else None,
        }
        if algo == "a1":
            # [AI-MOD 2026-11-05] A1 的失败构成从 message 文本解析（撞墙/机间碰撞/超时/到达）。
            cnt = {}
            for r in recs.values():
                k = a1_reason(r)
                cnt[k] = cnt.get(k, 0) + 1
            res["modes"][mode]["reasons"] = cnt
            res["modes"][mode]["crashed"] = cnt.get("wall", 0) + cnt.get("collision", 0)
            res["modes"][mode]["timeout"] = cnt.get("timeout", 0)
            res["modes"][mode]["arrived"] = cnt.get("ok", 0)
            continue
        # 失败原因细分（A2/A3 的 result.json 自带布尔字段）
        crashed = sum(1 for r in recs.values() if r.get("crashed"))
        timeout = sum(1 for r in recs.values() if r.get("timeout")) + \
            sum(1 for r in recs.values() if str(r.get("error", "")) == "TASK_TIMEOUT")
        if crashed or timeout:
            res["modes"][mode]["crashed"] = crashed
            res["modes"][mode]["timeout"] = timeout
            res["modes"][mode]["arrived"] = sum(1 for r in recs.values() if r.get("arrived"))

    base = load(algo, "na")
    if algo == "a3":
        # [AI-MOD 2026-11-05] A3 的 result.json 只记录完成迭代步 goal_it（A3 配置 dt=0.1 s），
        # 论文 Table II 的 CTime 是"完成任务所需时间"，故按 goal_it × 0.1 s 折算。
        ctimes = [r["goal_it"] * 0.1 for r in base.values()
                  if not r.get("failed") and isinstance(r.get("goal_it"), (int, float))]
    else:
        ctimes = [sim_time_of(r) for r in base.values() if not r.get("failed")]
        ctimes = [c for c in ctimes if c is not None]
    if ctimes:
        res["ctime_median"] = round(sorted(ctimes)[len(ctimes) // 2], 2)
        res["ctime_n"] = len(ctimes)

    for mode in ["sa", "ma", "sa_link1", "ma_link1"]:
        recs = load(algo, mode)
        if not recs or not base:
            continue
        both = sorted(set(recs) & set(base))
        b01 = sum(1 for s in both if not base[s].get("failed") and recs[s].get("failed"))  # 基线成功→攻击失败
        b10 = sum(1 for s in both if base[s].get("failed") and not recs[s].get("failed"))  # 基线失败→攻击成功
        res.setdefault("mcnemar", {})[mode] = {
            "paired": len(both), "base_ok_atk_fail": b01, "base_fail_atk_ok": b10,
            "p": float("%.3g" % binom_p(b01, b01 + b10)),
        }
    return res


def main():
    out = [summarize(a) for a in ALGOS]
    path = os.path.join(RUNS, "analysis.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    print("[analyze] ->", path)


if __name__ == "__main__":
    main()
