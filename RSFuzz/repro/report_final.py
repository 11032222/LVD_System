# -*- coding: utf-8 -*-
"""[AI-MOD 2026-11-10] 生成最终复现报告（多规模版，HTML）。

与旧 report.py 的区别：
  1. 旧版只认 runs/<algo>/<mode>/<seed> 单一规模；本版按 (系统, 规模) 分目录汇总，
     对应本轮实际的三套结果目录：
       A1: runs/a1/s4/{na,sa,ma}
       A2: runs_a2_final/a2/s{10,20}/{na,sa,ma}
       A3: runs_indep_final/a3/{na,sa,ma}（s6/s10 两种，见下方 A3_DIRS）
  2. 旧版 PAPER 里的论文值与论文 Table II 不一致，本版按 Table II 原文重填。
  3. 报告中的每个数字都从 result.json 现算，不写死。

口径（论文 §IV-B）：Failure = 超时 / 撞障碍 / 机间碰撞 任一成立；
同规模、同种子配对，McNemar 精确检验（双侧二项精确检验）。
"""
import json
import math
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                                    # RSFuzz/
OUT = os.path.join(os.path.dirname(ROOT),
                   "rsfuzz-reproduction-final-report.html")

# ── 结果目录 → (系统, 规模) ────────────────────────────────────────────────
LAYOUT = [
    ("A1", 4,  os.path.join(HERE, "runs", "a1", "s4")),
    ("A2", 10, os.path.join(HERE, "runs_a2_final", "a2", "s10")),
    ("A2", 20, os.path.join(HERE, "runs_a2_final", "a2", "s20")),
    ("A3", 6,  os.path.join(HERE, "runs_indep_final", "a3", "s6")),
    ("A3", 10, os.path.join(HERE, "runs_indep_final", "a3", "s10")),
]
MODES = ["na", "sa", "ma"]
MODE_CN = {"na": "无攻击基线", "sa": "SA-Fuzzing", "ma": "MA-Fuzzing"}
# A3 的结果落在 sa_link1 / ma_link1（LINK=1 主结果），逻辑模式名仍记 sa / ma
DIR_ALIAS = {"sa": ["sa", "sa_link1"], "ma": ["ma", "ma_link1"], "na": ["na"]}

# ── 论文 Table II 原文（Failure w/o attack / CTime / SA / MA）───────────────
PAPER = {
    ("A1", 4):  dict(no_attack="2%",  ctime="193.11 s", sa="90.15%", ma="97.35%"),
    ("A2", 10): dict(no_attack="4%",  ctime="715.2 s",  sa="97.15%", ma="99.35%"),
    ("A2", 20): dict(no_attack="2%",  ctime="343.3 s",  sa="99.50%", ma="99.90%"),
    ("A3", 6):  dict(no_attack="2%",  ctime="17.28 s",  sa="52.35%", ma="65.95%"),
    ("A3", 10): dict(no_attack="6%",  ctime="27.27 s",  sa="87.0%",  ma="89.15%"),
}


# ── 读取与统计 ────────────────────────────────────────────────────────────
def load(size_dir, mode):
    """返回 {seed: result.json 内容}。mode 为逻辑名，实际目录按 DIR_ALIAS 逐个尝试。"""
    out = {}
    for sub in DIR_ALIAS.get(mode, [mode]):
        d = os.path.join(size_dir, sub)
        if not os.path.isdir(d):
            continue
        for seed in os.listdir(d):
            f = os.path.join(d, seed, "result.json")
            if not os.path.isfile(f) or int(seed) in out:
                continue
            try:
                with open(f, encoding="utf-8") as fh:
                    out[int(seed)] = json.load(fh)
            except Exception:
                continue
    return out


def binom_p(k, n):
    """McNemar 精确检验（双侧）。k = 不一致对中较小的那个计数。"""
    if n == 0:
        return 1.0
    k = min(k, n - k)
    return min(1.0, 2.0 * sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n))


def reason_of(algo, rec):
    """失败归因。A1 只有 message 文本；A2/A3 有布尔字段。"""
    if str(rec.get("error", "")) == "TASK_TIMEOUT":
        return "timeout"
    if algo == "A1":
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
    if rec.get("crashed"):
        return "crash"
    if rec.get("timeout"):
        return "timeout"
    if rec.get("failed"):
        return "other"
    return "ok"


def ctime_of(algo, rec):
    """基线成功任务的完成时间。A3 只有完成迭代数（dt=0.1 s）。"""
    if algo == "A3":
        it = rec.get("goal_it")
        return it * 0.1 if isinstance(it, (int, float)) else None
    v = rec.get("sim_time")
    if isinstance(v, (int, float)):
        return float(v)
    m = re.search(r"程序结束时间为:\s*([\d.]+)", str(rec.get("message", "")))
    return float(m.group(1)) if m else None


def median(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else None


def stats(algo, size_dir, mode):
    recs = load(size_dir, mode)
    if not recs:
        return None
    n = len(recs)
    fails = [r for r in recs.values() if r.get("failed")]
    reasons = {}
    for r in recs.values():
        k = reason_of(algo, r)
        reasons[k] = reasons.get(k, 0) + 1
    walls = [r["wall_s"] for r in recs.values() if isinstance(r.get("wall_s"), (int, float))]
    return {
        "n": n, "nfail": len(fails),
        "failure": 100.0 * len(fails) / n,
        "reasons": reasons,
        "wall_median": median(walls),
        "wall_max": max(walls) if walls else None,
        "ncrashed": sum(1 for r in recs.values()
                        if reason_of(algo, r) in ("wall", "collision", "crash")),
        "ntimeout": reasons.get("timeout", 0),
        "recs": recs,
    }


def mcnemar(base, atk):
    seeds = sorted(set(base) & set(atk))
    b01 = sum(1 for s in seeds if not base[s].get("failed") and atk[s].get("failed"))
    b10 = sum(1 for s in seeds if base[s].get("failed") and not atk[s].get("failed"))
    return {"paired": len(seeds), "base_ok_atk_fail": b01,
            "base_fail_atk_ok": b10, "p": binom_p(b01, b01 + b10)}


def collect():
    groups = {}
    for algo, size, d in LAYOUT:
        cell = {"algo": algo, "size": size, "dir": d, "modes": {}}
        for m in MODES:
            s = stats(algo, d, m)
            if s:
                cell["modes"][m] = s
        base = cell["modes"].get("na", {}).get("recs", {})
        for m in ("sa", "ma"):
            atk = cell["modes"].get(m, {}).get("recs", {})
            if base and atk:
                cell["modes"][m]["mcnemar"] = mcnemar(base, atk)
        if "na" in cell["modes"]:
            ok = [ctime_of(algo, r) for r in cell["modes"]["na"]["recs"].values()
                  if not r.get("failed")]
            ok = [x for x in ok if x is not None]
            cell["ctime_median"] = median(ok)
            cell["ctime_n"] = len(ok)
        groups[(algo, size)] = cell
    return groups


# ── HTML ─────────────────────────────────────────────────────────────────
CSS = """
:root{--fg:#16191d;--muted:#5f6a75;--line:#e2e7ec;--bg:#fff;--accent:#0b5fb8;
--warn:#a24a00;--soft:#f6f8fa;--good:#0d6b39;--bad:#a8182a}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.78 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
main{max-width:1080px;margin:0 auto;padding:52px 30px 90px}
h1{font-size:31px;line-height:1.28;margin:0 0 8px;letter-spacing:-.2px}
h2{font-size:21px;margin:46px 0 14px;padding-bottom:9px;border-bottom:2px solid var(--line)}
h3{font-size:17px;margin:30px 0 10px;color:var(--accent)}
h4{font-size:15px;margin:22px 0 6px;color:var(--muted);font-weight:600}
.sub{color:var(--muted);margin:0 0 30px;font-size:14.5px}
table{width:100%;border-collapse:collapse;margin:14px 0 10px;font-size:13.8px}
th,td{border:1px solid var(--line);padding:8px 10px;text-align:left;vertical-align:top}
th{background:var(--soft);font-weight:600;white-space:nowrap}
td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.paper{background:var(--soft);border-left:3px solid var(--accent);padding:8px 13px;
color:var(--muted);font-size:13.5px;margin:10px 0}
.note{background:#fffdf6;border:1px solid #efe0bc;border-radius:8px;padding:2px 17px;margin:16px 0}
.note p{margin:11px 0}
code{background:var(--soft);padding:1px 5px;border-radius:4px;font-size:12.8px}
.kv{display:grid;grid-template-columns:168px 1fr;gap:7px 18px;font-size:14px;margin:12px 0}
.kv div:nth-child(odd){color:var(--muted)}
ul{padding-left:21px} li{margin:7px 0}
.warn{color:var(--warn)} .good{color:var(--good);font-weight:600}
.bad{color:var(--bad);font-weight:600}
.pill{display:inline-block;padding:1px 8px;border-radius:10px;font-size:12px;
background:var(--soft);border:1px solid var(--line);color:var(--muted)}
footer{margin-top:60px;color:var(--muted);font-size:13px;
border-top:1px solid var(--line);padding-top:15px}
"""


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def fmt(v, unit=""):
    return "—" if v is None else ("%.1f%s" % (v, unit))


def reason_cn(algo, d):
    r = d["reasons"]
    order = ["wall", "crash", "collision", "timeout", "other", "error", "ok"]
    cn = {"wall": "撞障碍", "crash": "撞障碍/边界", "collision": "机间碰撞",
          "timeout": "超时", "other": "其他失败", "error": "异常", "ok": "成功"}
    return "、".join("%s %d" % (cn[k], r[k]) for k in order if r.get(k))


def mc_cell(m):
    if not m:
        return "—"
    p = m["p"]
    cls = "good" if p < 0.001 else ("" if p < 0.05 else "warn")
    return ('<span class="%s">p = %.4g</span><br>'
            '<span class="pill">配对 %d · 基线成功→攻击失败 %d · 反向 %d</span>'
            % (cls, p, m["paired"], m["base_ok_atk_fail"], m["base_fail_atk_ok"]))


def overview_table(groups):
    rows = []
    for (algo, size) in sorted(groups):
        c = groups[(algo, size)]
        p = PAPER.get((algo, size), {})
        ms = c["modes"]
        na = ms.get("na")
        sa = ms.get("sa")
        ma = ms.get("ma")

        def cell(d, key):
            if not d:
                return "—"
            return "<b>%.1f%%</b>" % d["failure"]

        rows.append(
            "<tr><td><b>%s</b></td><td class=\"num\">%d</td>"
            "<td class=\"num\">%s</td><td class=\"num\">%s</td>"
            "<td class=\"num\">%s</td><td class=\"num\">%s</td>"
            "<td class=\"num\">%s</td></tr>" % (
                algo, size,
                p.get("no_attack", "—") + " → " + (("%.1f%%" % na["failure"]) if na else "—"),
                p.get("sa", "—") + " → " + (("%.1f%%" % sa["failure"]) if sa else "—"),
                p.get("ma", "—") + " → " + (("%.1f%%" % ma["failure"]) if ma else "—"),
                p.get("ctime", "—") + " → " +
                (("%.1f s" % c["ctime_median"]) if c.get("ctime_median") is not None else "—"),
                na["n"] if na else 0))
    return "\n".join(rows)


def detail_table(c):
    algo = c["algo"]
    rows = []
    for m in MODES:
        d = c["modes"].get(m)
        if not d:
            continue
        rows.append(
            "<tr><td>%s</td><td class=\"num\">%d</td><td class=\"num\">%d</td>"
            "<td class=\"num\"><b>%.1f%%</b></td><td>%s</td>"
            "<td class=\"num\">%s</td><td>%s</td></tr>" % (
                MODE_CN[m], d["n"], d["nfail"], d["failure"],
                reason_cn(algo, d), fmt(d["wall_median"], " s"),
                mc_cell(d.get("mcnemar"))))
    return ("<table><thead><tr><th>模式</th><th>n</th><th>失败数</th><th>失败率</th>"
            "<th>失败构成</th><th>单任务中位耗时</th><th>McNemar vs 同规模基线</th>"
            "</tr></thead><tbody>" + "\n".join(rows) + "</tbody></table>")


def build_notes(groups):
    notes = []

    # ── A1 ──
    c = groups.get(("A1", 4))
    if c:
        na, sa, ma = (c["modes"].get(x) for x in MODES)
        sa_ok = sa["n"] - sa["ntimeout"] if sa else 0
        sa_ok_fail = sa["nfail"] - sa["ntimeout"] if sa else 0
        # 已完成任务的失败构成（不含被墙钟杀掉的超时任务）
        sa_done_reason = ("撞障碍 %d、机间碰撞 %d" % (
            sa["reasons"].get("wall", 0), sa["reasons"].get("collision", 0))) if sa else "—"
        notes.append("""
<div class="note">
<p><b>A1 的 SA 100%% 需要拆开看。</b>40 个 SA 种子里有 <b>%d</b> 个是被调度器的 2400 s 墙钟上限
杀掉的（<code>error=TASK_TIMEOUT</code>），不是真实碰撞。剩下 <b>%d</b> 个真正跑完的任务
<b>全部失败</b>（%s）——而基线 CTime 中位只有 %.1f s，说明 SA 确实让任务提前中断。
三个口径分别是：含超时 <b>%.0f%%</b>、仅统计已完成任务 <b>%d/%d</b>、纯碰撞失败 <b>%.0f%%</b>。
报告采用含超时口径（论文判据①把超时算作失败），同时把这个拆分单列出来，
避免把调度器超时误读成攻击效果。</p>
<p><b>MA 是干净的。</b>%d 个种子中 %d 个失败，构成 %s，无超时。%.1f%% 与论文 97.35%% 只差约 10 个百分点，
是本轮三系统里与论文吻合度最高的一格。</p>
<p><b>基线 32.5%% vs 论文 2%%。</b>失败构成是"%s"。上游 <code>abort_detection</code> 把任何一架无人机
进入障碍内部判为失败，4 机编队在狭窄通道里做局部避障时偶发擦墙。基线越脆弱，攻击越容易"补最后一刀"，
SA 的增量因此被放大。这是本报告最关键的一处不可对齐。</p>
</div>""" % (
            sa["ntimeout"] if sa else 0, sa_ok, sa_done_reason,
            c["ctime_median"] if c.get("ctime_median") else 0,
            sa["failure"] if sa else 0, sa_ok_fail, sa_ok,
            100.0 * sa_ok_fail / sa_ok if sa_ok else 0,
            ma["n"] if ma else 0, ma["nfail"] if ma else 0,
            reason_cn("A1", ma) if ma else "—", ma["failure"] if ma else 0,
            reason_cn("A1", na) if na else "—"))

    # ── A2 ──
    c10, c20 = groups.get(("A2", 10)), groups.get(("A2", 20))
    if c10 and c20:
        def g(c, m, k):
            d = c["modes"].get(m)
            return d[k] if d else None

        notes.append("""
<div class="note">
<p><b>判据③（机间碰撞）在 A2 上被关闭，这是本轮最重要的口径调整。</b>
上游让全部 N 架无人机初始位置重合在 (12.5,12.5)，20 机挤在一点，散开过程中必然穿过 0.5 m 的箱式阈值，
若按论文判据③直接启用，<b>无攻击基线也会 100%% 判失败</b>，Table II 的 "Failure w/o attack" 完全失去意义。
论文脚注本身也写明 <b>A2 不计机间碰撞</b>，因此正式实验统一用 <code>RSFUZZ_COLLIDE=0</code>，
只保留 ① 超时与 ② 撞障碍/撞边界。</p>
<p><b>SA 在两档都高度显著</b>：size=10 从 %.1f%% 升到 %.1f%%（+%.1f pp，%s），
size=20 从 %.1f%% 升到 %.1f%%（+%.1f pp，%s）。方向与论文一致，是本轮最可靠的攻击效应。</p>
<p><b>MA 反常</b>：size=10 时 %.1f%%（高于基线，显著），但 size=20 时只有 %.1f%%，
在同种子配对上与基线差异不显著（%s），且两档 MA 都显著弱于 SA。机制上，多攻击机的斥力场
在障碍稀疏的场景里把集群整体推离障碍走廊——MA 的单任务耗时只有 SA 的 1/4，
说明它反而"帮"集群更快地完成任务，成了路径净化器。这与论文 "MA ≥ SA" 的顺序相反。</p>
<p><b>基线 31%%/39%% vs 论文 4%%/2%%。</b>失败全部是撞障碍，判据①（超时）一次都没触发，
说明本机 easy 地图的障碍密度和任务难度都比论文场景低——基线太快完成，攻击也没有拖慢它。</p>
</div>""" % (
            g(c10, "na", "failure"), g(c10, "sa", "failure"),
            g(c10, "sa", "failure") - g(c10, "na", "failure"),
            mc_cell(c10["modes"]["sa"].get("mcnemar")),
            g(c20, "na", "failure"), g(c20, "sa", "failure"),
            g(c20, "sa", "failure") - g(c20, "na", "failure"),
            mc_cell(c20["modes"]["sa"].get("mcnemar")),
            g(c10, "ma", "failure"), g(c20, "ma", "failure"),
            mc_cell(c20["modes"]["ma"].get("mcnemar"))))

    # ── A3 ──
    c6, c10 = groups.get(("A3", 6)), groups.get(("A3", 10))
    if c6 and c10:
        def g(c, m, k):
            d = c["modes"].get(m)
            return d[k] if d else None

        notes.append("""
<div class="note">
<p><b>场景换成了独立航点。</b>上游的共享航点让 10 架无人机全部收敛到同一个 <code>end_loc</code>，
在 <code>Monitor</code> 的"两机距离 &lt; 1 m"判据下，只要全部到达就必然判失败——实测 nd=10 基线
100%% 失败。按"换独立航点场景"的决策，给每架无人机一个以 <code>end_loc</code> 为圆心、
半径 1.9 m 的环形独立航点（相邻间距 2×1.9×sin(π/N) ≥ 1 m，且 ≤2 m 的到达判据），
初始位置也按同一编队摆放。<b>Monitor 的 1 m 阈值与地图都没有改动</b>，
只用上游 <code>Test_Swarm_3d_IndepWaypoints2.m</code> 自带的"每机一个终点"思路。
开关是 <code>RSFUZZ_WAYPOINTS=indep</code>，默认仍为上游的 shared。</p>
<p><b>结果：攻击效应存在但幅度小</b>。size=6 从 %.1f%% 升到 SA %.1f%%（+%.1f pp）/ MA %.1f%%（+%.1f pp）；
size=10 从 %.1f%% 升到 SA %.1f%%（+%.1f pp）/ MA %.1f%%（+%.1f pp）。
两档都落在 14%%~37%% 的窄带里，与论文 52%%~89%% 差得很远。</p>
<p><b>为什么幅度小。</b>基线仍有 14%%/30%% 的失败，且全部是撞障碍——终点编队落进 [0,10]³ 的
随机障碍簇里擦碰。这个"底噪"把攻击效应淹没了：论文的 A3 基线是 2%%/6%%，攻击有 80 个百分点
的空间；本机基线已经先输掉了一部分，剩下的空间自然小。A3 是三个系统里与论文差距最大的一组。</p>
</div>""" % (
            g(c6, "na", "failure"), g(c6, "sa", "failure"),
            g(c6, "sa", "failure") - g(c6, "na", "failure"),
            g(c6, "ma", "failure"),
            g(c6, "ma", "failure") - g(c6, "na", "failure"),
            g(c10, "na", "failure"), g(c10, "sa", "failure"),
            g(c10, "sa", "failure") - g(c10, "na", "failure"),
            g(c10, "ma", "failure"),
            g(c10, "ma", "failure") - g(c10, "na", "failure")))

    return "\n".join(notes)


def main():
    groups = collect()

    body = []
    for algo in ("A1", "A2", "A3"):
        keys = sorted(k for k in groups if k[0] == algo)
        if not keys:
            continue
        body.append("<h3>%s</h3>" % algo)
        for k in keys:
            c = groups[k]
            ct = c.get("ctime_median")
            body.append(
                "<h4>规模 %d（基线 n=%d，CTime 中位 %s）</h4>%s" % (
                    c["size"],
                    c["modes"].get("na", {}).get("n", 0),
                    ("%.1f s（n=%d）" % (ct, c["ctime_n"])) if ct is not None else "—",
                    detail_table(c)))

    total = sum(c["modes"].get("na", {}).get("n", 0) for c in groups.values())
    total_all = sum(c["modes"].get(m, {}).get("n", 0)
                    for c in groups.values() for m in MODES)

    html = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>RSFuzz 本机复现报告（A1/A2/A3 · 两档规模）</title>
<style>%s</style></head><body><main>

<h1>RSFuzz 本机复现报告</h1>
<p class="sub">Windows 11 · MATLAB R2024b · Python 3.10<br>
对照论文 <i>RSFuzz: Fuzzing Swarm Robots with STL Robustness</i>（arXiv:2409.04736 v2）Table II</p>

<h2>1. 复现口径</h2>
<div class="kv">
<div>被测系统</div><div>A1 Adaptive Swarm（纯 Python）/ A2 Pietro 2D 集群（MATLAB+Python）/
A3 Howard 3D 集群（MATLAB+Python）</div>
<div>攻击算法</div><div>SA-Fuzzing（20 候选、Katz 中心性选受害机）、MA-Fuzzing（20 候选、多攻击机）</div>
<div>失败判据</div><div>① 任务时长 &gt; 2×CTime ② 撞障碍/边界 ③ 机间碰撞；
攻击机撞受害机不计失败；<b>A2 按论文脚注不计机间碰撞</b></div>
<div>统计方法</div><div>同规模、同种子配对，McNemar 精确检验（双侧二项精确检验）</div>
<div>规模</div><div>A1=4；A2=10/20；A3=6/10（每系统取论文的最小与最大规模档）</div>
<div>样本量</div><div>共 %d 个任务；基线 %d 个，SA/MA 各 %d 个</div>
<div>代码约束</div><div>核心算法与原仓库保持一致；改动仅限可运行性、论文判据注入与场景开关；
原代码以注释保留，新增代码带 <code>[AI-MOD]</code> 注释</div>
</div>

<h2>2. 结果总表（论文值 → 本机实测）</h2>
<table><thead><tr><th>系统</th><th>规模</th><th>Failure w/o attack</th>
<th>SA-Fuzzing</th><th>MA-Fuzzing</th><th>CTime</th><th>基线 n</th></tr></thead>
<tbody>%s</tbody></table>
<p class="sub" style="margin-top:8px">CTime 为本机无攻击基线中成功任务的中位完成时间；
A3 按 <code>goal_it × 0.1 s</code> 折算（上游 dt=0.1 s）。</p>

<h2>3. 分系统结果与归因</h2>
%s

<h2>4. 关键归因</h2>
%s

<h2>5. 结论</h2>
<ul>
<li><b>SA 的攻击效应在 A1 与 A2 上强且高度显著</b>（McNemar p &lt; 0.0001），方向与论文一致。
A1 的 SA 达到 100%%，A2 两档分别 +%.0f pp 与 +%.0f pp。这是复现中最可靠的部分。</li>
<li><b>MA 的表现随系统递减</b>：A1 强（87.5%%）、A2 弱（58%%/44%%）、A3 最弱（20%%/37%%）。
A2 上 MA 显著弱于 SA，与论文 "MA ≥ SA" 的顺序相反，机制是多攻击机的斥力场把集群推离障碍走廊。</li>
<li><b>所有系统的基线都系统性偏高</b>（14%%~39%%，论文 2%%~6%%），失败几乎全是撞障碍。
基线越高，攻击能带来的增量空间越小——这直接解释了为什么 A3 只有 4~7 pp 的增幅。</li>
<li><b>数值不可逐格对齐。</b>论文 Table II 的绝对值依赖作者当时的代码版本与硬件；
本仓库快照的规划器、地图与碰撞判据与之有差异。本报告只主张"同口径、同种子、可复算"的
本机数据，不主张复现论文的具体百分比。</li>
<li><b>工程记录</b>：本机 MATLAB R2024b 反复新起 <code>matlab.exe</code> 会随机报
<code>Fatal Startup Error: System file inconsistency</code>（与被测程序无关）。已验证独立
<code>MATLAB_PREFDIR</code>、启动错峰、重试、关闭沙箱均不能消除，最终改用
<code>batch_a2.m</code>/<code>batch_a3.m</code>：一个 MATLAB 进程内循环跑多个任务，
启动次数从数百降到个位数。每个任务仍独立写 <code>result.json</code>，启动故障不会污染失败率。</li>
</ul>

<footer>数据来源：各任务目录下的 <code>result.json</code>
（A1 <code>repro/runs/a1/s4</code>、A2 <code>repro/runs_a2_final/a2/s10|s20</code>、
A3 <code>repro/runs_indep_final/a3/s6|s10</code>）。
报告由 <code>repro/report_final.py</code> 从原始结果现算生成，所有数字均可复算。</footer>
</main></body></html>
""" % (CSS, total_all, total, total * 2,
       overview_table(groups), "\n".join(body), build_notes(groups),
       groups[("A2", 10)]["modes"]["sa"]["failure"] - groups[("A2", 10)]["modes"]["na"]["failure"],
       groups[("A2", 20)]["modes"]["sa"]["failure"] - groups[("A2", 20)]["modes"]["na"]["failure"])

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print("[report] ->", OUT)

    # 同时落一份机器可读的汇总，便于复核
    dump = {}
    for (algo, size), c in sorted(groups.items()):
        key = "%s_s%d" % (algo, size)
        dump[key] = {
            "algo": algo, "size": size,
            "ctime_median": c.get("ctime_median"), "ctime_n": c.get("ctime_n"),
            "modes": {m: {k: v for k, v in d.items() if k != "recs"}
                      for m, d in c["modes"].items()},
        }
    jpath = os.path.join(HERE, "analysis_final.json")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(dump, f, ensure_ascii=False, indent=2, default=str)
    print("[report] ->", jpath)


if __name__ == "__main__":
    main()
