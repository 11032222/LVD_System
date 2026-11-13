function batch_a3()
% [AI-MOD 2026-11-09] A3 批量驱动：在**同一个 MATLAB 进程内**循环跑多个 (mode, seed) 任务。
%
% 为什么需要它：
%   本机每次新起一个 matlab.exe 都有很高概率报
%     Fatal Startup Error: System Error: File system inconsistency
%   退出码 1（与 qemu/沙箱/独立 prefdir/启动错峰都无关，见 batch_a2 的说明）。
%   因此 A3 也用"一次启动、循环跑完"，把 300 个任务的启动次数从 300 降到 1。
%
% 语义保持不变：每个任务仍然调用一次 run_a3（同样的环境变量、同样的
%   result.json 路径与内容），唯一差别是共享同一个 MATLAB 进程。
%
% 环境变量（由启动命令注入）：
%   RSFUZZ_BATCH_MODES  逗号分隔，如 "na,sa,ma"
%   RSFUZZ_BATCH_SEEDS  如 "1-100" 或 "1,3,5"
%   RSFUZZ_BATCH_SIZE   规模档：论文 A3 = 6/8/10（缺省 6，与上游一致）
%   RSFUZZ_BATCH_LINK   攻击链开关：na 恒为 0；sa/ma 用该值（0=上游原样，1=论文语义）
%   RSFUZZ_RUNS         repro/runs（result.json 根目录）
%   RSFUZZ_WORKDIR      repro/work（任务工作目录根）
%   其余（RSFUZZ_DRAW / RSFUZZ_MAXIT 等）原样继承给 run_a3。

rsfuzz_root = fileparts(mfilename('fullpath'));            % repro/
rsfuzz_runs = getenv('RSFUZZ_RUNS');
if isempty(rsfuzz_runs)
    rsfuzz_runs = fullfile(rsfuzz_root, 'runs');
end
rsfuzz_workdir = getenv('RSFUZZ_WORKDIR');
if isempty(rsfuzz_workdir)
    rsfuzz_workdir = fullfile(rsfuzz_root, 'work');
end

% run_a3.m 位于 Howard/src/ 目录，先加入搜索路径
addpath(fullfile(fileparts(rsfuzz_root), 'Howard', 'src'));

rsfuzz_modes = cellstr(strsplit(strtrim(getenv('RSFUZZ_BATCH_MODES')), ','));
rsfuzz_seeds = rsfuzz_parse_seeds(getenv('RSFUZZ_BATCH_SEEDS'));
rsfuzz_size = getenv('RSFUZZ_BATCH_SIZE');
if isempty(rsfuzz_size)
    rsfuzz_size = '6';
end
rsfuzz_link = getenv('RSFUZZ_BATCH_LINK');
if isempty(rsfuzz_link)
    rsfuzz_link = '0';
end

fprintf('[batch_a3] modes={%s} size=%s link=%s seeds=%d 个\n', ...
    strjoin(rsfuzz_modes, ','), rsfuzz_size, rsfuzz_link, numel(rsfuzz_seeds));

for mi = 1:numel(rsfuzz_modes)
    mode = strtrim(rsfuzz_modes{mi});
    if isempty(mode)
        continue;
    end
    % 与 sched.py 的目录约定一致：sa/ma 在 LINK=1 时写 *_link1 目录
    rsfuzz_dir_mode = mode;
    if strcmp(rsfuzz_link, '1') && ~strcmp(mode, 'na')
        rsfuzz_dir_mode = [mode, '_link1'];
    end
    for si = 1:numel(rsfuzz_seeds)
        seed = rsfuzz_seeds(si);
        out = fullfile(rsfuzz_runs, 'a3', ['s', rsfuzz_size], rsfuzz_dir_mode, num2str(seed));
        work = fullfile(rsfuzz_workdir, 'a3', sprintf('%s_s%s_%d', rsfuzz_dir_mode, rsfuzz_size, seed));
        % 断点续跑：已有 result.json 的任务跳过（与 sched.py 一致）
        if exist(fullfile(out, 'result.json'), 'file')
            fprintf('[batch_a3] skip %s seed=%d\n', mode, seed);
            continue;
        end
        % run_a3 全部参数从环境变量读取，这里逐个覆盖
        setenv('RSFUZZ_MODE', mode);
        setenv('RSFUZZ_SEED', num2str(seed));
        setenv('RSFUZZ_WORK', work);
        setenv('RSFUZZ_OUT', out);
        setenv('RSFUZZ_ND', rsfuzz_size);
        if strcmp(mode, 'na')
            setenv('RSFUZZ_A3_LINK', '0');   % 基线必须关攻击链
        else
            setenv('RSFUZZ_A3_LINK', rsfuzz_link);
        end
        fprintf('[batch_a3] run %s seed=%d\n', mode, seed);
        rsfuzz_t0 = tic;
        try
            run_a3();
        catch ME
            fprintf('[batch_a3] ERROR %s seed=%d: %s\n', mode, seed, ME.message);
        end
        fprintf('[batch_a3] done %s seed=%d %.1fs\n', mode, seed, toc(rsfuzz_t0));
    end
end
fprintf('[batch_a3] ALL DONE\n');
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
