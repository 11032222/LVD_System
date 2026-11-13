function rsfuzz_trace(it, drones, atk, rob, obst, dims, goals)
%RSFUZZ_TRACE  [AI-MOD 2026-11-12] A3(Howard) 数据采集：把每次迭代状态写入 JSONL。
%
%   与 Pietro/rsfuzz_trace.m 输出同一格式，供 app/app/etl/importer.py 统一入库。
%
%   行为约定（重要）：
%     1. 只读取入参、只写文件，**不修改任何仿真状态、不改变任何决策**；
%     2. RSFUZZ_TRACE 不为 '1' 时，函数在第一个分支立即返回，不建目录、不写文件；
%     3. 每次写入后立即 fclose，避免上游 error()/break 中断时缓冲区数据丢失。
%
%   与 A2 的差异：Howard 没有仿真时间，只有迭代序号 it，故 t 写 []（入库为 NULL）。
%
%   输入：
%     it      当前迭代序号（主循环变量，作为 step）
%     drones  Drone 对象数组（取 .pos，3x1）
%     atk     攻击机位置 3x1；无攻击 / 基线时传 []
%     rob     本次迭代攻击点对应的鲁棒度（A3 主循环已算好，直接复用，不重复计算）
%     obst    [AI-MOD 2026-11-12] Obstacle 对象数组（静态场景，不含攻击机）；
%             仅用于首次调用时导出 map.json，不参与任何计算
%     dims    [AI-MOD 2026-11-12] 3x2 地图边界（SA/MA_Fuzzing.m 的 dims）
%     goals   [AI-MOD 2026-11-12] 3xNd 每架无人机的终点（rsfuzz_goal）

persistent enabled inited out_dir

if nargin < 5, obst = []; end
if nargin < 6, dims = []; end
if nargin < 7, goals = []; end

if isempty(inited)
    inited = true;
    enabled = strcmp(getenv('RSFUZZ_TRACE'), '1');
    if enabled
        base_dir = getenv('RSFUZZ_OUT');       % run 根目录（与 A1 的 map.json 同一层）
        out_dir = fullfile(base_dir, 'trace');
        if ~exist(out_dir, 'dir')
            mkdir(out_dir);
        end
        for fn = {'frame.jsonl', 'iter.jsonl'}
            f = fullfile(out_dir, fn{1});
            if exist(f, 'file')
                delete(f);
            end
        end
        % [AI-MOD 2026-11-12] 场景几何：A3 的 7 个障碍是 [0,10]^3 内按种子随机生成的，
        % 每个种子的几何都不同，只能运行时从 obst 实例导出，不能写死在代码里。
        rsfuzz_write_map(base_dir, obst, dims, goals);
    end
end

if ~enabled
    return;
end

% ---- 1. 回放帧：所有无人机 + 攻击机 ----
n = numel(drones);
agents = struct('k', {}, 'id', {}, 'p', {});
for j = 1:n
    agents(j).k = 'uav';
    agents(j).id = j - 1;
    agents(j).p = drones(j).pos(:)';
end
if ~isempty(atk)
    agents(n + 1).k = 'attacker';
    agents(n + 1).id = n;
    agents(n + 1).p = atk(:)';
end

rec = struct('step', it, 't', [], 'agents', agents);
fid = fopen(fullfile(out_dir, 'frame.jsonl'), 'a');
if fid >= 0
    fprintf(fid, '%s\n', jsonencode(rec));
    fclose(fid);
end

% ---- 2. 鲁棒度曲线：直接用主循环算出的 rob_val ----
if ~isempty(atk) && ~isempty(rob) && ~isnan(rob)
    rec2 = struct('step', it, 't', [], 'pos', atk(:)', 'rob', rob);
    fid = fopen(fullfile(out_dir, 'iter.jsonl'), 'a');
    if fid >= 0
        fprintf(fid, '%s\n', jsonencode(rec2));
        fclose(fid);
    end
end
end

function rsfuzz_write_map(base_dir, obst, dims, goals)
%RSFUZZ_WRITE_MAP  [AI-MOD 2026-11-12] 把 A3 的 3D 场景几何写成 map.json（每 run 一份）。
%
%   与 A1 的 map.json 同一个用途：给回放提供真实障碍与边界，避免用首帧位姿外接框占位。
%   文件位置与 A1 一致（run 根目录，即 RSFUZZ_OUT 下），导入器据此读取。
%   格式：
%     {"dim":3,
%      "bounds":{"x":[lo,hi],"y":[lo,hi],"z":[lo,hi]},
%      "obstacles":[{"kind":"sphere","c":[x,y,z],"r":半径}, ...],
%      "targets":[[x,y,z], ...]}       % 每架无人机各自的终点（Nd 个）
%
%   只读入参，异常一律吞掉：几何导出失败不能影响仿真。

try
    if isempty(dims)
        dims = [0, 50; 0, 50; 0, 50];   % 与 SA/MA_Fuzzing.m 的缺省地图一致
    end
    geo = struct();
    geo.dim = 3;
    geo.bounds = struct('x', [dims(1, 1), dims(1, 2)], ...
                        'y', [dims(2, 1), dims(2, 2)], ...
                        'z', [dims(3, 1), dims(3, 2)]);
    obs = struct('kind', {}, 'c', {}, 'r', {});
    for o = 1:numel(obst)
        obs(o).kind = 'sphere';
        obs(o).c = obst(o).pos(:)';
        obs(o).r = obst(o).radius;
    end
    geo.obstacles = obs;
    if ~isempty(goals)
        geo.targets = goals';           % 3xNd → Nd x 3，jsonencode 得到 [[x,y,z],...]
    else
        geo.targets = zeros(0, 0);
    end
    fid = fopen(fullfile(base_dir, 'map.json'), 'w');
    if fid >= 0
        fprintf(fid, '%s\n', jsonencode(geo));
        fclose(fid);
    end
catch
    % 采集异常一律吞掉，绝不允许影响仿真结果
end
end
