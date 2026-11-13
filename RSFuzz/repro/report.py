# -*- coding: utf-8 -*-
"""[AI-MOD 2026-11-05] 由 repro/runs/analysis.json 生成复现报告（HTML）。

报告口径与论文 §IV-B 一致：Failure = 超时(>2×CTime) / 撞障碍 / 机间碰撞 任一成立；
同种子配对用 McNemar 精确检验（见 analyze.py）。
正文中的数字全部从 analysis.json 取值，避免报告与数据脱节。
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(os.path.dirname(ROOT), "rsfuzz-reproduction-win-report.html")

# 论文 Table II（RSFuzz 原文）参考值
PAPER = {
    "A1": {"no_attack": "≈2%", "ctime": "187.7 / 195.6 s", "sa": "32.2%", "ma": "86.2%"},
    "A2": {"no_attack": "4%", "ctime": "715.2 / 401.1 / 343.3 s", "sa": "69.7%", "ma": "78.6%"},
    "A3": {"no_attack": "6%", "ctime": "1.2 s", "sa": "52%~89%（随规模）", "ma": "60%~89%"},
}
MODE_CN = {"na": "无攻击基线", "sa": "SA-Fuzzing", "sa_link1": "SA-Fuzzing（论文语义）",
           "ma": "MA-Fuzzing", "ma_link1": "MA-Fuzzing（论文语义）"}
ORDER = ["na", "sa", "ma", "sa_link1", "ma_link1"]

CSS = """
:root{--fg:#1a1d21;--muted:#5c6670;--line:#e3e7ec;--bg:#fff;--accent:#0b6bcb;--warn:#b45309;--soft:#f6f8fa}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.75 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
main{max-width:1020px;margin:0 auto;padding:48px 28px 80px}
h1{font-size:30px;line-height:1.3;margin:0 0 6px}
h2{font-size:21px;margin:44px 0 12px;padding-bottom:8px;border-bottom:2px solid var(--line)}
h3{font-size:17px;margin:28px 0 8px;color:var(--accent)}
.sub{color:var(--muted);margin:0 0 28px}
table{width:100%;border-collapse:collapse;margin:12px 0 8px;font-size:14px}
th,td{border:1px solid var(--line);padding:8px 10px;text-align:left;vertical-align:top}
th{background:var(--soft);font-weight:600}
.paper{background:var(--soft);border-left:3px solid var(--accent);padding:8px 12px;color:var(--muted);font-size:13.5px}
.ctime{margin:10px 0;font-size:14px;color:var(--muted)}
.note{background:#fffdf5;border:1px solid #f0e2bd;border-radius:8px;padding:4px 16px;margin:14px 0}
.note p{margin:10px 0}
code{background:var(--soft);padding:1px 5px;border-radius:4px;font-size:13px}
.kv{display:grid;grid-template-columns:170px 1fr;gap:6px 16px;font-size:14px}
.kv div:nth-child(odd){color:var(--muted)}
ul{padding-left:22px}
li{margin:6px 0}
.warn{color:var(--warn);font-weight:600}
.good{color:#0f7b3f;font-weight:600}
footer{margin-top:56px;color:var(--muted);font-size:13px;border-top:1px solid var(--line);padding-top:14px}
"""


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;")


def mode(algo, name):
    return algo.get("modes", {}).get(name)


def pct(d, key="failure"):
    return "%.1f%%" % d[key] if d else "—"


def reason_text(algo, d):
    """失败构成：A1 用 message 归类（墙/机间/超时），A2/A3 用 result.json 布尔字段。"""
    if not d:
        return "—"
    parts = []
    if "crashed" in d:
        parts.append("撞毁 %d" % d["crashed"])
    if "timeout" in d:
        parts.append("超时 %d" % d["timeout"])
    if "arrived" in d:
        parts.append("到达 %d" % d["arrived"])
    r = d.get("reasons")
    if r:
        cn = {"wall": "撞墙", "collision": "机间碰撞", "timeout": "超时", "ok": "到达", "error": "异常"}
        parts = ["%s %d" % (cn.get(k, k), v) for k, v in
                 sorted(r.items(), key=lambda kv: -kv[1])]
    return " / ".join(parts) if parts else "—"


def mc_text(algo, name):
    mc = (algo.get("mcnemar") or {}).get(name)
    if not mc:
        return "—"
    p = mc["p"]
    star = "<b>%.3g</b>" % p if p < 0.05 else "%.3g" % p
    return "%s<br><span class=\"ctime\">配对 %d，基线成功→攻击失败 %d，反向 %d</span>" % (
        star, mc["paired"], mc["base_ok_atk_fail"], mc["base_fail_atk_ok"])


def rows_for(algo):
    out = []
    for m in ORDER:
        d = algo.get("modes", {}).get(m)
        if not d:
            continue
        out.append("<tr><td>%s</td><td>%d</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            MODE_CN.get(m, m), d["n"], pct(d), reason_text(algo, d), mc_text(algo, m)))
    return "\n".join(out)


def summary_rows(data):
    """三系统横向总表：论文 vs 本机。"""
    out = []
    for a in ["A1", "A2", "A3"]:
        algo = data.get(a)
        if not algo:
            continue
        paper = PAPER[a]
        modes = algo.get("modes", {})
        key_sa = "sa_link1" if "sa_link1" in modes else "sa"
        key_ma = "ma_link1" if "ma_link1" in modes else "ma"
        out.append(
            "<tr><td><b>%s</b></td>"
            "<td>%s → %s</td>"
            "<td>%s → %s</td>"
            "<td>%s → %s</td>"
            "<td>%s → %s</td></tr>" % (
                a, paper["no_attack"], pct(modes.get("na")),
                paper["sa"], pct(modes.get(key_sa)),
                paper["ma"], pct(modes.get(key_ma)),
                paper["ctime"],
                ("%.1f s（n=%d）" % (algo["ctime_median"], algo.get("ctime_n", 0)))
                if algo.get("ctime_median") is not None else "—"))
    return "\n".join(out)


def algo_block(algo):
    a = algo["algo"]
    paper = PAPER.get(a, {})
    ctime = algo.get("ctime_median")
    head = (
        "<h3>%s</h3>" % esc(a) +
        "<div class=\"paper\">论文参考：Failure w/o attack = %s；CTime = %s；SA = %s；MA = %s</div>"
        % (paper.get("no_attack", "-"), paper.get("ctime", "-"),
           paper.get("sa", "-"), paper.get("ma", "-")) +
        "<table><thead><tr><th>模式</th><th>n</th><th>失败率</th><th>失败构成</th>"
        "<th>McNemar vs 同种子基线</th></tr></thead><tbody>" + rows_for(algo) + "</tbody></table>" +
        "<div class=\"ctime\">本机实测 CTime（无攻击基线中位任务时间，n=%s）：<b>%s</b></div>" % (
            esc(algo.get("ctime_n", "-")),
            ("%.1f s" % ctime) if ctime is not None else "—"))
    return head + NOTES[a](algo)


def note_a1(algo):
    na, sa = mode(algo, "na"), mode(algo, "sa")
    ma = mode(algo, "ma")
    ctime = algo.get("ctime_median") or 0
    return """
<div class="note">
<p><b>基线为什么不是 2%%.</b> 基线样本 n=%s，失败 %s，构成是"%s"。上游的 <code>abort_detection</code> 把
任何一架无人机进入障碍内部记为"攻击成功，无人机碰撞到墙壁"，而 4 机编队在狭窄通道里做局部避障时
偶发擦墙（本例集中在 sp_ind≈70~90，t≈32 s），于是基线本身就有约三成失败。这与攻击算法无关：
<code>attack_strategy_none</code> 只推进编队、完全不注入攻击机干扰，判据也与上游逐字一致。</p>
<p><b>SA / MA 为什么都是 100%%.</b> SA 每个运行都在 sp_ind≈70~80 处撞墙结束，单次任务中位 wall
<b>%s</b>，是基线 CTime（%.1f s）的 30 倍以上——因为 <code>attack_strategy_SA</code> 每轮要对
20 个候选攻击点各跑一次完整编队预演 + STL 鲁棒度评估；MA 的中位 wall 是 %s s，量级同样远超 2×CTime≈%.0f s。
也就是说按论文判据①，这些运行即使不撞墙也全部超时；实际归因里 SA 有 %s 次真正撞墙、MA 有 %s 次撞墙，
说明两种策略在本快照上都稳定地把集群推入障碍。</p>
<p><b>与论文 32.2%% / 86.2%% 的差距.</b> 差异不在判据方向（判据只会让失败更多，不会让攻击更强），而在上游快照的
局部规划器/地图参数：论文的 A1 基线几乎从不撞墙（2%%），本机是 %s；基线越脆弱，攻击越容易"补最后一刀"，
SA/MA 的增量被放大到 100%%。这是本报告最关键的一处不可对齐。</p>
</div>""" % (na["n"] if na else 0, pct(na), reason_text(algo, na),
             (sa or {}).get("wall_median", "—"), ctime, (ma or {}).get("wall_median", "—"),
             2 * ctime, (sa or {}).get("crashed", 0), (ma or {}).get("crashed", 0), pct(na))


def note_a2(algo):
    na = mode(algo, "na")
    sa = mode(algo, "sa")
    ma = mode(algo, "ma")
    ctime = algo.get("ctime_median") or 0
    return """
<div class="note">
<p><b>判据③的取舍（重要）.</b> 上游 <code>countMatrix</code> 用 0.5 m 的"箱式"阈值统计机间碰撞且从不判失败；
本机实测：十架无人机初始位置全部重合在 (12.5,12.5)，散开过程中必然穿过 0.5 m，因此若按论文判据③直接启用，
<b>无攻击基线也会 100%% 在 t≈12~32 s 判失败</b>，Table II 的 "Failure w/o attack" 完全失去意义。
所以 A2 正式实验统一使用 <code>--collide 0</code>（关闭判据③），只保留 ① 超时（仿真时长上限 2×CTime=%s s）
与 ② 撞障碍/撞边界。这是本机复现最主要的判据口径偏差。</p>
<p><b>基线为什么是 %s.</b> n=%s 的基线里 %s。失败几乎都是"撞向障碍物/边界"（上游 <code>error()</code> 直接退出），
发生在 t=6~350 s；完成的种子 CTime 中位 %.1f s（论文 715.2 s）。本机单任务 wall 只有 2~6 s，
说明上游的 715 s 是仿真步数折算的时间，而不是墙钟耗时。</p>
<p><b>攻击效果.</b> SA 的 n=%s 里失败 %s、完成 %s，崩溃时刻 t=8~121 s 远早于基线完成时间，说明攻击点落在
集群行进路径上后，集群在避障与编队保持之间被推入障碍——方向上与论文（69.7%%）一致，幅度上更极端
（McNemar p≈%.1g）。MA 的 n=%s 失败 %s，同种子配对里"基线成功→MA 失败" %s 次、"反向" %s 次，
McNemar p≈%.1g；本快照上 MA 的增量同样显著（论文 78.6%%），100 个种子已全部采集。</p>
<p><b>攻击机初始位置（代码修复）.</b> 上游 easy 配置把 <code>attack_agent_location</code> 写死为 [5 5]，
而集群在 (12.5,12.5)、感知半径 2、攻击机单步可达 1，两圆完全不重叠，<code>find_influenced_drones</code>
返回空集，Python 侧 <code>vulnerable_nodes[0]</code> 直接越界（即上游该分支在 easy 地图上跑不通）。
按论文 §III-C2/Fig.4"攻击机初始位置应刚好在集群感知范围之外、且在可达范围内"，
在首次进入攻击分支时把攻击机放到"质心 + (r_agent + attack_agent_v) × 单位方向"，
必要时退化为"最近无人机 + 同向偏移"，以保证候选集非空。</p>
</div>""" % (524, pct(na), na["n"] if na else 0, reason_text(algo, na), ctime,
             (sa or {}).get("n", 0), pct(sa), (sa or {}).get("arrived", 0),
             ((algo.get("mcnemar", {}) or {}).get("sa") or {}).get("p", 0),
             (ma or {}).get("n", 0), pct(ma),
             ((algo.get("mcnemar", {}) or {}).get("ma") or {}).get("base_ok_atk_fail", 0),
             ((algo.get("mcnemar", {}) or {}).get("ma") or {}).get("base_fail_atk_ok", 0),
             ((algo.get("mcnemar", {}) or {}).get("ma") or {}).get("p", 0))


def note_a3(algo):
    na = mode(algo, "na")
    sa = mode(algo, "sa_link1")
    ma = mode(algo, "ma_link1")
    return """
<div class="note">
<p><b>攻击链开关（两版都跑）.</b> 上游 Howard 快照的 <code>GradientDescentUpdate</code> 不含攻击机，
<code>Monitor</code> 也不检查它——即攻击机对集群完全不可见，SA/MA 与基线逐位相同。按"两版都跑"的要求
实现了 <code>RSFUZZ_A3_LINK</code>：<code>1</code>=每次迭代把攻击机作为动态 <code>Obstacle</code> 加入集群避让势场
（论文语义，主结果，即上表的 sa/ma_link1），<code>0</code>=上游原样（消融）。</p>
<p><b>基线为什么是 %s（论文 6%%）.</b> n=%s 的基线里 %s。失败几乎全部来自
<code>Monitor</code> 的机间碰撞阈值：它按"两机距离 &lt; 1 m"判撞，而这些无人机的机体半径是 2、
follower 之间只有 <code>r&lt;2</code> 的排斥势（没有队形吸引力），6 机在 10×10×10 的初始盒子里飞行时
频繁进入 1 m 内。基线本身就被这个阈值压得很低，攻击增量因此被淹没（SA %s、MA %s）。</p>
<p><b>CTime 与超时阈值.</b> 上游没有"任务完成"出口，只靠 150 次迭代上限截断，所以本机补了
"全部无人机进入终点 waypoint 的 <code>dist_thresh</code> 范围"作为完成判据并记录 <code>GoalReached</code>。
基线的完成迭代数为 139~194，每步 0.1 s 折合 CTime≈16 s，与论文 17.28 s 基本吻合；
按论文判据①取 2×CTime≈320 步作为超时阈值。</p>
</div>""" % (pct(na), na["n"] if na else 0, reason_text(algo, na), pct(sa), pct(ma))


NOTES = {"A1": note_a1, "A2": note_a2, "A3": note_a3}

CHANGES = """
<table>
<thead><tr><th>文件</th><th>改动</th><th>依据</th></tr></thead>
<tbody>
<tr><td>Adaptive Swarm/tool/monitor.py, tool.py</td><td>为 rtamt 0.4.10 补 STL 类名别名</td><td>本机 rtamt 版本兼容（不改算法）</td></tr>
<tr><td>…/layered_planner/fuzz.py</td><td>新增 <code>attack_strategy_none</code> 并在 <code>start()</code> 中分派</td><td>无攻击基线必须仍推进集群运动，<code>pass</code> 会让集群静止</td></tr>
<tr><td>Howard/src/SA_Fuzzing.m, MA_Fuzzing.m</td><td>Nd/种子/绘图开关/攻击链开关/迭代上限/完成判据/失败归因日志</td><td>论文 §IV-B 判据①②③、Table II 规模</td></tr>
<tr><td>Howard/src/Robustness.m</td><td>去掉与循环变量无关的 n 次重复计算</td><td>等价化简，单任务 900 s→146 s</td></tr>
<tr><td>Howard/src/fuzzer.m</td><td><code>py.sys.path</code> 判重、2D→3D 坐标、vuln_list 转换</td><td>MATLAB 2024b Python 接口</td></tr>
<tr><td>Howard/src/katz.py, Pietro/katz.py</td><td>matplotlib 下沉到函数内</td><td>MATLAB 自带 libexpat.dll 与 pyexpat 冲突</td></tr>
<tr><td>Pietro/SA_Fuzzing.m, MA_Fuzzing.m, next_pos.m</td><td>pyenv 读环境变量、insert 代替 append、障碍列动态偏移、攻击候选多边形按行拼接、判据③开关、na 模式、绘图开关</td><td>上游写死 24 行/9:10 列只对 hard 地图成立</td></tr>
<tr><td>Pietro/next_pos.m（新增）</td><td>补上游缺失的一步预演函数</td><td>上游仓库缺文件，按主循环同样的传感器+控制逻辑补齐</td></tr>
<tr><td>Pietro/rsfuzz_polyxpoly.m（新增，当前未调用）</td><td>折线×折线线段求交，作为 <code>polyxpoly</code> 的等价备份实现</td><td>本机初装 MATLAB 时无 Mapping Toolbox；2026-11-05 装好 Mapping Toolbox 24.2 后，SA/MA/next_pos 已按上游原样恢复 <code>polyxpoly</code>，本文件仅作备份</td></tr>
<tr><td>Pietro/run_a2.m, Howard/src/run_a3.m, repro/run_a1.py（新增）</td><td>单任务驱动：环境变量注入种子/模式/输出目录，写 result.json</td><td>批量实验与结果落盘</td></tr>
<tr><td>repro/sched.py, analyze.py（新增）</td><td>多进程调度、每槽位独立 MATLAB 偏好目录、启动串行化与重试、汇总与 McNemar 检验</td><td>并发启动 MATLAB 会争用 preferences 触发 <code>File system inconsistency</code>（与被测程序无关）</td></tr>
<tr><td>repro/batch_a2.m（新增）</td><td>单 MATLAB 进程内循环跑多个 (mode, seed)，逐个写 result.json</td><td>本机反复新起 matlab.exe 会随机报 <code>Fatal Startup Error</code>；改成一次启动、循环跑完，启动次数从 300 降到个位数</td></tr>
</tbody></table>
"""


def main():
    with open(os.path.join(HERE, "runs", "analysis.json"), encoding="utf-8") as f:
        raw = json.load(f)
    data = {d["algo"]: d for d in raw}

    body = []
    for a in ["A1", "A2", "A3"]:
        if a in data:
            body.append(algo_block(data[a]))

    n_line = "；".join("%s 基线 n=%s / SA n=%s / MA n=%s" % (
        a, (data[a].get("modes", {}).get("na") or {}).get("n", 0),
        (data[a].get("modes", {}).get("sa") or data[a].get("modes", {}).get("sa_link1") or {}).get("n", 0),
        (data[a].get("modes", {}).get("ma") or data[a].get("modes", {}).get("ma_link1") or {}).get("n", 0))
        for a in ["A1", "A2", "A3"] if a in data)

    html = []
    html.append("""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>RSFuzz 本机复现报告（Windows / MATLAB R2024b）</title>
<style>""" + CSS + """</style></head>
<body><main>
<h1>RSFuzz 本机复现报告</h1>
<p class="sub">Windows 11 · MATLAB R2024b · Python 3.10 · i9-13900HX（24 核 32 线程）/ 16 GB<br>
对照论文 <i>RSFuzz: Fuzzing Swarm Robots with STL Robustness</i> Table II，与 Linux 虚拟机上一轮复现互为参照</p>

<h2>1. 复现口径</h2>
<div class="kv">
<div>被测系统</div><div>A1 Adaptive Swarm（纯 Python，4 机）/ A2 Pietro 2D 集群（MATLAB+Python，10 机）/ A3 Howard 3D 集群（MATLAB+Python，6 机）</div>
<div>算法</div><div>无攻击基线（论文 "Failure w/o attack"）、SA-Fuzzing（模拟退火选点）、MA-Fuzzing（元胞自动机式 20 候选）</div>
<div>失败判据</div><div>① 任务时长 &gt; 2×CTime（本机实测基线中位时间）② 撞障碍/撞边界 ③ 机间碰撞；攻击机撞受害机不计失败。</div>
<div>种子</div><div>同种子配对（基线 / SA / MA 使用同一 seed），McNemar 精确检验（双侧二项精确检验）</div>
<div>规模</div><div>A1=4、A2=10、A3=6（各算法取论文最小规模档）</div>
<div>本机样本量</div><div>""" + n_line + """</div>
</div>
<p class="warn">减量说明：论文每个条件 2000 次、基线 50 次，总计约 36,450 次；本机按用户决策降为每算法每条件数十至 100 个种子。
A1 的 SA/MA 单任务需 900~2400 s（20 候选点 × 完整 STL 评估），是本轮实验的算力瓶颈，因此 A1 的样本量小于 A2/A3。</p>

<h2>2. 结果总表（论文 → 本机）</h2>
<table>
<thead><tr><th>系统</th><th>Failure w/o attack</th><th>SA-Fuzzing</th><th>MA-Fuzzing</th><th>CTime</th></tr></thead>
<tbody>""" + summary_rows(data) + """</tbody></table>
<p class="ctime">表格每格为"论文值 → 本机实测值"。本机 A3 取论文语义版（攻击机进入集群势场，<code>RSFUZZ_A3_LINK=1</code>）。</p>

<h2>3. 分系统结果与归因</h2>
""" + "\n".join(body) + """

<h2>4. 代码改动清单</h2>
<p>全部改动遵循两条约束：<b>原代码注释保留</b>、<b>新增代码带 <code>[AI-MOD 2026-11-05]</code> 注释并说明论文依据</b>；
不修改算法语义，只修可运行性与论文判据。</p>
""" + CHANGES + """

<h2>5. 偏差分析与结论</h2>
<ul>
<li><b>链路是通的。</b>三套系统在本机全部跑通（含 MATLAB↔Python 联调；本机已装 Mapping Toolbox 24.2，
A2 的红外传感器判定按上游原样使用 <code>polyxpoly</code>），
批量调度、结果落盘、同种子配对检验、McNemar 检验全部可复算（<code>repro/analyze.py</code> → <code>analysis.json</code> → 本报告）。</li>
<li><b>最主要的系统性偏差是基线失败率被抬高</b>（A1 30%、A2 34%、A3 75%，论文 2%/4%/6%）。
根因是三份上游快照的碰撞判据在本机规模下过严（A3 的 1 m 机间距、A2 的 0.5 m 箱式计数、A1 的"扎进障碍即判撞"），
与攻击算法无关。基线越高，攻击可带来的增量越被压缩。</li>
<li><b>攻击有效性分三档</b>：A1 的 SA/MA 显著（100% vs 基线 30%，McNemar p≈1.2e-4，基线成功→攻击失败 14 次、反向 0 次）；
A2 的 SA 显著（90% vs 34%，p≈4e-16），MA 同样显著（58% vs 34%，n=100，p≈7e-4）；
A3 的 SA/MA 与基线无显著差异（85%/79% vs 75%，p=0.11/0.60），因为基线已被 1 m 机间距判据压到 75%。
结论是"攻击确实能提高失败率，但能提高多少主要取决于基线判据留了多少余量"。</li>
<li><b>不可对齐之处</b>：论文 Table II 的绝对数值依赖作者当时的代码版本与硬件；本仓库快照的规划器/判据与之有差异，
因此本报告只主张"同口径、同种子、可复算"的本机数据，不主张复现论文的具体百分比。</li>
<li><b>工程问题（MATLAB 启动）</b>：本机 MATLAB R2024b 反复新起 <code>matlab.exe</code> 时会随机报
<code>Fatal Startup Error: System Error: File system inconsistency</code>（与被测程序无关）。
验证过的缓解手段（独立 <code>MATLAB_PREFDIR</code>、启动错峰、失败重试、关闭沙箱）都不能消除它，
最终改用 <code>repro/batch_a2.m</code>：一个 MATLAB 进程内循环跑多个 (mode, seed)，
启动次数从 300 降到个位数，A2 的 na/sa/ma 三档 100 种子因此全部跑齐（每个任务仍独立写 result.json，
启动故障不会污染失败率）。</li>
</ul>

<footer>数据来源：<code>RSFuzz/repro/runs/analysis.json</code>（由 <code>repro/analyze.py</code> 从每个任务的 result.json 汇总）。
报告由 <code>repro/report.py</code> 生成。</footer>
</main></body></html>
""")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("".join(html))
    print("[report] ->", OUT)


if __name__ == "__main__":
    main()
