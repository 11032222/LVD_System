function batch_a2()
% [AI-MOD 2026-11-06] A2 批量驱动：在**同一个 MATLAB 进程内**循环跑多个 (mode, seed) 任务。
%
% 为什么需要它：
%   本机每次新起一个 matlab.exe 都有几率（实测连续批量时几乎必然）报
%     Fatal Startup Error: System Error: File system inconsistency
%   退出码 1。这与被测程序无关，是 MATLAB 启动期的环境故障（独立 prefdir、
%   启动错峰、关闭沙箱均无法消除）。sched.py 的"一任务一进程"方式因此
%   在 300 任务的量级上不可用，故改为"一次启动、循环跑完"，把启动次数
%   从 300 降到 1~2 次。
%
% 语义保持不变：每个任务仍然调用一次 run_a2（同样的环境变量、同样的
%   result.json 路径），唯一差别是它们共享同一个 MATLAB 进程。
%
% 环境变量（由启动命令注入）：
%   RSFUZZ_BATCH_MODES  逗号分隔，如 "na,sa,ma"
%   RSFUZZ_BATCH_SEEDS  如 "1-100" 或 "1,3,5"
%   RSFUZZ_BATCH_SIZE   无人机数量档位（论文 Table II 的 A2 为 10/15/20），缺省 10
%   RSFUZZ_RUNS         repro/runs（result.json 根目录）
%   RSFUZZ_WORKDIR      repro/work（任务工作目录根）
%   其余（RSFUZZ_DRAW / RSFUZZ_MAXT / RSFUZZ_COLLIDE 等）原样继承给 run_a2。

rsfuzz_root = fileparts(mfilename('fullpath'));            % repro/
rsfuzz_runs = getenv('RSFUZZ_RUNS');
if isempty(rsfuzz_runs)
    rsfuzz_runs = fullfile(rsfuzz_root, 'runs');
end
rsfuzz_workdir = getenv('RSFUZZ_WORKDIR');
if isempty(rsfuzz_workdir)
    rsfuzz_workdir = fullfile(rsfuzz_root, 'work');
end

% run_a2.m 位于 Pietro/ 目录，先加入搜索路径（否则这里调用不到）
addpath(fullfile(fileparts(rsfuzz_root), 'Pietro'));

rsfuzz_modes = cellstr(strsplit(strtrim(getenv('RSFUZZ_BATCH_MODES')), ','));
rsfuzz_seeds = rsfuzz_parse_seeds(getenv('RSFUZZ_BATCH_SEEDS'));
% [AI-MOD 2026-11-10] 论文 Table II 的 A2 规模档为 10/15/20；缺省保持上游 N=10。
% 目录与注入的环境变量都按规模区分，避免覆盖 runs/a2 下 size=10 的历史结果。
rsfuzz_size = strtrim(getenv('RSFUZZ_BATCH_SIZE'));
if isempty(rsfuzz_size)
    rsfuzz_size = '10';
end

fprintf('[batch_a2] size=%s modes={%s} seeds=%d 个\n', rsfuzz_size, strjoin(rsfuzz_modes, ','), numel(rsfuzz_seeds));

for mi = 1:numel(rsfuzz_modes)
    mode = strtrim(rsfuzz_modes{mi});
    if isempty(mode)
        continue;
    end
    for si = 1:numel(rsfuzz_seeds)
        seed = rsfuzz_seeds(si);
        % out = fullfile(rsfuzz_runs, 'a2', mode, num2str(seed));            % [AI-MOD 2026-11-10] 原路径不含规模
        % work = fullfile(rsfuzz_workdir, 'a2', sprintf('%s_%d', mode, seed));
        out = fullfile(rsfuzz_runs, 'a2', ['s' rsfuzz_size], mode, num2str(seed));   % [AI-MOD 2026-11-10] 按规模分目录
        work = fullfile(rsfuzz_workdir, 'a2', ['s' rsfuzz_size], sprintf('%s_%d', mode, seed));
        % 断点续跑：已有 result.json 的任务跳过（与 sched.py 一致）
        if exist(fullfile(out, 'result.json'), 'file')
            fprintf('[batch_a2] skip %s seed=%d\n', mode, seed);
            continue;
        end
        % 每个任务都是 run_a2 读的环境变量，这里逐个覆盖
        setenv('RSFUZZ_MODE', mode);
        setenv('RSFUZZ_SEED', num2str(seed));
        setenv('RSFUZZ_WORK', work);
        setenv('RSFUZZ_OUT', out);
        % setenv('RSFUZZ_ND', '6');                                          % [AI-MOD 2026-11-10] A2 不使用该变量
        setenv('RSFUZZ_ND', rsfuzz_size);
        setenv('RSFUZZ_N', rsfuzz_size);   % [AI-MOD 2026-11-10] easy_simulation_config.m 读此变量设置 N
        setenv('RSFUZZ_A3_LINK', '0');
        fprintf('[batch_a2] run %s seed=%d\n', mode, seed);
        rsfuzz_t0 = tic;
        try
            run_a2();
        catch ME
            fprintf('[batch_a2] ERROR %s seed=%d: %s\n', mode, seed, ME.message);
        end
        fprintf('[batch_a2] done %s seed=%d %.1fs\n', mode, seed, toc(rsfuzz_t0));
    end
end
fprintf('[batch_a2] ALL DONE\n');
end

function seeds = rsfuzz_parse_seeds(txt)
% 解析 "1-100" / "1,3,5" / "1-3,7" 形式的种子列表
seeds = [];
parts = strsplit(strtrim(txt), ',');
for pi = 1:numel(parts)
    part = strtrim(parts{pi});
    if isempty(part)
        continue;
    end
    if contains(part, '-')
        ab = strsplit(part, '-');
        seeds = [seeds, str2double(ab{1}):str2double(ab{2})]; %#ok<AGROW>
    else
        seeds(end + 1) = str2double(part); %#ok<AGROW>
    end
end
end
