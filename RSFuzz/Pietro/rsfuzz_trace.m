function rsfuzz_trace(t, Q, atk, obstacles_list)
%RSFUZZ_TRACE  [AI-MOD 2026-11-12] A2(Pietro) 数据采集：把每步状态写入 JSONL。
%
%   用途：为平台数据库提供"回放帧"与"鲁棒度曲线"的原始数据。
%
%   行为约定（重要）：
%     1. 只读取入参、只写文件，**不修改任何仿真状态、不改变任何决策**，因此不影响任务结果；
%     2. RSFUZZ_TRACE 未设为 '1' 时，函数在第一个分支立即返回，
%        不建目录、不写文件、不做任何额外计算（保证与原版逐位一致）；
%     3. 每次写入后立即 fclose，避免上游 error() 中断时缓冲区数据丢失。
%
%   输入：
%     t            当前仿真时间 (s)
%     Q            4xN 状态矩阵（第 2、3 行为 x,y）
%     atk          攻击机位置 [x y]；无攻击机 / 攻击尚未开始时传 []
%     obstacles_list  障碍多边形 cell（与 attack.py 的 obstacles_list 同源）；
%                     为空时不计算鲁棒度，rob 写 null
%
%   输出（目录 = $RSFUZZ_OUT/trace/）：
%     frame.jsonl  每步一行：机群 + 攻击机位置（回放用）
%     iter.jsonl   每轮一行：攻击点 + 鲁棒度（曲线用，仅攻击模式）
%
%   调用方式（主循环末尾一行，见 SA_Fuzzing.m / MA_Fuzzing.m）：
%     rsfuzz_trace(t, Q, atk, obstacles_list);

persistent enabled inited out_dir step_no

if isempty(inited)
    inited = true;
    enabled = strcmp(getenv('RSFUZZ_TRACE'), '1');
    if enabled
        out_dir = fullfile(getenv('RSFUZZ_OUT'), 'trace');
        if ~exist(out_dir, 'dir')
            mkdir(out_dir);
        end
        % 同一任务重跑时先清空，避免追加出重复帧
        for fn = {'frame.jsonl', 'iter.jsonl'}
            f = fullfile(out_dir, fn{1});
            if exist(f, 'file')
                delete(f);
            end
        end
        step_no = 0;
    end
end

if ~enabled
    return;
end

% attack_agent_location 在攻击分支里先是 MATLAB 的 1x2 double，随后被赋成
% attack_strategy_SA 的返回值（Python tuple）。py.tuple 不能用 () 索引、也不能参与
% 数值拼接（实测报"不允许使用类 'py.tuple' 的对象组成数组"），这里统一转成 double。
% 花括号索引与 SA/MA_Fuzzing.m 中 attack_agent_next{1} 的用法一致。
if isa(atk, 'py.tuple') || isa(atk, 'py.list')
    atk = [double(atk{1}), double(atk{2})];
end

% ---- 1. 回放帧：所有无人机 + 攻击机 ----
n = size(Q, 2);
agents = struct('k', {}, 'id', {}, 'p', {});
for j = 1:n
    agents(j).k = 'uav';
    agents(j).id = j - 1;
    agents(j).p = [Q(2, j), Q(3, j)];
end
if ~isempty(atk)
    agents(n + 1).k = 'attacker';
    agents(n + 1).id = n;
    agents(n + 1).p = [atk(1), atk(2)];
end

rec = struct('step', step_no, 't', t, 'agents', agents);
fid = fopen(fullfile(out_dir, 'frame.jsonl'), 'a');
if fid >= 0
    fprintf(fid, '%s\n', jsonencode(rec));
    fclose(fid);
end

% ---- 2. 鲁棒度：对选中的攻击点，用算法自身的函数算一次（每轮 1 次，不是 20 次） ----
if ~isempty(atk)
    rob = rsfuzz_rob(Q, atk, obstacles_list);
    if isnan(rob)
        rob = [];   % jsonencode 不支持 NaN，用 [] 编码成 null
    end
    rec2 = struct('step', step_no, 't', t, 'pos', [atk(1), atk(2)], 'rob', rob);
    fid = fopen(fullfile(out_dir, 'iter.jsonl'), 'a');
    if fid >= 0
        fprintf(fid, '%s\n', jsonencode(rec2));
        fclose(fid);
    end
end

step_no = step_no + 1;
end


function rob = rsfuzz_rob(Q, atk, obstacles_list)
% [AI-MOD 2026-11-12] 复用 Pietro/attack.py 中的同一鲁棒度函数（robustness.rule1_prepare），
% 保证曲线与攻击搜索的目标函数完全一致，不另写一套语义。
% 任何异常（Python 未就绪、障碍为空等）都退化为 NaN，不影响主流程。
rob = NaN;
if isempty(obstacles_list)
    return;
end
try
    dloc = py.attack.drones_agent_location(Q(2, :), Q(3, :));
    x = atk(1);
    y = atk(2);
    ol = obstacles_list;
    % 与 attack_strategy_SA/MA 中一致：把攻击机表示成菱形多边形后追加。
    % 这里直接复用 attack.py 的 obstacles_list() 构造（它丢弃最后一点），
    % 传入首尾重复的闭合多边形，得到与原策略完全相同的 4 个顶点。
    ol{end + 1} = py.attack.obstacles_list( ...
        [x - 1; x; x + 1; x; x - 1], [y; y - 1; y; y + 1; y]);
    rob = double(py.robustness.rule1_prepare(dloc, ol));
catch
    rob = NaN;
end
end
