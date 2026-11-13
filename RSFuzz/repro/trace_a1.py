# -*- coding: utf-8 -*-
"""[AI-MOD 2026-11-12] A1 (Adaptive Swarm) 数据采集。

设计约束（与 A2/A3 的 rsfuzz_trace 一致）：
  1. **不修改 fuzz.py**：全部逻辑靠"包装实例方法"实现，只读取 att 的状态后写文件；
  2. 只在 RSFUZZ_TRACE=1 时生效，关闭时不包装、不建目录、不产生任何开销；
  3. 输出格式与 MATLAB 侧相同（frame.jsonl / iter.jsonl），供 etl/importer.py 统一入库。

记录的内容：
  frame.jsonl  {step, t, agents:[{k:'uav'|'attacker', id, p:[x,y]}]}
  iter.jsonl   {step, t, pos:[x,y], rob}      —— rob 取本轮 20 个候选里的最小值

与 A2/A3 的差异：Adaptive Swarm 没有仿真时钟（按循环次数推进），t 一律写 null。
"""
import json
import math
import os


def _pt(v):
    """位置向量 → 保留 6 位的 [x, y]（A1 是 2D，且坐标可为负）。"""
    return [round(float(v[0]), 6), round(float(v[1]), 6)]


def _append(path, rec):
    """逐行追加并立即关闭：仿真中途抛异常时已写内容不会丢。"""
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n")


class TraceWriter:
    def __init__(self, out_dir):
        self.enabled = os.environ.get("RSFUZZ_TRACE") == "1"
        self.step = 0
        trace_dir = os.path.join(out_dir, "trace")
        self.frame_path = os.path.join(trace_dir, "frame.jsonl")
        self.iter_path = os.path.join(trace_dir, "iter.jsonl")
        if not self.enabled:
            return
        os.makedirs(trace_dir, exist_ok=True)
        for p in (self.frame_path, self.iter_path):
            if os.path.exists(p):
                os.remove(p)

    def frame(self, robots, attacker=None):
        if not self.enabled:
            return
        agents = [{"k": "uav", "id": i, "p": _pt(r.sp)} for i, r in enumerate(robots)]
        if attacker is not None:
            agents.append({"k": "attacker", "id": len(robots), "p": _pt(attacker)})
        _append(self.frame_path, {"step": self.step, "t": None, "agents": agents})

    def iteration(self, pos, rob):
        if not self.enabled or rob is None:
            return
        _append(self.iter_path, {"step": self.step, "t": None, "pos": _pt(pos), "rob": rob})

    def tick(self):
        if self.enabled:
            self.step += 1


def write_map(att, out_dir):
    """把地图几何（障碍多边形 + 边界 + 起终点）写成 map.json，供回放渲染与入库。

    上游把障碍写死在 fuzz.py 的 self.obstacles 里（4x2 顶点数组列表），这里只是抄一份，
    不参与任何计算。
    注意：fuzz.py 末尾有一个放在 (999, 2) 的"哨兵障碍"（for fuzzing 用），如果计入，
    边界会被撑到 999 m，且画面上会出现一个地图外的方块，所以这里按坐标合理性剔除。
    """
    def sane(ob):
        return all(abs(float(v)) <= 100 for v in ob.ravel())

    usable = [ob for ob in att.obstacles if sane(ob)]
    pts = [p for ob in usable for p in ob]
    xs = [float(p[0]) for p in pts]
    ys = [float(p[1]) for p in pts]
    rec = {
        "bounds": {"x": [min(xs + [float(att.xy_start[0]), float(att.xy_goal[0])]),
                         max(xs + [float(att.xy_start[0]), float(att.xy_goal[0])])],
                   "y": [min(ys + [float(att.xy_start[1]), float(att.xy_goal[1])]),
                         max(ys + [float(att.xy_start[1]), float(att.xy_goal[1])])]},
        "obstacles": [{"kind": "polygon",
                       "pts": [[round(float(x), 6), round(float(y), 6)] for x, y in ob]}
                      for ob in usable],
        "start": _pt(att.xy_start),
        "goal": _pt(att.xy_goal),
        "dim": 2,
    }
    with open(os.path.join(out_dir, "map.json"), "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)


def install(att, out_dir):
    """包装四个攻击策略方法，每轮结束后记一帧。返回 TraceWriter（关闭时 enabled=False）。"""
    writer = TraceWriter(out_dir)
    if not writer.enabled:
        return writer

    write_map(att, out_dir)

    names = ("attack_strategy_random", "attack_strategy_SA",
             "attack_strategy_MA", "attack_strategy_none")
    for name in names:
        original = getattr(att, name)

        def make(orig, is_attack):
            def wrapped(traj_global, sp_ind, followers_sp):
                n0 = len(att.rob_list)          # 本轮新增的候选鲁棒度从这里开始
                out = orig(traj_global, sp_ind, followers_sp)
                atk = att.attack_robot.sp if is_attack else None
                writer.frame(att.robots, atk)
                fresh = [r for r in att.rob_list[n0:] if isinstance(r, (int, float))
                         and math.isfinite(r)]
                if fresh:
                    # rob_list 每轮按候选追加一次，取最小值 = 本轮选中的攻击点鲁棒度
                    writer.iteration(att.attack_robot.sp, round(min(fresh), 6))
                writer.tick()
                return out
            return wrapped

        setattr(att, name, make(original, name != "attack_strategy_none"))
    return writer
