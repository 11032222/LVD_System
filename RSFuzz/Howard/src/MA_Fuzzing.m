%% Test Swarm Trajectory in 3-D
% Author: Zhou Ruoyu
% Date   : 7/31/2024
% Info    : This is a script developed to show the swarm navigation
% algorithms in 3-D. This script also allows for the user to specify
% various waypoints so that they can maneuver around a space

clear all;
warning("off")
false = 0;
true = 1;

% [AI-MOD 2026-11-05] 与 SA_Fuzzing.m 相同的批量复现入口（种子/规模/绘图/攻击链开关）。
% 论文 §IV-B：同一种子下成对比较基线与本算法；A3 规模 6/8/10。
rsfuzz_seed = getenv('RSFUZZ_SEED');
if isempty(rsfuzz_seed)
    rng('shuffle');
else
    rng(str2double(rsfuzz_seed));
end
rsfuzz_nd = getenv('RSFUZZ_ND');
if isempty(rsfuzz_nd)
    RSFUZZ_Nd = 1+9;             % 与上游默认规模一致
else
    RSFUZZ_Nd = str2double(rsfuzz_nd);
end
rsfuzz_mode = getenv('RSFUZZ_MODE');
RSFUZZ_ATTACK = ~strcmp(rsfuzz_mode, 'na');
RSFUZZ_DRAW = ~strcmp(getenv('RSFUZZ_DRAW'), '0');
% [AI-MOD 2026-11-12] 数据采集开关（与 SA_Fuzzing.m 一致）：关闭时 rsfuzz_trace 立即 return。
RSFUZZ_TRACE = strcmp(getenv('RSFUZZ_TRACE'), '1');
% [AI-MOD 2026-11-05] 论文 §IV-B 判据①：任务耗时超过正常完成时间 CTime 的 2 倍即失败。
% 上游把迭代上限写死 150，改为可注入；缺省仍为 150，正式实验按本机实测 2×CTime 设置。
RSFUZZ_MAXIT = str2double(getenv('RSFUZZ_MAXIT'));
if isnan(RSFUZZ_MAXIT)
    RSFUZZ_MAXIT = 150;
end
RSFUZZ_LINK = strcmp(getenv('RSFUZZ_A3_LINK'), '1');

%% Setup the movie stuff
make_movie = false;
make_pot     = false; % make video showing potential field | Takes a LONG time to make, so usually set to false
writerObj = [];

%% Define the plane of points to evaluate potential function, if you are making video of potential function
x = linspace(0, 50, 100);
y = linspace(0, 50, 100);
z = 5;

[X,Y] = meshgrid(x,y);
[rx, cx] = size(X);
Z = zeros(rx, cx);

%% Setup the movie file and frame rate
if( make_movie )
    writerObj = VideoWriter('test_fuzzer.avi');
    writerObj.FrameRate = 15;
    open(writerObj);
end

% initial perspective in video
az = -60;
el = 20;

% final perspective in video
azf = -60;
elf = 20;

%%  Parameter specifications for drones
% Nd = 1+9;                    % number of drones in swarm
Nd = RSFUZZ_Nd;               % [AI-MOD 2026-11-05] 由环境变量注入（论文 A3: 6/8/10）
ind_c = -1;                       % index for center/lead drone
radius = 2;                     % radius for drones and possibly obstacles
dims = [0, 50; 0, 50; 0, 50]; % first row is lower and upper x bounds
                                                  % second row is lower and upper y bounds
                                                  % third row is lower and upper z bounds
xc = [40, 40, 40]'; % initial location for central/lead drone
end_loc = [5, 5, 5]'; % Desired end location

%% Setup the waypoint object
dist_thresh = 2; % The distance threshold the swarm must be within of the waypoint
                           % to make the waypoint change to the new one
droneWaypoints = [];
copyWaypoints = [];

% 编队几何与取值理由见 SA_Fuzzing.m：上下两层环形（xy 半径 2.0 m、z 偏移 ±1.5 m），
% 间距既大于 dist_thresh=2 也大于斥力半径 2，且 xy 足迹小、避开 [0,10]^3 的随机障碍簇。
rsfuzz_indep = strcmp(getenv('RSFUZZ_WAYPOINTS'), 'indep');
rsfuzz_ring = 2.0;     % 编队环半径（水平面内）
rsfuzz_h = 1.5;        % 上下两层各自的 z 偏移
rsfuzz_goal = zeros(3, Nd);     % 每架无人机的终点（shared 时全部等于 end_loc）
rsfuzz_off_arr = zeros(3, Nd);  % 每架无人机相对集群航点的偏移（shared 时全零）
if rsfuzz_indep
    rsfuzz_nlayer = ceil(Nd/2);              % 每层架数
    for i = 1:Nd
        rsfuzz_layer = mod(i-1, 2);          % 0 = 下层, 1 = 上层
        rsfuzz_k = floor((i-1)/2);           % 层内序号（从 0 开始）
        rsfuzz_th = 2*pi*rsfuzz_k/rsfuzz_nlayer;
        rsfuzz_off_arr(:, i) = [rsfuzz_ring*cos(rsfuzz_th); ...
                                rsfuzz_ring*sin(rsfuzz_th); ...
                                (2*rsfuzz_layer - 1)*rsfuzz_h];
    end
end

for i = 1:Nd
    wypt = Waypoints( dist_thresh );
    
    % Add waypoint structure to drone waypoint structure
    % The drone waypoint structure represents individual waypoints for each
    % drone, so they don't have to move in the same direction. 
    droneWaypoints(i).w = wypt;
    
    wypt2 = Waypoints( dist_thresh ); % copy waypoints for use in plotting waypoints
    
    % Add waypoint structure to copy waypoint structure
    copyWaypoints(i).w = wypt2;
    
end

% Initialize the waypoints 
% For simplicity in this example, will initilize waypoint paths to be the
% same thing for each drone. 
pt1 = [15;50;20];
pt2 = [0; 50; 0];
pt3 = end_loc;

for i = 1:Nd
    
    % [AI-MOD 2026-11-09] indep：本机航点按上方 rsfuzz_off_arr 的编队偏移错开；
    % shared 时偏移为零，与上游共享航点逐位等价。
    rsfuzz_off = rsfuzz_off_arr(:, i);
    rsfuzz_goal(:, i) = pt3 + rsfuzz_off;
    
    % 原代码（共享航点）：
    % droneWaypoints(i).w.addPoint( pt1 );
    % droneWaypoints(i).w.addPoint( pt2 );
    % droneWaypoints(i).w.addPoint( pt3 );
    droneWaypoints(i).w.addPoint( pt1 + rsfuzz_off );
    droneWaypoints(i).w.addPoint( pt2 + rsfuzz_off );
    droneWaypoints(i).w.addPoint( pt3 + rsfuzz_off );
    
    % [AI-MOD 2026-11-09] 绘图用的副本航点与真实航点保持一致（仅 RSFUZZ_DRAW=1 时可见）
    copyWaypoints(i).w.addPoint( pt1 + rsfuzz_off );
    copyWaypoints(i).w.addPoint( pt2 + rsfuzz_off );
    copyWaypoints(i).w.addPoint( pt3 + rsfuzz_off );

end

%% Parameter specifications for the obstacles
No = 7;
i = 1;
% obst = [50, 15, 25];
obst = [Obstacle([20, 50, 25],4), Obstacle([10, 30, 0],4), Obstacle([10, 50, 10],4)];
dims_o = [0, 10; 0, 10; 0, 10]; % first row is lower and upper x bounds
                                      % second row is lower and upper y bounds
while( i <= No )
    %randomly generate position of obstacle within bounds
    pos = rand(3,1).*( dims_o(:,2)-dims_o(:,1) ) + dims_o(:,1);
    
    % Add new obstacle to obstacle array obst
    obst = [obst, Obstacle(pos,radius)];
    i = i + 1;
end

%% Create drones and obstacle arrays
i = 1;
drones = [];
while( i <= Nd )
    if( i == ind_c )
        % Add lead drone to drone array
        drones = [drones, Drone(radius, xc , 2)];
    else
        % Add a follower drone to drone array
        % [AI-MOD 2026-11-09] indep：改用与独立航点同一环形偏移的编队初始位置
        % （上游随机初值会让无人机一开始就落入 1 m 机间阈值）。
        if rsfuzz_indep
            pos = xc + rsfuzz_off_arr(:, i);   % 编队初值（与各自终点一一对应）
        else
            DEL = [xc - 5, xc + 5]; % make swarm initialize around lead drone randomly
            pos = rand(3,1).*( DEL(:,2)-DEL(:,1) ) + DEL(:,1);
        end
        drones = [drones, Drone(radius, pos, 1)];
    end
    i = i + 1;
end
% Define the attack drone
% Generate a random position near the lead drone
% DEL_attack = [drones(5).pos - 5, drones(5).pos + 5]; % Range for attack drone to initialize around lead drone
% [AI-MOD 2026-11-05] 原代码固定取第 5 架，规模 Nd<5 时越界；改为末架，语义不变。
DEL_attack = [drones(end).pos - 5, drones(end).pos + 5]; % Range for attack drone to initialize around lead drone
pos_attack = rand(3,1).*( DEL_attack(:,2)-DEL_attack(:,1) ) + DEL_attack(:,1);
attackdrone = Drone(5, pos_attack, 3); % Example initial position for attack drone

% [AI-MOD 2026-11-05] A3 攻击链开关（说明见 SA_Fuzzing.m）：1 时攻击机进入集群避让势场。
% Drone 与 Obstacle 不可直接拼接，改为在迭代内构造随攻击机位置更新的 Obstacle。
rsfuzz_obst_ctrl = obst;


%% Setup figure traits for the movie
% [AI-MOD 2026-11-05] RSFUZZ_DRAW=0 时关闭全部绘图（批量实验用）
if RSFUZZ_DRAW
close all;
h = figure('Position', [10, 10, 1000, 800]);
set(gca,'nextplot','replacechildren');
set(gcf,'Renderer','zbuffer');
end
dims2 = dims';

%% Do the initial drawing
i = 1;

if RSFUZZ_DRAW
figure(1)
N = 1;
if( make_pot )
    N = 2;
end

subplot(1,N,1)
while( i <=Nd ) % loop through drones
    drawObject(drones(i));
    if( i == 1 )
        hold on
    end
    i = i + 1;
end
drawObject(attackdrone);


i = 1;
while( i <= No ) % loop through obstacles
    drawObject(obst(i));
    i = i + 1;
end
hold off
grid on
view(az, el)
axis(dims2(:))
end
xpos = [];

%% Do iterations of the drone moving to final location
it = 1;
count = 0;
done = 0;
% 结果目录与日志文件（按无人群数量Nd命名；不含攻击机）
if ~exist('./Result','dir')
    mkdir('./Result');
end
logfile = sprintf('./Result/iteration_log_%d.txt', Nd);
fileID = fopen(logfile, 'a');
while( done == 0 )
    % [AI-MOD 2026-11-05] 每次迭代按攻击机当前位置重建集群避让集合（见上方 RSFUZZ_LINK 说明）
    if RSFUZZ_LINK
        rsfuzz_obst_ctrl = [obst, Obstacle(attackdrone.pos, attackdrone.radius)];
    else
        rsfuzz_obst_ctrl = obst;
    end
    i = 1;
    
    % Compute new locations
    while( i <= Nd )
        pt = droneWaypoints(i).w.getWaypoint( drones(i).pos );
        % drones(i).pos = drones(i).pos + GradientDescentUpdate(drones(i).pos, i, drones, obst, pt );
        % [AI-MOD 2026-11-05] 按 RSFUZZ_A3_LINK 决定攻击机是否进入集群避让势场
        drones(i).pos = drones(i).pos + GradientDescentUpdate(drones(i).pos, i, drones, rsfuzz_obst_ctrl, pt );

        if( count > 20 || it >= RSFUZZ_MAXIT )   % [AI-MOD] 原 it >= 150，改为可注入上限
            done = 1;
            fprintf(fileID, 'Iteration stopped because it reached the limit: %d\n', it);
        end
        i = i + 1;
    end

    % [AI-MOD 2026-11-05] 任务完成判据，说明见 SA_Fuzzing.m（全部无人机进入终点的
    % dist_thresh 范围即完成，用于测量论文 §IV-B 的 CTime）。
    % [AI-MOD 2026-11-09] indep：每架无人机各自有终点，完成判据改为“每架进入自己终点
    % 的 dist_thresh 范围”；shared（默认）仍以共享终点 end_loc 判定。
    if rsfuzz_indep
        rsfuzz_all_in = true;
        for i = 1:Nd
            if norm(drones(i).pos - rsfuzz_goal(:, i)) > dist_thresh
                rsfuzz_all_in = false;
                break;
            end
        end
    else
        rsfuzz_all_in = all(arrayfun(@(d) norm(d.pos - end_loc), drones) <= dist_thresh);
    end
    if rsfuzz_all_in && done == 0
        fprintf(fileID, 'GoalReached: %d\n', it);
        done = 1;
    end
    
    % Draw drones in new position
    i = 1;
    
    if RSFUZZ_DRAW   % [AI-MOD 2026-11-05] 批量实验关闭每帧重绘
    figure(1)
    subplot(1,N,1)
    
    while( i <= Nd ) % loop through drones
        drawObject(drones(i));
        if( i == 1 )
            hold on
        end
        i = i + 1;
    end
    drawObject(attackdrone);
    i = 1;
    while( i <= Nd )
        drawWaypoints( copyWaypoints(i).w );
        i = i + 1;
    end
    
    i = 1;
    while( i <= No ) % loop through obstacles
        drawObject(obst(i));
        i = i + 1;
    end
    hold off
    coef = it/100;
    
    %zoom(2)
    grid on
    axis(dims2(:))
    view(az + coef*(azf - az) , el + coef*(elf - el) )
    %rotate(h, [0, 0, 1], 1)
    pause(.01)
    end   % [AI-MOD 2026-11-05] 结束 RSFUZZ_DRAW 绘图块
    
    % Add frame to movie, if you are wanting to make the movie
    if( make_movie && it > 3 )
        ind = 1;
        if( N > 1 )
            subplot(1, N, 2)
            ind = 1;
            for ii = 1:rx
                for jj = 1:cx
                    Z(ii, jj) = getTotalPotential( [X(ii,jj); Y(ii, jj); z(1)], ind, drones, obst, end_loc );
                end
            end
            
            surf(X,Y,Z)
            axis( [x(1), x(end), y(1), y(end)] )
        end
        
        
        frame = getframe(gcf);
        writeVideo(writerObj,frame);
    end
    
    % Monitor the drones and obstacles
    success = Monitor(drones, obst, end_loc, 20);
    if success
        disp('Collision detected or target not reached!');
        % [AI-MOD 2026-11-05] 失败归因日志（说明见 SA_Fuzzing.m），不影响仿真与判定。
        rsfuzz_min_obst = inf;
        for a = 1:numel(drones)
            for o = 1:numel(obst)
                rsfuzz_min_obst = min(rsfuzz_min_obst, norm(drones(a).pos - obst(o).pos));
            end
        end
        rsfuzz_min_dd = inf;
        for a = 1:numel(drones)
            for b = (a+1):numel(drones)
                rsfuzz_min_dd = min(rsfuzz_min_dd, norm(drones(a).pos - drones(b).pos));
            end
        end
        fprintf(fileID, 'FailureReason: min_obst_dist=%.4f min_drone_dist=%.4f\n', rsfuzz_min_obst, rsfuzz_min_dd);
        fprintf(fileID, 'Iteration stopped because of fuzzing success: %d\n', it);
        % done = 1;
        break;
    end
    
    % Test fuzzer function
    % drones_vel = [5,5,5,5,5,5,5,5,5,5];
    % [AI-MOD 2026-11-05] 速度向量按实际规模生成（原代码写死 10 个分量，Nd≠10 时越界）
    drones_vel = 5 * ones(1, Nd);
    if RSFUZZ_ATTACK
        attack_pos = MA_fuzzer(attackdrone, drones, obst, end_loc, it, drones_vel);
        attackdrone.pos = attack_pos;
        % 计算并记录鲁棒性
        rob_val = Robustness(attackdrone, drones, obst, end_loc, it, drones_vel);
        fprintf(fileID, '[%f, %f, %f, %f]\n', attack_pos(1), attack_pos(2), attack_pos(3), rob_val);
        fprintf('[%f, %f, %f, %f]\n', attack_pos(1), attack_pos(2), attack_pos(3), rob_val);
    else
        % [AI-MOD] 无攻击基线（论文 Table II "Failure w/o attack"）
        attack_pos = attackdrone.pos;
        fprintf(fileID, '[%f, %f, %f, %f]\n', attack_pos(1), attack_pos(2), attack_pos(3), 0);
    end
    
    %% [AI-MOD 2026-11-12] 数据采集插桩（与 SA_Fuzzing.m 一致）：只读状态写 trace，
    %  不参与任何计算与判定；关闭开关时 rsfuzz_trace 立即 return。
    if RSFUZZ_TRACE
        try
            if RSFUZZ_ATTACK
                rsfuzz_trace(it, drones, attack_pos, rob_val, obst, dims, rsfuzz_goal);
            else
                rsfuzz_trace(it, drones, [], [], obst, dims, rsfuzz_goal);
            end
        catch
            % 采集异常一律吞掉，绝不允许影响仿真结果
        end
    end

    it = it + 1;
end
% 关闭文件
% [AI-MOD 2026-11-05] 记录收尾距离，供 run_a3.m 判定“是否在时限内到达目标”（论文判据①）
% [AI-MOD 2026-11-09] indep：收尾距离改为“到本机自己的终点”；shared 仍为到 end_loc。
if rsfuzz_indep
    rsfuzz_final_dist = zeros(1, Nd);
    for i = 1:Nd
        rsfuzz_final_dist(i) = norm(drones(i).pos - rsfuzz_goal(:, i));
    end
else
    rsfuzz_final_dist = arrayfun(@(d) norm(d.pos - end_loc), drones);
end
fprintf(fileID, 'FinalDistToGoal: max=%.4f mean=%.4f within2=%d within01=%d total=%d\n', ...
        max(rsfuzz_final_dist), mean(rsfuzz_final_dist), ...
        sum(rsfuzz_final_dist <= dist_thresh), sum(rsfuzz_final_dist <= 0.1), numel(rsfuzz_final_dist));
fclose(fileID);
error('Complete!');
%% Close movie file, if you are recording a movie
if( make_movie )
    close(writerObj);
end
error('Complete!');