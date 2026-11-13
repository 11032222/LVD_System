%% Configuration file for quadrotor_swarm.m
%Enter simulation parameter values below
% N = 10;         %number of agents
% [AI-MOD 2026-11-09] 论文 Table II 的 A2 规模档为 10/15/20；改为读 batch 注入的 RSFUZZ_N，
% 未设置时保持上游默认 10（等价于原行为）。
rsfuzz_n_env = getenv('RSFUZZ_N');
if isempty(rsfuzz_n_env)
    N = 10;     %number of agents
else
    N = str2double(rsfuzz_n_env);
end
t0 = 0;         %initial time (s)
t_end = 1000;     %end time (s)
timer = 1;    %agent timer s(1) / S(1,j). Can be used to transition from initial state
dt = 5e-1;      %simulation time step (s)

%Try to keep values below unchanged
r_agent = 2;    %nearby agent detection/communication radius (m)
IR_angle = pi/4; %infrared proximity sensor angle
IR_dist = 2;    %infrared proximity sensor range (m)
target_radius = 1;    %radius of target(s)
v_max = 2;      %max quadcopter velocity (m/s)
d_max = v_max*dt; %maximum agent travel displacement per time step
% Check time step is sufficiently small:
if d_max >= IR_dist
    disp('Warning: time step too large, may cause agents to crash into obstacles')    
end
R_search = 0.02; %target search rate (/s)
%%Attack
attack_agent_location = [5 5];
attack_agent_v = 1;

%% Terrain/obstacle properties

map_type = 0;   % = 0 for standard map, = 1 for custom map

if map_type == 0;
    % [AI-MOD 2026-11-05] 上游用相对当前目录的 load('easy_obstacles.mat')。批量复现时每个任务会
    % cd 到独立工作目录（RSFUZZ_WORK），相对路径就找不到数据文件。改为基于本配置文件自身目录
    % 的绝对路径加载（.mat 与配置同目录），在任意 cwd 下都可复现。
    % load easy_obstacles.mat;
    % load easy_targets.mat;
    rsfuzz_cfg_dir = fileparts(mfilename('fullpath'));
    load(fullfile(rsfuzz_cfg_dir, 'easy_obstacles.mat'));
    load(fullfile(rsfuzz_cfg_dir, 'easy_targets.mat'));
    %load obstacles_standard.mat;  %rename as map_standard.mat or similar
    %load targets_standard.mat;
    map_size = 25;
else
    [map_size] = map_maker(1); 
    load easy_obstacles.mat;
    load easy_targets.mat;
end
