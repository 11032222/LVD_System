% %% Simulation parameters
% run simulation_config  %Change simulation parameters in simulation_config.m
% 设置 Python 解释器路径

% [AI-MOD 2026-11-05] 上游把解释器路径硬编码为作者机器上的
% D:\Frame_envir\anaconda3\envs\zry-python3.10\python.exe（本机不存在）。改为读环境变量
% RSFUZZ_PYTHON，缺省为本机 py3.10（已装 numpy/scipy/shapely/networkx，满足 A2 的
% 攻击策略所需依赖）。pyenv 装载后不可再次设置，故 try/catch 兜底——run_a2.m 会先设置。
% pyenv('Version','D:\\Frame_envir\\anaconda3\\envs\\zry-python3.10\\python.exe');
rsfuzz_py = getenv('RSFUZZ_PYTHON');
if isempty(rsfuzz_py)
    rsfuzz_py = 'D:\Anaconda_envs\envs\py3.10\python.exe';
end
try
    pyenv('Version', rsfuzz_py);
catch
    % 已装载 Python 时忽略
end
% [AI-MOD 2026-11-05] 上游硬编码 D:\liyilin\Swarm\SwarmRoboticsSim\；改为按本脚本自身
% 位置推导（attack.py / katz.py / robustness.py 就在本目录）。批量任务会 cd 到独立工作
% 目录，只有绝对路径才能保证 py.attack 仍可导入。
% python_module_path = 'D:\liyilin\Swarm\SwarmRoboticsSim\';
python_module_path = fileparts(mfilename('fullpath'));
%py.importlib.import_module('attack.py');
% 添加 Python 模块路径
if isfolder(python_module_path)
    % py.sys.path().append(python_module_path);
    insert(py.sys.path, int32(0), python_module_path); % [AI-MOD] MATLAB 不支持 py.sys.path() 调用语法
else
    disp('Error: Python module path does not exist.');
end

% [AI-MOD 2026-11-05] 批量实验开关（由 repro/sched.py 注入环境变量）：
%   RSFUZZ_DRAW=0 关闭全部绘图：每步 figure/patch/text 重绘是批量跑的主要耗时，且与论文
%                 §IV-B 的失败判据无关（默认仍保留上游的绘图行为）。
%   RSFUZZ_MODE=na 无攻击基线（论文 Table II 的 "Failure w/o attack"）：整段攻击机逻辑跳过，
%                  集群更新与失败判据完全不变。
RSFUZZ_DRAW = ~strcmp(getenv('RSFUZZ_DRAW'), '0');
RSFUZZ_MODE = getenv('RSFUZZ_MODE');
if isempty(RSFUZZ_MODE)
    RSFUZZ_MODE = 'sa';   % 缺省与上游一致：带攻击
end
RSFUZZ_ATTACK = ~strcmp(RSFUZZ_MODE, 'na');
% [AI-MOD 2026-11-05] 判据③（论文 §IV-B 机间碰撞）开关，缺省开启。设 RSFUZZ_COLLIDE=0 可单独关闭：
% 实测上游 countMatrix 的 0.5 m 箱式阈值只相当于"擦肩"（两机中心相距 0.65 m 即命中），而本快照的
% 集群没有机间避让、且多机会同时停在同一个目标圆内搜索，因此任何一次 na 基线在 t≈13~37 s 就会命中，
% 使基线 100% 失败、论文 Table II 的 "Failure w/o attack" 失去意义。保留开关便于对比赛判据的影响。
RSFUZZ_COLLIDE = ~strcmp(getenv('RSFUZZ_COLLIDE'), '0');
% [AI-MOD 2026-11-12] 数据采集开关（论文复现可视化 / 数据库 trace_frame、iteration_metric 用）。
%   RSFUZZ_TRACE=1 时每步调用 rsfuzz_trace 落 JSONL；缺省未设置即关闭。
%   采集只读状态、只写文件，不参与任何计算与判定；关闭时 rsfuzz_trace 立即 return，
%   与原版逐位一致（可用同一 seed 对比 result.json 验证）。
RSFUZZ_TRACE = strcmp(getenv('RSFUZZ_TRACE'), '1');
%% Initialise swarm state matrix - q(:,j) = [x y]
global Q
global S
Q = zeros(4,N); %create empty swarm state array
S = zeros(11,N); %create empty swarm sensor array
S(1,:) = timer; %input timer value into sensor array
countMatrix = zeros(1,N); %collisions between drones
rsfuzz_coll_prev = [];    % [AI-MOD 2026-11-05] 上一时刻的机间碰撞矩阵（见下方判据③的边沿触发说明）

%% Base location coordinates and target status
for i = 1:N;
    Q(2,i) = map_size/2; %initial x position (m)
    %Q(2,i) = 1.2 ;
    %Q(3,i) = 1.25;
    Q(3,i) = map_size/2; %initial y position (m)
end
target_status = zeros(size(targets,2),3); %create array to store search status (:,1), completion time of each target (:,2) and number of agents inside (:,3)
target_status(:,2) = NaN;   %initialise target 100% completion times as NaN

%% Calculations and plotting
t = t0;
% [AI-MOD 2026-11-05] RSFUZZ_DRAW=0 时整体跳过绘图（批量实验用；绘图不参与任何计算与判据）。
if RSFUZZ_DRAW
figure(1);
whitebg([1 1 1]);
axis equal;
axis([0 map_size 0 map_size]);
xlabel('x (m)');
ylabel('y (m)');
ho = text(map_size/20,map_size/20,strcat(num2str(t),'s'));
end

for i = 1:((t_end/dt)+1);
if RSFUZZ_DRAW   % [AI-MOD 2026-11-05] 见上：批量实验关闭绘图
figure(1);
end
target_status(:,3) = 0; %reset searching agents in target_status
% if i >=10 
% [AI-MOD 2026-11-05] 见文件头 RSFUZZ_MODE 说明：na 模式（无攻击基线，论文 Table II
% "Failure w/o attack"）跳过整段攻击机逻辑，只保留原来的集群更新与失败判据。
if i >= 10 && RSFUZZ_ATTACK
    %%AttackDrone
    %攻击机的坐标
    drones_agent_center = py.attack.drones_agent_location(Q(2,:), Q(3,:));
    for k = 1:size(obstacles,2)/2   
        obstacles_list{k} = py.attack.obstacles_list(obstacles{1,(2*k - 1)}(:),obstacles{1,(2*k)}(:));
    end
    % [AI-MOD 2026-11-05] 攻击机多边形追加到障碍物列表末尾，而不是上游写死的第 9~10 列。
    % 依据：列号 9:10 对应 hard 地图的 8 列障碍；easy 地图只有 2 列（1 个五边形障碍），
    % 写死 9:10 会在第 3~8 列留下空障碍单元（空单元经 obstacles_list 传给 Python 会变成
    % 空多边形，shapely 距离变 NaN），并把 size(obstacles,2)/2 撑成 5 个"障碍"。
    % 末尾追加与上游语义一致（攻击机作为附加障碍参与集群避障），列偏移只在首次进入时算一次。
    if i == 10
        rsfuzz_atk_col = size(obstacles, 2) + 1;
    end
    m = 1;
    drones_agent_center_new = py.attack.find_influenced_drones(drones_agent_center, IR_dist, attack_agent_location, attack_agent_v);
    % [AI-MOD 2026-11-05] 论文 §III-C2 / Fig.4：攻击机初始位置应"刚好在集群感知范围之外、且在
    % 可达范围内"，候选点取自"受害机感知圆 ∩ 攻击机可达圆"的重叠区。上游 easy 配置写死
    % attack_agent_location = [5 5]，而集群初始在 (12.5,12.5)、IR_dist = 2、attack_agent_v = 1，
    % 两圆完全不重叠 -> find_influenced_drones 返回空 -> Python 侧 vulnerable_nodes[0] 越界。
    % 因此仅在"首次进入攻击分支且受影响集合为空"时，把攻击机放到
    % 质心 + (r_agent + attack_agent_v) × 单位方向（方向取远离地图中心；退化时取 [1 0]）。
    if i == 10 && int32(py.len(drones_agent_center_new)) == 0
        rsfuzz_c = [mean(Q(2,:)), mean(Q(3,:))];
        rsfuzz_dir = rsfuzz_c - [map_size/2, map_size/2];
        if norm(rsfuzz_dir) < 1e-9
            rsfuzz_dir = [1 0];
        else
            rsfuzz_dir = rsfuzz_dir / norm(rsfuzz_dir);
        end
        rsfuzz_d = r_agent + attack_agent_v;
        attack_agent_location = rsfuzz_c + rsfuzz_d * rsfuzz_dir;
        drones_agent_center_new = py.attack.find_influenced_drones(drones_agent_center, IR_dist, attack_agent_location, attack_agent_v);
        % 若集群已散开、质心公式仍未命中任何受害机，则改用"距质心最近的无人机 + 同一方向偏移"，
        % 使攻击机恰落在该机感知边界上（距离 = r_agent + attack_agent_v），保证候选集合非空。
        if int32(py.len(drones_agent_center_new)) == 0
            [~, rsfuzz_near] = min(sum((Q(2:3,:) - rsfuzz_c').^2, 1));
            attack_agent_location = Q(2:3,rsfuzz_near)' + rsfuzz_d * rsfuzz_dir;
            drones_agent_center_new = py.attack.find_influenced_drones(drones_agent_center, IR_dist, attack_agent_location, attack_agent_v);
        end
        fprintf('[A2] i=%d 攻击机初始位置重置为 [%.3f %.3f]，受影响无人机 %d 架\n', ...
                i, attack_agent_location(1), attack_agent_location(2), int32(py.len(drones_agent_center_new)));
    end
    attack_agent_random = py.attack.attack_agent_location_random(drones_agent_center_new, IR_dist, attack_agent_location, attack_agent_v, 20, 0.5);
    while m < length(attack_agent_random)
        % [AI-MOD 2026-11-05] 按 size(obstacles,1) 动态重建候选多边形（上游写死 1:5 实心、6:24 空）。
        % easy 地图的 obstacles 只有 5 行（1 个五边形障碍），写死 24 行会让下面的
        % "obstacles(:, rsfuzz_atk_col+(0:1)) = Attack_agnet" 尺寸不匹配报错；cell 预分配同时
        % 避免上一次迭代留下的 24 行残留（行数=障碍顶点数，列=2 个/障碍，与 .mat 布局一致）。
        Attack_agnet_x = cell(size(obstacles,1),1);
        Attack_agnet_y = cell(size(obstacles,1),1);
        Attack_agnet_x(1:5) = {[attack_agent_random{m}{1}-1,attack_agent_random{m}{1},attack_agent_random{m}{1}+1,attack_agent_random{m}{1},attack_agent_random{m}{1}-1]};
        % Attack_agnet_x(6:24) = {[]};
        Attack_agnet_y(1:5) = {[attack_agent_random{m}{2},attack_agent_random{m}{2}-1,attack_agent_random{m}{2},attack_agent_random{m}{2}+1,attack_agent_random{m}{2}]};
        % Attack_agnet_y(6:24) = {[]};
        % Attack_agnet = [Attack_agnet_x',Attack_agnet_y'];
        % [AI-MOD 2026-11-05] 上游用 [x', y'] 拼成 1×(2n)，而 obstacles(:,col:col+1) 是 n×2，
        % 尺寸不匹配（实测报错"左侧 5×2 / 右侧 1×10"），即该攻击分支在上游快照里根本跑不通。
        % 改为按行=顶点、列=(x,y) 直接拼接，保持 cell 布局与 .mat 一致。
        Attack_agnet = [Attack_agnet_x, Attack_agnet_y];
        % obstacles(:,9:10) = Attack_agnet;
        obstacles(:, rsfuzz_atk_col + (0:1)) = Attack_agnet;
        [New_Q] = next_pos(t ,map_size ,IR_dist ,IR_angle ,r_agent ,targets , target_status, target_radius, obstacles, N,d_max, Q, S, neighbour);
        % crash = inpolygon(New_Q(2,:),New_Q(3,:),obstacles{1,(9)}(:),obstacles{1,(10)}(:));
        crash = inpolygon(New_Q(2,:),New_Q(3,:),obstacles{1,rsfuzz_atk_col}(:),obstacles{1,rsfuzz_atk_col+1}(:));
        %if py.robustness.drone_is_crush(py.attack.drones_agent_location(New_Q(2,:),New_Q(3,:)), {py.attack.obstacles_list((obstacles{1,(9)}(:)),obstacles{1,(10)}(:))}) == 1
        %if inpolygon(New_Q(2,:),New_Q(3,:),obstacles{1,(9)}(:),obstacles{1,(10)}(:)) == 1
        if isempty(find(crash)) == 0
            attack_agent_random.remove(attack_agent_random{m})
        else
            m = m+1;
        end
    end
    % obstacles(:,9:10) = [];
    if size(obstacles,2) >= rsfuzz_atk_col + 1
        obstacles(:, rsfuzz_atk_col + (0:1)) = [];   % [AI-MOD 2026-11-05] 列号改为动态偏移
    end
    % attack_agent_next = py.attack.attack_strategy_SA(attack_agent_random, drones_agent_center, obstacles_list);
    % [AI-MOD 2026-11-05] attack.py 在"两圆无重叠/采样退化"时返回空列表（见该文件的有界采样说明）。
    % 此时 m 循环不执行、候选为空，Python 的 robustness.index(min(robustness)) 对空序列会抛
    % ValueError 使整任务中断；按"s 步无可行候选 -> 攻击机原地不动"处理，不改变策略语义。
    if int32(py.len(attack_agent_random)) == 0
        attack_agent_next = attack_agent_location;
    else
        attack_agent_next = py.attack.attack_strategy_SA(attack_agent_random, drones_agent_center, obstacles_list);
    end
    Attack_agnet_x = cell(size(obstacles,1),1);   % [AI-MOD 2026-11-05] 见上：按障碍行数动态重建
    Attack_agnet_y = cell(size(obstacles,1),1);
    Attack_agnet_x(1:5) = {[attack_agent_next{1}-1,attack_agent_next{1},attack_agent_next{1}+1,attack_agent_next{1},attack_agent_next{1}-1]};
    % Attack_agnet_x(6:24) = {[]};
    Attack_agnet_y(1:5) = {[attack_agent_next{2},attack_agent_next{2}-1,attack_agent_next{2},attack_agent_next{2}+1,attack_agent_next{2}]};
    % Attack_agnet_y(6:24) = {[]};
    % Attack_agnet = [Attack_agnet_x',Attack_agnet_y'];
    Attack_agnet = [Attack_agnet_x, Attack_agnet_y];   % [AI-MOD 2026-11-05] 见上：n×2 布局
    % obstacles(:,9:10) = Attack_agnet;
    obstacles(:, rsfuzz_atk_col + (0:1)) = Attack_agnet;
    % [New_Q] = next_pos(t ,map_size ,IR_dist ,IR_angle ,r_agent ,targets , target_status, target_radius, obstacles, N,d_max, Q, S, neighbour);
    % t 
    % map_size
    % IR_dist 
    % IR_angle 
    % r_agent 
    % targets 
    % target_status
    % target_radius
    % obstacles
    % 4
    % d_max
    % Q
    % S 
    % neighbour
    %% next_crash = inpolygon(New_Q(2,:),New_Q(3,:),obstacles{1,(9)}(:),obstacles{1,(10)}(:))
    attack_agent_location = attack_agent_next;
end


%% Calculate sensor values for current position of agent j
for j = 1:N    %cycle through swarm of agents
    
    %% Define IR sensors
    %Left/right IR proxity sensors 
    IR_right = [Q(2,j) (Q(2,j)+IR_dist*cos(Q(4,j))) (Q(2,j)+IR_dist*cos(Q(4,j)-IR_angle)) Q(2,j); Q(3,j) (Q(3,j)+IR_dist*sin(Q(4,j))) (Q(3,j)+IR_dist*sin(Q(4,j)-IR_angle)) Q(3,j)]; 
    IR_left = [Q(2,j) (Q(2,j)+IR_dist*cos(Q(4,j))) (Q(2,j)+IR_dist*cos(Q(4,j)+IR_angle)) Q(2,j); Q(3,j) (Q(3,j)+IR_dist*sin(Q(4,j))) (Q(3,j)+IR_dist*sin(Q(4,j)+IR_angle)) Q(3,j)];
    S(2,j) = 0; %reset right IR sensor value to 0
    S(3,j) = 0; %reset left IR sensor value to 0
%   plot(IR_left(1,:),IR_left(2,:),'-g');    %plot left IR sensor
%   hold on;
%   plot(IR_right(1,:),IR_right(2,:),'-r');  %plot right IR sensor
    
    %% Obstacle detection
    % [AI-MOD 2026-11-05] 本机原无 Mapping Toolbox（exist('polyxpoly')==0）时曾临时改用 rsfuzz_polyxpoly.m；
    % 2026-11-05 已安装 Mapping Toolbox 24.2（R2024b，license 可用），按"上游原样/论文 §III-C1"恢复 polyxpoly。
    for k = 1:size(obstacles,2)/2;        
        [IR_detect] = polyxpoly(IR_right(1,:),IR_right(2,:),obstacles{1,(2*k - 1)}(:),obstacles{1,(2*k)}(:));
        % [IR_detect] = rsfuzz_polyxpoly(IR_right(1,:),IR_right(2,:),obstacles{1,(2*k - 1)}(:),obstacles{1,(2*k)}(:));
        if  IR_detect
             S(2,j) = 1; %obstacle detected right, set right IR sensor to 1
        end
        [IR_detect] = polyxpoly(IR_left(1,:),IR_left(2,:),obstacles{1,(2*k - 1)}(:),obstacles{1,(2*k)}(:));
        % [IR_detect] = rsfuzz_polyxpoly(IR_left(1,:),IR_left(2,:),obstacles{1,(2*k - 1)}(:),obstacles{1,(2*k)}(:));
        if  IR_detect
             S(3,j) = 1; %obstacle detected left, set left IR sensor to 1
        end
    end
    
    %% Map boundary detection
    [IR_detect] = polyxpoly(IR_right(1,:),IR_right(2,:),[1E-3; 1E-3; map_size; map_size; 1E-3],[1E-3; map_size; map_size; 1E-3; 1E-3]);
    % [IR_detect] = rsfuzz_polyxpoly(IR_right(1,:),IR_right(2,:),[1E-3; 1E-3; map_size; map_size; 1E-3],[1E-3; map_size; map_size; 1E-3; 1E-3]);
    %[IR_detect] = polyxploy(IR_right(1,:),IR_right(2,:),[-2.5; -2.5; 2.5; 2.5; -2.5],[-2.5; 2.5; 2.5; -2.5; -2.5]);
        if  IR_detect
             S(2,j) = 1; %map boundary detected right, set right IR sensor to 1
        end
    [IR_detect] = polyxpoly(IR_left(1,:),IR_left(2,:),[1E-3; 1E-3; map_size; map_size; 1E-3],[1E-3; map_size; map_size; 1E-3; 1E-3]);
    % [IR_detect] = rsfuzz_polyxpoly(IR_left(1,:),IR_left(2,:),[1E-3; 1E-3; map_size; map_size; 1E-3],[1E-3; map_size; map_size; 1E-3; 1E-3]);
    %[IR_detect] = polyxploy(IR_letf(1,:),IR_letf(2,:),[-2.5; -2.5; 2.5; 2.5; -2.5],[-2.5; 2.5; 2.5; -2.5; -2.5]);
        if  IR_detect
             S(3,j) = 1; %map boundary detected left, set left IR sensor to 1          
        end
    
    %% Detect nearby agent
    % dseachn function is used to find nearest agent
    % neighbour is the index of the nearest agent
    % d_agent is the distance to the nearest agent
    if j == 1;
        [neighbour,d_agent] = dsearchn(Q(2:3,2:N)',Q(2:3,j)');
    elseif j == N;
        [neighbour,d_agent] = dsearchn(Q(2:3,(1:(j-1)))',Q(2:3,j)');
    else
        [neighbour,d_agent] = dsearchn(Q(2:3,[(1:(j-1)) ((j+1):N)])',Q(2:3,j)');
    end
        
    if neighbour >= j;
        neighbour = neighbour +1;  %ensure neighbour index is correct 
    end
    
    if d_agent <= r_agent; %neighbouring agent is not within communication range
        S(9,j) = 1;         %agent detection set to 1 in sensor array
        S(10,j) = d_agent;  %agent-agent distance input to sensor array
        S(11,j) = acos((Q(2,neighbour)-Q(2,j))/d_agent);   %agent-agent angle input to sensor array
        if (Q(3,neighbour)-Q(3,j)) < 0;   
            S(11,j) = S(11,j)*-1; %ensure angle sign is correct
        end
%        plot([Q(2,j) Q(2,neighbour)],[Q(3,j) Q(3,neighbour)],'-m'); %plot solid line between nearby agents within comms range
%        hold on;
    else    %neighbouring agent is not within communication range
        S(9,j) = 0; %agent detection set to 0 in sensor array
        S(10,j) = 0; %non-existent agent-agent distance input to sensor array
        S(11,j) = 0; %non-existent agent-agent angle input to sensor array
%        plot([Q(2,j) Q(2,neighbour)],[Q(3,j) Q(3,neighbour)],':m'); %plot dotted line between nearby agents outside comms range
%        hold on;
        neighbour = NaN;  %nearby agent is out of communcation range so cannot be accessed in agent_control.m
    end

    %% Proximity to target
    S(6,j) = 0; %reset target sensor value to 0
    [nearby_target,d_target] = dsearchn(targets',Q(2:3,j)');    
    
    if target_status(nearby_target,1) < 1;
        if d_target <= target_radius;   %target is detectable
            S(6,j) = 1; %set target sensor value to 1
            S(7,j) = d_target;
            if Q(2,j) >= targets(1,nearby_target) && Q(3,j) >= targets(2,nearby_target);
                 S(8,j) = acos(abs(targets(1,nearby_target)-Q(2,j))/d_target)+pi;
            elseif Q(2,j) <= targets(1,nearby_target) && Q(3,j) >= targets(2,nearby_target);
                 S(8,j) = (2*pi)-acos(abs(targets(1,nearby_target)-Q(2,j))/d_target);
            elseif Q(2,j) <= targets(1,nearby_target) && Q(3,j) <= targets(2,nearby_target)
                 S(8,j) = acos(abs(targets(1,nearby_target)-Q(2,j))/d_target);
            else
                 S(8,j) = (pi - acos(abs(targets(1,nearby_target)-Q(2,j))/d_target));
            end
        end
    end        

    %% Input state and sensor data into agent logic 
    pos_old = Q(2:3,j); %temporarily store old position
    %这里需要还原无人机现场
    [Q(:,j)] = advanced_agent_control(t,j,N,d_max,Q(:,j),S(:,j),neighbour);    %run agent_control sub-function for agent j
    S(4,j) = sqrt((pos_old(1) - Q(2,j))^2 + (pos_old(2) - Q(3,j))^2);  %enter agent translation distance into sensor array
    S(5,j) = Q(4,j); %enter agent theta into sensor array
end

% if i > 10
%     if ~isequal(Q, New_Q)
%         i
%         Q
%         New_Q
%         t 
%         map_size
%         IR_dist 
%         IR_angle 
%         r_agent 
%         targets 
%         target_status
%         target_radius
%         obstacles 
%         4
%         d_max
%         Q
%         S 
%         neighbour
%     end
% end
%% Plotting
% [AI-MOD 2026-11-05] RSFUZZ_DRAW=0 时跳过每步绘图（见文件头说明），计算逻辑不变
if RSFUZZ_DRAW
 plot(Q(2,:),Q(3,:),'db'); %plot quadrotor agents
 hold on;
 plot(Q(2,:),Q(3,:),'xb'); %plot quadrotor agents
 hold on;
 for j = 1:N
     rectangle('Position', [Q(2,j)-IR_dist,Q(3,j)-IR_dist,2*IR_dist,2*IR_dist], 'Curvature', [1 1],'EdgeColor', 'r');
     %viscircles([Q(2,j) Q(3,j)],IR_dist,'Color','r');
     axis equal
 end
 %plot(1.2,1.25,'sk','MarkerFaceColor','c'); %plot base location
end
 %% Crash detection
% [AI-MOD 2026-11-05] 上游用 "1:size(obstacles,2)/2-1" 排除"最后一个多边形"，其本意是排除攻击机
% 多边形（论文 §IV-B：攻击机撞受害机不计为失败）。但 easy 地图只有 1 个真实障碍，此时"最后一个"
% 恰好是真实障碍 -> 障碍撞击完全检测不到（na 基线会漏判判据②）。改为遍历全部障碍，按列号显式
% 跳过攻击机多边形；无攻击机时 rsfuzz_atk_col 未定义，跳过条件自然不成立。
 in_obstacles = cell(size(obstacles,2)/2,1);
 % for k = 1:size(obstacles,2)/2-1;
 for k = 1:size(obstacles,2)/2;
     if exist('rsfuzz_atk_col', 'var') && (2*k - 1) == rsfuzz_atk_col
         continue;   % 跳过攻击机多边形
     end
     in_obstacles{k} = inpolygon(Q(2,:),Q(3,:),obstacles{1,(2*k - 1)}(:),obstacles{1,(2*k)}(:));
     for b = find(in_obstacles{k}); %find agents in obstacles
         Q(1,b) = 3; %State = 3 (crashed, terminal state)
         display(t)
         filename_txt = 'ablation_result.txt'; % 文件名
         fid = fopen(filename_txt, 'a'); % 打开文件以供写入
         fprintf(fid, '%d\n', t); % 将变量的值写入文件
         fclose(fid); % 关闭文件
         error("集群无人机撞向障碍物")
         plot(Q(2,b),Q(3,b),'dk');
         plot(Q(2,b),Q(3,b),'xk');
     end
 end
 
 in_map = inpolygon(Q(2,:),Q(3,:),[1E-3 map_size map_size 1E-3],[1E-3 1E-3 map_size map_size]);  %find agents outside map boundary
 %in_map = inpolygon(Q(2,:),Q(3,:),[-2.5 2.5 2.5 -2.5],[-2.5 -2.5 2.5 2.5]);
  if ~in_map(:) == zeros(N,1)
      %all agents within map boundaries => do nothing
  else
      %find agents outside map boundaries => crash them
      for b = find(~in_map);
         Q(1,b) = 3; %State = 3 (crashed, terminal state)
         display(t)
         filename_txt = 'ablation_result.txt'; % 文件名
         fid = fopen(filename_txt, 'a'); % 打开文件以供写入
         fprintf(fid, '%d\n', t); % 将变量的值写入文件
         fclose(fid); % 关闭文件
         error("集群无人机撞向边界")
         plot(Q(2,b),Q(3,b),'dk');
         plot(Q(2,b),Q(3,b),'xk');
         axis equal
      end
  end

 %%collisions between drones
% [AI-MOD 2026-11-05] 论文 §IV-B 判据③"机间碰撞"应按失败处理，而上游只累加 countMatrix、从不判失败。
% 判据：任一对无人机 abs(dx)<=0.5 && abs(dy)<=0.5 即视为碰撞（上游阈值不变）。命中则按失败退出。
% 这里采用边沿触发（上一时刻未满足、本时刻满足），原因：advanced_agent_control.m 用
% linspace(0,2*pi,N) 生成初始航向，N=10 时首尾重复（0 与 2π），第 1、10 架机从一开始就同向同起点、
% 距离恒为 0 —— 若按"满足即失败"统计，任何一次运行都会在第一次检查（i=10）即判失败（实测 100%），
% 与论文报告的成功率明显矛盾。边沿触发只统计运行过程中新发生的接近，不影响"攻击导致碰撞"的语义。
% 攻击机撞受害机不计为失败。
if i >= 10
     rsfuzz_collision = false;
     rsfuzz_coll_now = false(N,N);
     for i = 1:N
         for j = (i+1):N
             if abs(Q(2,i) - Q(2,j))<=0.5&&abs(Q(3,i) - Q(3,j))<=0.5
                 countMatrix(i) = countMatrix(i) + 1;
                 rsfuzz_coll_now(i,j) = true;
                 if ~isempty(rsfuzz_coll_prev) && ~rsfuzz_coll_prev(i,j)
                     rsfuzz_collision = true;   % [AI-MOD 2026-11-05] 新发生的机间碰撞
                 end
             end
         end
     end
     rsfuzz_coll_prev = rsfuzz_coll_now;   % [AI-MOD 2026-11-05] 供下一时刻判边沿

    % disp(countMatrix);
    if rsfuzz_collision && RSFUZZ_COLLIDE
        filename_txt = 'ablation_result.txt'; % 与撞障碍一致：记录碰撞时刻，供 run_a2.m 判 crashed
        fid = fopen(filename_txt, 'a');
        fprintf(fid, '%d\n', t);
        fclose(fid);
        error("集群无人机之间发生碰撞")
    end
end


 %% More plotting
% [AI-MOD 2026-11-05] RSFUZZ_DRAW=0 时跳过（见文件头说明）
if RSFUZZ_DRAW
ho = text(map_size/20,map_size/20,strcat(num2str(t),'s'));
axis equal;
%axis([-2.6 2.6 -2.6 2.6]);
axis([0 map_size 0 map_size]);
xlabel('x (m)');
ylabel('y (m)');
for k = 1:size(obstacles,2)/2;
    facecolour = zeros(1,size(obstacles{1,(2*k - 1)}(:),1));
    patch((obstacles{1,(2*k - 1)}(:))',(obstacles{1,(2*k)}(:))',facecolour,'EdgeAlpha',0.2,'FaceColor','g','FaceAlpha',0.2);
    whitebg([1 1 1]);
end
end

%% Target search calculation and display
agents_inside = find(Q(1,:)==2); %find agents in State 2 - Search

for k = agents_inside; %cycle through each agent that has entered a target
    [entered_target,d_target] = dsearchn(targets',Q(2:3,k)');  %find which target is being searched
    if d_target <= target_radius; %double check agent is actually above target and not just in wrong FSA state
        target_status(entered_target,3) = target_status(entered_target,3) + 1;
    end
end

for k = 1:size(targets,2);
    target_status(k,1) = target_status(k,1) + (target_status(k,3)*R_search*dt);
    if target_status(k,1) < 1;
        if RSFUZZ_DRAW   % [AI-MOD 2026-11-05] 仅绘图受开关控制，搜索进度计算不变
        rectangle('Position',[targets(1,k)-target_radius targets(2,k)-target_radius 2*target_radius 2*target_radius],'Curvature',[1,1],'FaceColor','r');
        end
    else
        target_status(k,1) = 1;
        if isnan(target_status(k,2)) == 1;
            target_status(k,2) = t; %store time of target search completion
        end
        if RSFUZZ_DRAW   % [AI-MOD 2026-11-05] 同上
        rectangle('Position',[targets(1,k)-target_radius targets(2,k)-target_radius 2*target_radius 2*target_radius],'Curvature',[1,1],'FaceColor','w');
        end
    end
    if RSFUZZ_DRAW   % [AI-MOD 2026-11-05] 同上
    text((targets(1,k)+(map_size/100)),(targets(2,k)+(map_size/100)),strcat(num2str(100*target_status(k,1)),'%'));
    end
end

for k = agents_inside; %cycle through each agent that has entered a target
    [entered_target] = dsearchn(targets',Q(2:3,k)');  %find which target is being searched
    if target_status(entered_target,1) >= 1;    %check if target has 100% completion
        S(6,k) = 0; %target is 100% searched to reset target detection to 0 (allows transition to other state)
    end
end

%% [AI-MOD 2026-11-12] 数据采集插桩（复现回放 + 鲁棒度曲线用）。
%  只读取当前状态并写 trace 文件，不参与任何计算与判定；RSFUZZ_TRACE=0（默认）时
%  rsfuzz_trace 首个分支即 return，行为与原版逐位一致。
%  attack_agent_location / obstacles_list 只在攻击分支内定义（na 模式或 i<10 时不存在），
%  故用 exist 守卫，缺失时按"本步无攻击机"采集。
%  注意：上面判据③的循环复用了循环变量 i，本步不能用 i 作步号 —— rsfuzz_trace 内部
%  自带 persistent 计数器。
if RSFUZZ_TRACE
    try
        if exist('attack_agent_location', 'var') && exist('obstacles_list', 'var')
            rsfuzz_trace(t, Q, attack_agent_location, obstacles_list);
        else
            rsfuzz_trace(t, Q, [], {});
        end
    catch
        % [AI-MOD 2026-11-12] 采集异常一律吞掉：trace 只是旁路数据，
        % 绝不允许它中断仿真或改变结果（关闭开关时更不应有任何影响）。
    end
end

%% Save screengrab of Figure 1 as image

if sum(target_status(:,1)) == size(target_status,1);
% [AI-MOD 2026-11-05] RSFUZZ_DRAW=0 时不保存截图（批量实验用），退出条件 break 不变
if RSFUZZ_DRAW
name = strcat('Advanced_agent_control_completed_swarm_map',num2str(t),'s.bmp'); %create filename for screengrab
p = figure(1);
print(p,'-dbmp',name);  %save Figure(1) at time t as a bitmap image file
end

break

end    
% name = strcat('swarm_movie',num2str(t),'s.bmp'); %create filename for screengrab
% p = figure(1);
% print(p,'-dbmp',name);  %save Figure(1) at time t as a bitmap image file
%name = strcat('AAAAmedium_completed_swarm_map',num2str(t),'s.bmp'); %create filename for screengrab
%p = figure(1);
%print(p,'-dbmp',name);  %save Figure(1) at time t as a bitmap image file


%% Prepare for next time step
if RSFUZZ_DRAW   % [AI-MOD 2026-11-05] 未开 figure 时 hold off 会隐式建图，故一并关掉
hold off;
end
t = t + dt; %next time step
target_status;
end
