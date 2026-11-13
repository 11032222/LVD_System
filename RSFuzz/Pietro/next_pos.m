function New_Q = next_pos(t, map_size, IR_dist, IR_angle, r_agent, targets, ...
                         target_status, target_radius, obstacles, N, d_max, ...
                         Q_in, S_in, neighbour)
% [AI-MOD 2026-11-05] 上游仓库缺失该文件（Pietro/SA_Fuzzing.m 第 62 行调用了 next_pos，
% MA_Fuzzing.m 中同一行是注释掉的，即快照里漏提交了这个函数）。这里按其调用签名补齐：
%
%   next_pos(t, map_size, IR_dist, IR_angle, r_agent, targets, target_status,
%            target_radius, obstacles, N, d_max, Q, S, neighbour)
%
% 语义（依据论文 §III-C3 与 SA-Fuzzing 的候选筛选流程）：
%   "For each candidate position, it simulates the swarm's next state" —— 对每个候选攻击机
%   位置，把该候选位置当成障碍物（由调用方放入 obstacles），预演一步集群状态，供调用方判断
%   集群是否会撞上候选攻击机。因此本函数**只做一次预演**，返回 New_Q，不修改调用方的 Q/S。
%
% 实现：把 SA_Fuzzing.m 主循环里 "IR 传感器 / 障碍检测 / 边界检测 / 最近邻 / 目标接近 /
% advanced_agent_control" 那段计算原样搬到这里（含相同的传感器索引与更新顺序），
% 唯一差别是把 polyxpoly 换成 rsfuzz_polyxpoly（本机无 Mapping Toolbox）。
% advanced_agent_control 需要读取 global Q/S 中邻居的状态，所以预演期间临时把 global 置为
% 拷贝，结束后恢复原值。
%
% 注：输入参数 Q_in / S_in 对应上游调用签名里的 Q / S（改名是为了能与 global Q/S 共存）；
%     参数 neighbour 仅为签名兼容保留——本函数内部会按主循环同样的规则重新计算最近邻。

global Q S

Q_prev = Q;
S_prev = S;

% 在拷贝上预演，避免污染调用方状态
Q = Q_in;
S = S_in;

%% Calculate sensor values for current position of agent j
for j = 1:N    %cycle through swarm of agents

    %% Define IR sensors
    %Left/right IR proxity sensors
    IR_right = [Q(2,j) (Q(2,j)+IR_dist*cos(Q(4,j))) (Q(2,j)+IR_dist*cos(Q(4,j)-IR_angle)) Q(2,j); Q(3,j) (Q(3,j)+IR_dist*sin(Q(4,j))) (Q(3,j)+IR_dist*sin(Q(4,j)-IR_angle)) Q(3,j)];
    IR_left = [Q(2,j) (Q(2,j)+IR_dist*cos(Q(4,j))) (Q(2,j)+IR_dist*cos(Q(4,j)+IR_angle)) Q(2,j); Q(3,j) (Q(3,j)+IR_dist*sin(Q(4,j))) (Q(3,j)+IR_dist*sin(Q(4,j)+IR_angle)) Q(3,j)];
    S(2,j) = 0; %reset right IR sensor value to 0
    S(3,j) = 0; %reset left IR sensor value to 0

    %% Obstacle detection
    for k = 1:size(obstacles,2)/2
        % [AI-MOD 2026-11-05] 2026-11-05 已装 Mapping Toolbox 24.2（R2024b），恢复上游 polyxpoly 调用
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
        if  IR_detect
             S(2,j) = 1; %map boundary detected right, set right IR sensor to 1
        end
    [IR_detect] = polyxpoly(IR_left(1,:),IR_left(2,:),[1E-3; 1E-3; map_size; map_size; 1E-3],[1E-3; map_size; map_size; 1E-3; 1E-3]);
    % [IR_detect] = rsfuzz_polyxpoly(IR_left(1,:),IR_left(2,:),[1E-3; 1E-3; map_size; map_size; 1E-3],[1E-3; map_size; map_size; 1E-3; 1E-3]);

    %% Detect nearby agent
    % dseachn function is used to find nearest agent
    % neighbour is the index of the nearest agent
    % d_agent is the distance to the nearest agent
    if j == 1
        [nb,d_agent] = dsearchn(Q(2:3,2:N)',Q(2:3,j)');
    elseif j == N
        [nb,d_agent] = dsearchn(Q(2:3,(1:(j-1)))',Q(2:3,j)');
    else
        [nb,d_agent] = dsearchn(Q(2:3,[(1:(j-1)) ((j+1):N)])',Q(2:3,j)');
    end

    if nb >= j
        nb = nb + 1;  %ensure neighbour index is correct
    end

    if d_agent <= r_agent; %neighbouring agent is not within communication range
        S(9,j) = 1;         %agent detection set to 1 in sensor array
        S(10,j) = d_agent;  %agent-agent distance input to sensor array
        S(11,j) = acos((Q(2,nb)-Q(2,j))/d_agent);   %agent-agent angle input to sensor array
        if (Q(3,nb)-Q(3,j)) < 0
            S(11,j) = S(11,j)*-1; %ensure angle sign is correct
        end
    else    %neighbouring agent is not within communication range
        S(9,j) = 0; %agent detection set to 0 in sensor array
        S(10,j) = 0; %non-existent agent-agent distance input to sensor array
        S(11,j) = 0; %non-existent agent-agent angle input to sensor array
        nb = NaN;  %nearby agent is out of communcation range so cannot be accessed in agent_control.m
    end

    %% Proximity to target
    S(6,j) = 0; %reset target sensor value to 0
    [nearby_target,d_target] = dsearchn(targets',Q(2:3,j)');

    if target_status(nearby_target,1) < 1
        if d_target <= target_radius;   %target is detectable
            S(6,j) = 1; %set target sensor value to 1
            S(7,j) = d_target;
            if Q(2,j) >= targets(1,nearby_target) && Q(3,j) >= targets(2,nearby_target)
                 S(8,j) = acos(abs(targets(1,nearby_target)-Q(2,j))/d_target)+pi;
            elseif Q(2,j) <= targets(1,nearby_target) && Q(3,j) >= targets(2,nearby_target)
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
    [Q(:,j)] = advanced_agent_control(t,j,N,d_max,Q(:,j),S(:,j),nb);    %run agent_control sub-function for agent j
    S(4,j) = sqrt((pos_old(1) - Q(2,j))^2 + (pos_old(2) - Q(3,j))^2);  %enter agent translation distance into sensor array
    S(5,j) = Q(4,j); %enter agent theta into sensor array
end

New_Q = Q;

% 恢复调用方状态（本函数只做预演）
Q = Q_prev;
S = S_prev;
end
