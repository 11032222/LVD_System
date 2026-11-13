function run_a3()
% [AI-MOD 2026-11-05] A3 (Howard 3D swarm) 单任务驱动脚本。
%
% 用途：把上游 SA_Fuzzing.m / MA_Fuzzing.m 包装成“一次任务 = 一个进程”的批处理单元，
% 读取环境变量（由 repro/sched.py 注入），结束后写出 result.json，供统一统计。
%   RSFUZZ_SEED   随机种子（论文要求同种子配对比较）
%   RSFUZZ_MODE   'na' 无攻击基线 | 'sa' SA-Fuzzing | 'ma' MA-Fuzzing
%   RSFUZZ_ND     集群规模（论文 A3: 6/8/10）
%   RSFUZZ_WORK   任务工作目录（隔离 Result/ 与日志）
%   RSFUZZ_OUT    结果输出目录
%   RSFUZZ_DRAW   '0' 关闭绘图（批量实验用）
%
% 失败判据（论文 §IV-B）：①未在 2×CTime 内到达目标 ②撞障碍 ③机间碰撞。
% 上游脚本在 ②③ 发生时打印 "fuzzing success" 并 break；①对应 150 次迭代截断
% （A3 正常完成约 67 次迭代，150 ≈ 2×CTime）。是否到达目标由日志中的
% FinalDistToGoal 判定（集群全部进入 dist_thresh=2 视为到达）。

rsfuzz_out = getenv('RSFUZZ_OUT');
if isempty(rsfuzz_out)
    error('RSFUZZ_OUT 未设置');
end
rsfuzz_work = getenv('RSFUZZ_WORK');
if ~isempty(rsfuzz_work)
    if ~exist(rsfuzz_work, 'dir'), mkdir(rsfuzz_work); end
    cd(rsfuzz_work);
end

% 本机 Python 环境（论文 A2/A3 的 Python 侧模块）
rsfuzz_py = getenv('RSFUZZ_PYTHON');
if isempty(rsfuzz_py)
    rsfuzz_py = 'D:\Anaconda_envs\envs\py3.10\python.exe';
end
try
    pyenv('Version', rsfuzz_py);
catch
    % 已设置或不可用时忽略，后续 katz 调用会走 MATLAB 侧降级逻辑
end

rsfuzz_src = fileparts(mfilename('fullpath'));
addpath(rsfuzz_src);

% [AI-MOD 2026-11-05] 上游 SA_Fuzzing/MA_Fuzzing 以追加模式 ('a') 打开 Result/iteration_log_<Nd>.txt。
% 同一工作目录重跑会累积旧日志，导致 "fuzzing success"/FinalDistToGoal 解析到上一次的残留。
% 每次任务开始前先清空该日志（仅动日志，不改仿真代码）。
rsfuzz_nd0 = getenv('RSFUZZ_ND');
if isempty(rsfuzz_nd0), rsfuzz_nd0 = '6'; end
rsfuzz_log0 = fullfile(rsfuzz_work, 'Result', sprintf('iteration_log_%s.txt', rsfuzz_nd0));
if exist(rsfuzz_log0, 'file'), delete(rsfuzz_log0); end

rsfuzz_mode = getenv('RSFUZZ_MODE');
if isempty(rsfuzz_mode), rsfuzz_mode = 'sa'; end

rsfuzz_err = '';
tic;
try
    if strcmp(rsfuzz_mode, 'ma')
        MA_Fuzzing;
    else
        SA_Fuzzing;   % 'sa' 与 'na'（RSFUZZ_ATTACK=0）共用同一脚本
    end
catch ME
    rsfuzz_err = ME.message;
end
rsfuzz_wall = toc;   % clear all 不会重置内置秒表

% clear all 之后变量已丢失，全部从环境变量/文件重新获取
rsfuzz_out = getenv('RSFUZZ_OUT');
rsfuzz_work = getenv('RSFUZZ_WORK');
rsfuzz_seed = getenv('RSFUZZ_SEED');
rsfuzz_mode = getenv('RSFUZZ_MODE');
rsfuzz_nd = getenv('RSFUZZ_ND');
if isempty(rsfuzz_nd) || strcmp(rsfuzz_nd, ''), rsfuzz_nd = '6'; end
nd = str2double(rsfuzz_nd);

rsfuzz_log = fullfile(rsfuzz_work, 'Result', sprintf('iteration_log_%d.txt', nd));
rsfuzz_txt = '';
if exist(rsfuzz_log, 'file')
    rsfuzz_txt = fileread(rsfuzz_log);
end

crashed = contains(rsfuzz_txt, 'fuzzing success');
limited = contains(rsfuzz_txt, 'reached the limit');
iterations = NaN;
tok = regexp(rsfuzz_txt, 'stopped because[^:]*: (\d+)', 'tokens');
if ~isempty(tok)
    iterations = str2double(tok{end}{1});
end
arrived = false;
maxdist = NaN;
meandist = NaN;
within2 = NaN;
total = NaN;
% [AI-MOD 2026-11-05] 任务正常完成的迭代数（用于测量论文 §IV-B 的 CTime）
goalit = NaN;
tokg = regexp(rsfuzz_txt, 'GoalReached: (\d+)', 'tokens');
if ~isempty(tokg)
    goalit = str2double(tokg{end}{1});
end
tok2 = regexp(rsfuzz_txt, 'FinalDistToGoal: max=([\d\.]+) mean=([\d\.]+) within2=(\d+) within01=(\d+) total=(\d+)', 'tokens');
if ~isempty(tok2)
    t = tok2{end};
    maxdist = str2double(t{1});
    meandist = str2double(t{2});
    within2 = str2double(t{3});
    total = str2double(t{5});
    arrived = (within2 == total);
end

% 判据：②③（crashed）或 ①（未到达目标/超时）任一成立即失败
failed = crashed || ~arrived;
if ~crashed && ~limited && isempty(rsfuzz_err)
    % 脚本异常中断且没有任何判据记录，按失败计，但保留 error 说明
    failed = true;
end

rec = struct('algo', 'A3', 'mode', rsfuzz_mode, 'seed', str2double(rsfuzz_seed), ...
    'nd', nd, 'failed', failed, 'crashed', crashed, 'timeout', limited && ~arrived, ...
    'arrived', arrived, 'iterations', iterations, 'goal_it', goalit, 'final_max_dist', maxdist, ...
    'final_mean_dist', meandist, 'within2', within2, 'total', total, ...
    'wall_s', round(rsfuzz_wall * 100) / 100, 'error', rsfuzz_err);
if ~exist(rsfuzz_out, 'dir'), mkdir(rsfuzz_out); end
fid = fopen(fullfile(rsfuzz_out, 'result.json'), 'w');
fprintf(fid, '%s', jsonencode(rec));
fclose(fid);
fprintf('RESULT %s\n', jsonencode(rec));
end
