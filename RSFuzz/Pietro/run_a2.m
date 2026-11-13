function run_a2()
% [AI-MOD 2026-11-05] A2 (Pietro MATLAB 集群搜救算法) 单任务驱动脚本。
%
% 用途：把上游 easy/medium/hard_simulation_config.m + SA_Fuzzing.m / MA_Fuzzing.m 包装成
% "一次任务 = 一个进程"的批处理单元，读环境变量（由 repro/sched.py 注入），结束后写 result.json。
% 结构与 Howard/src/run_a3.m 保持一致（入口函数名由调度器固定为 run_a2）。
%   RSFUZZ_SEED   随机种子（论文要求同种子配对比较）
%   RSFUZZ_MODE   'na' 无攻击基线 | 'sa' SA-Fuzzing | 'ma' MA-Fuzzing
%   RSFUZZ_MAP    地图档位（缺省 easy，对应论文 Table II 的 easy 地图）
%   RSFUZZ_WORK   任务工作目录（隔离上游写出的崩溃时序文件）
%   RSFUZZ_OUT    结果输出目录
%   RSFUZZ_DRAW   '0' 关闭绘图（批量实验用）
%   RSFUZZ_PYTHON Python 解释器路径（A2 的攻击策略用 python 侧 attack.py）
%
% 失败判据（论文 §IV-B）：
%   ① 超过 2×CTime 仍未完成：t_end/dt 步跑完还没把所有目标搜索到 100%；
%   ② 撞障碍/撞地图边界（上游 error(...) + 崩溃时序文件）；
%   ③ 机间碰撞（上游只累加 countMatrix，已在 SA/MA_Fuzzing.m 中补为失败退出）。
%   攻击机撞受害机不计为失败（见 SA/MA_Fuzzing.m 的 Crash detection 注释）。

%% 1. 任务环境准备
rsfuzz_out = getenv('RSFUZZ_OUT');
if isempty(rsfuzz_out)
    error('RSFUZZ_OUT 未设置');
end
rsfuzz_work = getenv('RSFUZZ_WORK');
if isempty(rsfuzz_work)
    rsfuzz_work = pwd;
end
if ~exist(rsfuzz_work, 'dir')
    mkdir(rsfuzz_work);
end
cd(rsfuzz_work);

rsfuzz_src = fileparts(mfilename('fullpath'));   % Pietro/ 目录
addpath(rsfuzz_src);

rsfuzz_py = getenv('RSFUZZ_PYTHON');
if isempty(rsfuzz_py)
    rsfuzz_py = 'D:\Anaconda_envs\envs\py3.10\python.exe';
end
try
    pyenv('Version', rsfuzz_py);
catch
    % 已装载 Python 时忽略
end

rsfuzz_map = getenv('RSFUZZ_MAP');
if isempty(rsfuzz_map)
    rsfuzz_map = 'easy';
end
rsfuzz_mode = getenv('RSFUZZ_MODE');
if isempty(rsfuzz_mode)
    rsfuzz_mode = 'sa';
end
rsfuzz_seed = str2double(getenv('RSFUZZ_SEED'));
if isnan(rsfuzz_seed)
    rsfuzz_seed = 0;
end

% [AI-MOD 2026-11-05] 上游脚本在判据②③命中时向工作目录追加崩溃时刻文件，同目录重跑会读到
% 上一次的残留而误判 crashed。每次任务开始前先删除（与 run_a3.m 清日志同理）。
% 注意：变量名不能与下面（配置 clear 之后）继续使用的名字冲突，故这里用局部名。
rsfuzz_crashfiles_init = {'ablation_result.txt', 'MA_10_result.txt'};
for kk = 1:numel(rsfuzz_crashfiles_init)
    if exist(fullfile(rsfuzz_work, rsfuzz_crashfiles_init{kk}), 'file')
        delete(fullfile(rsfuzz_work, rsfuzz_crashfiles_init{kk}));
    end
end

rng(rsfuzz_seed);   % MATLAB 侧随机数（论文要求同种子配对比较）
try
    % [AI-MOD 2026-11-05] attack.py 用 np.random 采样候选攻击位置，必须同种子同步，
    % 否则同一 seed 的 sa/ma 结果不可复现。
    py.random.seed(int32(rsfuzz_seed));
    py.numpy.random.seed(int32(rsfuzz_seed));
catch
    % Python 未就绪时忽略，后续 py.attack 调用会给出明确报错
end

fprintf('[A2] mode=%s map=%s seed=%d python=%s\n', rsfuzz_mode, rsfuzz_map, rsfuzz_seed, rsfuzz_py);

%% 2. 载入地图配置
% [AI-MOD 2026-11-05] 用绝对路径 run，配合各 *_simulation_config.m 中基于 mfilename 的
% .mat 绝对路径加载，保证在任意工作目录下都能找到地图数据。
% 注意：medium/hard 的配置脚本首行有 clear，会清空本函数工作区（包括这里的局部变量），
% 所以配置阶段的错误先存到 root appdata，配置跑完后再取回。
setappdata(0, 'rsfuzz_cfg_err', '');
try
    run(fullfile(rsfuzz_src, [rsfuzz_map '_simulation_config.m']));
catch ME
    setappdata(0, 'rsfuzz_cfg_err', ME.message);
end

%% 3. 运行仿真
% medium/hard 配置里的 clear 会清空上面的局部变量，这里全部重新获取
rsfuzz_cfg_err = getappdata(0, 'rsfuzz_cfg_err');
rsfuzz_out = getenv('RSFUZZ_OUT');
rsfuzz_work = getenv('RSFUZZ_WORK');
if isempty(rsfuzz_work)
    rsfuzz_work = pwd;
end
rsfuzz_mode = getenv('RSFUZZ_MODE');
if isempty(rsfuzz_mode)
    rsfuzz_mode = 'sa';
end
rsfuzz_map = getenv('RSFUZZ_MAP');
if isempty(rsfuzz_map)
    rsfuzz_map = 'easy';
end
rsfuzz_seed = str2double(getenv('RSFUZZ_SEED'));
if isnan(rsfuzz_seed)
    rsfuzz_seed = 0;
end

rsfuzz_err = rsfuzz_cfg_err;
rsfuzz_wall = 0;
rsfuzz_crashfiles = {'ablation_result.txt', 'MA_10_result.txt'};   % 配置 clear 之后需要重新定义
if isempty(rsfuzz_cfg_err)
    % [AI-MOD 2026-11-05] 论文 §IV-B 判据①：任务耗时超过 2×CTime 即失败。上游 t_end=1000 s
    % （easy 档）远大于 2×CTime，超时永远不会触发；这里允许用 RSFUZZ_MAXT 注入 2×实测 CTime，
    % 只截短仿真时长，不改任何运动/判定逻辑。
    rsfuzz_maxt = str2double(getenv('RSFUZZ_MAXT'));
    if ~isnan(rsfuzz_maxt) && rsfuzz_maxt > 0 && rsfuzz_maxt < t_end
        rsfuzz_tend_orig = t_end;
        t_end = rsfuzz_maxt;
        fprintf('[A2] t_end: %g -> %g (RSFUZZ_MAXT, 判据① 2×CTime)\n', rsfuzz_tend_orig, t_end);
    end
    rsfuzz_t0 = tic;
    try
        if strcmp(rsfuzz_mode, 'ma')
            MA_Fuzzing;
        else
            SA_Fuzzing;   % 'sa' 与 'na'（脚本内 RSFUZZ_ATTACK=0）共用同一脚本
        end
    catch ME
        rsfuzz_err = ME.message;
    end
    rsfuzz_wall = toc(rsfuzz_t0);
end

%% 4. 采集判据所需的仿真状态（脚本共享工作区，出错时变量仍保留）
rsfuzz_t = NaN;
rsfuzz_steps = NaN;
rsfuzz_n = NaN;
rsfuzz_arrived = false;
rsfuzz_timeout = false;

if exist('t', 'var')
    rsfuzz_t = t;
end
if exist('dt', 'var') && exist('t0', 'var') && isfinite(rsfuzz_t)
    rsfuzz_steps = round((rsfuzz_t - t0) / dt);   % 实际执行的步数（dt 步长与 t0 起点来自配置）
end
if exist('N', 'var')
    rsfuzz_n = N;
end
if exist('target_status', 'var') && ~isempty(target_status)
    rsfuzz_arrived = all(target_status(:,1) >= 1);   % 所有目标搜索进度 100%
end
if exist('t_end', 'var') && isfinite(rsfuzz_t)
    % 判据①：步数配额（t_end/dt）耗尽仍未搜完 -> 超时（2×CTime 的上限由上游 t_end=100s 给定）
    rsfuzz_timeout = ~rsfuzz_arrived && rsfuzz_t >= t_end;
end

rsfuzz_crashed = false;
if ~isempty(rsfuzz_err)
    rsfuzz_crashed = contains(rsfuzz_err, '撞向障碍物') || contains(rsfuzz_err, '撞向边界') ...
        || contains(rsfuzz_err, '碰撞');
end
for kk = 1:numel(rsfuzz_crashfiles)
    if exist(fullfile(rsfuzz_work, rsfuzz_crashfiles{kk}), 'file')
        rsfuzz_crashed = true;   % 上游在判据②③命中时写出的时序文件
    end
end

rsfuzz_failed = rsfuzz_crashed || rsfuzz_timeout || ~rsfuzz_arrived || ~isempty(rsfuzz_err);

%% 5. 输出 result.json
% jsonencode 不接受 NaN，缺失值统一用 [] （编码为 null）
if isnan(rsfuzz_t), rsfuzz_t = []; end
if isnan(rsfuzz_steps), rsfuzz_steps = []; end
if isnan(rsfuzz_n), rsfuzz_n = []; end

rec = struct('algo', 'A2', 'mode', rsfuzz_mode, 'seed', rsfuzz_seed, 'map', rsfuzz_map, ...
    'n', rsfuzz_n, 'failed', rsfuzz_failed, 'crashed', rsfuzz_crashed, ...
    'timeout', rsfuzz_timeout, 'arrived', rsfuzz_arrived, ...
    'steps', rsfuzz_steps, 'sim_time', rsfuzz_t, ...
    'wall_s', round(rsfuzz_wall * 100) / 100, 'error', rsfuzz_err);

if ~exist(rsfuzz_out, 'dir')
    mkdir(rsfuzz_out);
end
fid = fopen(fullfile(rsfuzz_out, 'result.json'), 'w');
fprintf(fid, '%s', jsonencode(rec));
fclose(fid);
fprintf('RESULT %s\n', jsonencode(rec));
end
