%% Configuration file for quadrotor_swarm.m
%Enter simulation parameter values below
clear
N = 15;         %number of agents
t0 = 0;         %initial time (s)
t_end = 2000;     %end time (s)
timer = 1;    %agent timer s(1) / S(1,j). Can be used to transition from initial state
dt = 5e-1;      %simulation time step (s)

%Try to keep values below unchanged
r_agent = 2;    %nearby agent detection/communication radius (m)
IR_angle = pi*2; %infrared proximity sensor angle
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
attack_agent_location = [25 25];
attack_agent_v = 2;
number = 10;
%% Terrain/obstacle properties

map_type = 0;   % = 0 for standard map, = 1 for custom map

if map_type == 0;
    % [AI-MOD 2026-11-05] 与 easy_simulation_config.m 同一处修复：批量任务会 cd 到独立工作目录，
    % 相对路径 load 会找不到 .mat。改为基于本配置文件自身目录的绝对路径。
    % load hard_obstacles.mat;
    % load hard_targets.mat;
    rsfuzz_cfg_dir = fileparts(mfilename('fullpath'));
    load(fullfile(rsfuzz_cfg_dir, 'hard_obstacles.mat'));
    load(fullfile(rsfuzz_cfg_dir, 'hard_targets.mat'));
    %load obstacles_standard.mat;  %rename as map_standard.mat or similar
    %load targets_standard.mat;
    map_size = 50;
else
    [map_size] = map_maker(1); 
    load hard_obstacles.mat;
    load hard_targets.mat;
end
