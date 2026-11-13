function [xi, yi] = rsfuzz_polyxpoly(x1, y1, x2, y2)
% [AI-MOD 2026-11-05] polyxpoly 的等价替代实现（本机当时未安装 Mapping Toolbox）。
%
% 现状（2026-11-05 晚）：本机已安装 Mapping Toolbox 24.2（R2024b，license('test','MAP_Toolbox')=1），
%   SA_Fuzzing.m / MA_Fuzzing.m / next_pos.m 中的调用已全部还原为上游的 polyxpoly，本文件不再被调用，
%   仅作为"无 toolbox 环境"的备份实现保留。
%
% 为什么曾经需要：
%   上游 Pietro/SA_Fuzzing.m、MA_Fuzzing.m 用 polyxpoly 判断 IR 传感器折线是否与
%   障碍物多边形/地图边界相交（论文 §III-C1 的红外接近传感器模型）。本机 MATLAB R2024b
%   当时只装了 Optimization / Robotics System / Statistics 三个 toolbox，polyxpoly 不可用
%   （exist('polyxpoly') == 0），因此提供同接口的替代实现。
%
% 接口：与 polyxpoly 的常用形式一致，输入两条折线（向量），输出交点列向量；
%       无交点时返回 0x1 空向量（MATLAB 中空矩阵为假，兼容上游的
%       "IR_detect = polyxpoly(...); if IR_detect" 用法）。
%
% 实现依据：
%   1) 只做"折线 × 折线"的线段相交判定，用参数化线段求交，不用 polyshape
%      （退化多边形会让 polyshape 报错，而上游障碍物顶点可能存在重复点）；
%   2) 共线重叠时按"相交"处理，返回重叠段中点——上游只关心是否检测到障碍物。

xi = zeros(0, 1);
yi = zeros(0, 1);

% [AI-MOD 2026-11-05] 上游在攻击机分支里会临时把 obstacles 扩成含空单元的 cell，
% 空输入必须安全返回空交点（polyxpoly 对空输入同样返回空）。
x1 = x1(:); y1 = y1(:); x2 = x2(:); y2 = y2(:);
if numel(x1) < 2 || numel(y1) < 2 || numel(x2) < 2 || numel(y2) < 2
    return;
end
if numel(x1) ~= numel(y1) || numel(x2) ~= numel(y2)
    return;
end

tol = 1e-12;

for i = 1:(numel(x1) - 1)
    p = [x1(i), y1(i)];
    r = [x1(i + 1) - x1(i), y1(i + 1) - y1(i)];
    for j = 1:(numel(x2) - 1)
        q = [x2(j), y2(j)];
        s = [x2(j + 1) - x2(j), y2(j + 1) - y2(j)];
        den = r(1) * s(2) - r(2) * s(1);
        qp = [q(1) - p(1), q(2) - p(2)];
        if abs(den) > tol
            t = (qp(1) * s(2) - qp(2) * s(1)) / den;
            u = (qp(1) * r(2) - qp(2) * r(1)) / den;
            if t >= -tol && t <= 1 + tol && u >= -tol && u <= 1 + tol
                xi(end + 1, 1) = p(1) + t * r(1); %#ok<AGROW>
                yi(end + 1, 1) = p(2) + t * r(2); %#ok<AGROW>
            end
        else
            % 平行：仅当共线且投影区间重叠时视为相交，取重叠段中点
            if abs(qp(1) * r(2) - qp(2) * r(1)) <= tol && (r(1) ~= 0 || r(2) ~= 0)
                rr = r(1) * r(1) + r(2) * r(2);
                t0 = (qp(1) * r(1) + qp(2) * r(2)) / rr;
                t1 = t0 + (s(1) * r(1) + s(2) * r(2)) / rr;
                lo = max(0, min(t0, t1));
                hi = min(1, max(t0, t1));
                if hi >= lo - tol
                    tm = (lo + hi) / 2;
                    xi(end + 1, 1) = p(1) + tm * r(1); %#ok<AGROW>
                    yi(end + 1, 1) = p(2) + tm * r(2); %#ok<AGROW>
                end
            end
        end
    end
end
end
