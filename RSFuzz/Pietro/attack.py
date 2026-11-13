import numpy as np
import random
import robustness as rob
import math
import os
import katz
# os.sys.path().append('D:\\liyilin\\Swarm\\SwarmRoboticsSim\\')
##数据处理

def attack_agent_location(x, y):
    x_location, y_location = 0, 0
    for i in range(10):
        x_location += float(x[i])
        y_location += float(y[i])
    x_location = y_location/10
    y_location = y_location/10
    return [x_location, y_location]

def drones_agent_location(x, y):
    x, y= list(x), list(y)
    drones_agent_location = []
    for i in range(len(x)):
        drones_agent_location.append((float(x[i]), float(y[i])))
    return drones_agent_location

def obstacles_list(x, y):
    x, y= list(x), list(y)
    obstacles_list = []
    location_x, location_y = x[:-1], y[:-1]
    for i in range(len(location_x)):
        obstacles_list.append((float(location_x[i]), float(location_y[i])))
    return obstacles_list


# def attack_agent_location_random(attack_agent_location, attack_agent_v):
#     random_points= []
#     # 在攻击机的行驶范围内随机生成a个点
#     # 生成随机角度
#     for i in range(20):
#         angle = random.uniform(0, 2*math.pi)
#         # 计算随机点的坐标
#         x = attack_agent_location[0] + attack_agent_v * math.cos(angle)
#         y = attack_agent_location[1] + attack_agent_v * math.sin(angle)
#         random_points.append((x, y))
#     return random_points
    # pass
def attack_agent_location_random(drone_list, drone_agent_r, attack_agent_location, attack_agent_v, number, max_influence_distance):
    # [AI-MOD 2026-11-05] 空 drone_list 必须在建图之前返回：katz.Graph 内 nx.katz_centrality 对
    # 空节点集返回空字典，随后 max(katz_centrality.values()) 抛
    # "ValueError: max() arg is an empty sequence"（实测 i=25 时触发，MATLAB 侧整任务中断）。
    # 语义上：没有受害机就取不到候选点（论文 §III-C2），返回空列表由 MATLAB 侧跳过。
    if not drone_list:
        return []
    graph = katz.Graph(drone_list, max_influence_distance)
    # [AI-MOD 2026-11-05] 上游直接 drone_list[graph.vulnerable_nodes[0]]，vulnerable_nodes 为空时
    # 会 IndexError；同理返回空列表。
    # drone_agent_location = drone_list[graph.vulnerable_nodes[0]]
    if not graph.vulnerable_nodes:
        return []
    drone_agent_location = drone_list[graph.vulnerable_nodes[0]]
    # print(drone_agent_location)  
    x1, y1 = drone_agent_location[0], drone_agent_location[1]
    x2, y2 = attack_agent_location[0], attack_agent_location[1]
    r1 = drone_agent_r
    r2 = attack_agent_v
    # 找出两个圆的交点
    def find_intersection_points(x1, y1, r1, x2, y2, r2):
        d = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        if d > r1 + r2 or d < abs(r1 - r2):
            return None  # 没有交点
        
        a = (r1**2 - r2**2 + d**2) / (2 * d)
        h = np.sqrt(r1**2 - a**2)
        x0 = x1 + a * (x2 - x1) / d
        y0 = y1 + a * (y2 - y1) / d
        rx = -(y2 - y1) * (h / d)
        ry = (x2 - x1) * (h / d)
        
        return [(x0 + rx, y0 + ry), (x0 - rx, y0 - ry)]
    # 找出交点
    intersection_points = find_intersection_points(x1, y1, r1, x2, y2, r2)
    # print(intersection_points)
    if intersection_points is None:
        # [AI-MOD 2026-11-05] 上游打印提示后返回 None；MATLAB 侧拿到的 py.NoneType 无法安全判空
        # （会继续传给 attack_strategy_SA 并抛出 TypeError 使整任务中断）。两圆无重叠 = 本步不存在
        # 可行候选点，统一返回空列表，MATLAB 侧判空后跳过攻击机插入。
        # print("攻击机与无人机没有重叠部分")
        # return None
        return []
    else:
        # 在重叠区域内随机生成点
        random_points = []            
        # [AI-MOD 2026-11-05] 上游是 "每个点一个 while True" 的拒绝采样：当两圆相切（例如攻击机
        # 与受害机距离恰为 r_agent + attack_agent_v，本机初始位置正是这种相切布置）或重叠面积极小时，
        # 命中概率为 0，会死循环并卡死整个 MATLAB 批处理任务。改为全局有界重试：
        # 每个候选点最多 200 次采样，预算耗尽后按"重叠区退化"处理，保证函数一定返回。
        # for _ in range(int(number)):
        #     while True:
        #         x = np.random.uniform(min(x1 - r1, x2 - r2), max(x1 + r1, x2 + r2))
        #         y = np.random.uniform(min(y1 - r1, y2 - r2), max(y1 + r1, y2 + r2))
        #         if (x - x1)**2 + (y - y1)**2 <= r1**2 and (x - x2)**2 + (y - y2)**2 <= r2**2:
        #             random_points.append((x, y))
        #             break        
        max_tries = 200 * max(1, int(number))
        tries = 0
        while len(random_points) < int(number) and tries < max_tries:
            tries += 1
            x = np.random.uniform(min(x1 - r1, x2 - r2), max(x1 + r1, x2 + r2))
            y = np.random.uniform(min(y1 - r1, y2 - r2), max(y1 + r1, y2 + r2))
            if (x - x1)**2 + (y - y1)**2 <= r1**2 and (x - x2)**2 + (y - y2)**2 <= r2**2:
                random_points.append((x, y))
        if not random_points:
            # [AI-MOD 2026-11-05] 退化情形（典型：d == r1 + r2，两圆相切，重叠区面积为 0）：均匀撒点
            # 不可能命中，退回"重叠区边界的交点"作为候选位置。该点同时落在受害机感知圆与攻击机可达圆
            # 上，符合论文 §III-C2 "候选点取自两圆重叠区"的语义，且保证返回非空、SA-Fuzzing 有候选可筛。
            uniq = []
            for p in intersection_points:
                if not any(abs(p[0] - q[0]) < 1e-9 and abs(p[1] - q[1]) < 1e-9 for q in uniq):
                    uniq.append((float(p[0]), float(p[1])))
            random_points = uniq
        return random_points

def find_influenced_drones(drone_agent_location, drone_agent_r, attack_agent_location, attack_agent_v):
    """
    找出与攻击机可达范围有重叠部分的无人机的无人机坐标
    """
    influenced_drones = []
    
    for center in drone_agent_location:
        dist = math.sqrt((center[0] - attack_agent_location[0]) ** 2 + (center[1] - attack_agent_location[1]) ** 2)
        if dist <= (drone_agent_r + attack_agent_v) and dist >= abs(drone_agent_r - attack_agent_v):
            influenced_drones.append(center)
    
    return influenced_drones

def attack_strategy_SA(attack_agent_location, drones_agent_location, obstacles_list):
    """
    攻击策略1：SA-Fuzzing
    """
    # print(len(attack_agent_location))
    robustness = [0 for i in range(len(attack_agent_location))]
    obstacles_list = list(obstacles_list)
    i = 0
    for attack in attack_agent_location:
        x, y = attack[0], attack[1]
        # print(x, y)
        obstacles_list.append([(x-1, y),(x, y-1),(x+1, y),(x, y+1)])
        # 计算每个随机点的robustness值
        robustness[i] = rob.rule1_prepare(drones_agent_location, obstacles_list)
        #obstacles_list.remove([(x-1, y),(x, y-1),(x+1, y),(x, y+1)])
        obstacles_list.pop()
        i += 1
    # print(robustness)
    attack_index = robustness.index(min(robustness))
    return attack_agent_location[attack_index]


def attack_strategy_MA(drones_agent_location, drones_agent_r, obstacles_list):
    """
    攻击策略2：MA-Fuzzing
    """
    graph = katz.Graph(drones_agent_location, 1.5*drones_agent_r)
    drone_agent_location = drones_agent_location[graph.vulnerable_nodes[0]]
    # print(vulnerable_nodes)
    attack_agent_locations = []
    for i in range(20):
        angle = random.uniform(0, 2 * math.pi)
        x = drone_agent_location[0] + drones_agent_r * math.cos(angle)
        y = drone_agent_location[1] + drones_agent_r * math.sin(angle)
        attack_agent_locations.append((x, y))
    robustness = [0 for i in range(20)]
    obstacles_list = list(obstacles_list)
    # 随机在无人机的周围生成20个点 
    for i, attack_point in enumerate(attack_agent_locations):
        x, y = attack_point[0], attack_point[1]
        obstacles_list.append([(x-1, y),(x, y-1),(x+1, y),(x, y+1)])
        # 计算每个随机点的robustness值
        robustness[i] = rob.rule1_prepare(drones_agent_location, obstacles_list)
        obstacles_list.remove([(x-1, y),(x, y-1),(x+1, y),(x, y+1)])
    
    # 选择robustness最小的攻击点
    best_attack_index = robustness.index(min(robustness))
    attack_agent_location = attack_agent_locations[best_attack_index]
    return attack_agent_location
            
            






