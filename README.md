# 无人机集群算法逻辑漏洞发现系统（LVD System）

面向多无人机集群算法（Adaptive Swarm / Pietro / Howard）的**逻辑漏洞自动发现与可视化分析平台**。平台在 RSFuzz 模糊测试框架之上补齐了「参数编排 → 批量调度 → 结果入库 → 轨迹回放 → 统计分析」的完整闭环，用于定位集群算法在攻击场景下的碰撞、超时与任务失败。

```
┌──────────────────────────┐        ┌──────────────────────────┐
│  Vue 3 前端 (web/LVD_System) │  /api  │   FastAPI 后端 (app/)      │
│  控制台 / 历史 / 批次 / 回放  │ ─────► │   批次、任务、回放数据查询    │
└──────────────────────────┘        └────────────┬─────────────┘
                                                  │ pymysql
                                     ┌────────────▼─────────────┐
                                     │  MySQL  rsfuzz（10 张表）  │
                                     └────────────▲─────────────┘
                                                  │ ETL 导入
                                     ┌────────────┴─────────────┐
                                     │  RSFuzz 复现实验产物 runs/ │
                                     │  A1 Python / A2·A3 MATLAB │
                                     └──────────────────────────┘
```

## 功能特性

- **测试控制台**：算法选择、论文档位 / 自定义集群规模、三条失败判据开关与自定义阈值、自带 / 自定义场景、种子区间或随机抽取、NA/SA/MA 模式、并发数与硬超时等参数编排，提交前实时预览调度命令。
- **测试历史**：按批次查询，批次卡片可查看「批次详情」，每条任务可查看「测试详情」。
- **批次分析**：批次基本信息、判据参数快照、场景快照、失败类型分布 / 模式对比 / 迭代与耗时直方图、任务明细。
- **测试分析**：three.js 3D 与 2D 俯视轨迹复现，可自动播放或拖动时间轴的执行回放；起飞点、失败点、成功点同时标注在复现场景与时间轴节点上，右侧联动展示当前帧状态、关键事件与鲁棒度曲线。
- **自定义场景**：结构化表单（地图边界、多边形 / 球体障碍、目标点）加实时预览，保存时按几何哈希去重入库。
- **数据导入**：把 RSFuzz 的 `repro/runs/` 产物幂等导入 MySQL，重复任务自动跳过。

## 目录结构

```
ex/
├─ app/                     FastAPI 后端
│  ├─ app/
│  │  ├─ main.py            服务入口（/api/health 等）
│  │  ├─ core/config.py     .env 配置加载与校验
│  │  ├─ db.py              pymysql 连接、游标、JSON 解码
│  │  ├─ api/               overview / meta / scenarios / batches / runs
│  │  └─ etl/importer.py    runs/ → MySQL 幂等导入
│  ├─ sql/001_schema.sql    数据库结构与约束
│  ├─ .env.example          配置模板（可提交）
│  └─ .env                  本机配置（不入库）
├─ web/LVD_System/          Vue 3 + Vite 前端
│  └─ src/
│     ├─ layouts/           控制台左导航布局
│     ├─ views/             首页、控制台、历史、批次分析、测试分析
│     ├─ components/        TrackStage(3D) / SceneThumb / EChart 等
│     ├─ api/index.js       axios 封装
│     └─ styles/main.css    设计令牌与 Element Plus 主题覆盖
├─ RSFuzz/                  模糊测试框架与复现实验
│  ├─ Adaptive Swarm/       A1（Python）
│  ├─ Pietro/               A2（MATLAB + Python）
│  ├─ Howard/               A3（MATLAB + Python）
│  └─ repro/                调度与分析脚本（sched.py / run_a1.py / batch_a*.m / analyze.py）
└─ README.md
```

## 技术栈

| 层 | 选型 |
|---|---|
| 前端 | Vue 3.5（`<script setup>`）、Vite 8、Vue Router、Pinia、Element Plus、ECharts、three.js |
| 后端 | FastAPI、Uvicorn、PyMySQL（短连接 + DictCursor） |
| 数据库 | MySQL 8.0 / 9.x，utf8mb4 |
| 实验 | Python 3.10+、MATLAB R2024b（A2/A3） |

## 快速开始

### 1. 环境要求

- Python 3.10+
- Node.js `^22.18.0 || >=24.12.0`
- MySQL 8.0+（本仓库在 MySQL 9.3 上验证）

### 2. 初始化数据库

```bash
mysql -u root -p < app/sql/001_schema.sql
```

脚本会创建 `rsfuzz` 库及 `scenario`、`criteria_profile`、`batch`、`task_run`、`failure_event`、`iteration_metric`、`trace_frame`、`artifact`、`import_log`、`schema_meta` 共 10 张表。`task_run` 以 `batch_id`、`scenario_id`、`criteria_id` 建立外键，`replay_key` 唯一保证导入幂等。

### 3. 启动后端

```bash
cd app
cp .env.example .env        # Windows: copy .env.example .env
# 编辑 .env，至少填写 RSFUZZ_DB_PASSWORD
pip install fastapi uvicorn pymysql
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

健康检查：<http://127.0.0.1:8000/api/health>，交互式文档：<http://127.0.0.1:8000/docs>。

> `.env` 含数据库口令，已被 `.gitignore` 排除，请勿提交。

### 4. 导入实验数据

```bash
cd app
python -m app.etl.importer --dry-run                 # 先预览将导入多少任务
python -m app.etl.importer --algo all                # 全量导入
python -m app.etl.importer --algo a2 --size 10 --maxt 60 --collide 0
```

导入器扫描 `RSFuzz/repro/runs/<algo>/s<size>/<mode>/<seed>/`，读取 `result.json` 与 `trace/*.jsonl`，写入任务、失败事件、迭代指标与回放帧；同一 `replay_key` 重复导入直接跳过。

### 5. 启动前端

```bash
cd web/LVD_System
npm install
npm run dev          # http://localhost:5173
```

开发服务器已把 `/api` 代理到 `http://127.0.0.1:8000`（见 `vite.config.js`）。生产构建：`npm run build`。

## 页面与路由

| 路由 | 页面 | 说明 |
|---|---|---|
| `/` | 首页 | 平台概览：任务总量、失败率、三种算法卡片、流程与最近任务 |
| `/console/test` | 测试控制台 | 参数编排、自定义场景、命令预览与提交 |
| `/console/history` | 测试历史 | 批次列表、筛选、批次详情 / 测试详情入口 |
| `/console/batch/:id` | 批次分析 | 基本信息、参数快照、结果统计图表 |
| `/console/run/:id` | 测试分析 | 轨迹与场景复现、时间轴回放、事件与鲁棒度 |

## API 一览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 服务与数据库连通性 |
| GET | `/api/overview` | 首页统计、算法与失败类型分布、最近任务 |
| GET | `/api/meta` | 算法、论文档位、判据默认值、自定义规模上下限 |
| GET | `/api/scenarios` | 场景列表（按算法 / 维度 / 规模过滤） |
| GET | `/api/scenarios/{id}` | 场景完整几何 |
| POST | `/api/scenarios` | 新建自定义场景（几何哈希去重，重复返回 `created:false`） |
| GET | `/api/batches` | 批次列表（筛选 + 分页 + 任务聚合） |
| GET | `/api/batches/{id}` | 批次详情、判据快照、场景、统计直方图 |
| POST | `/api/batches` | 登记测试批次并返回计划任务数、种子列表与调度命令 |
| GET | `/api/runs` | 任务列表（按批次 / 算法 / 规模 / 模式 / 状态过滤） |
| GET | `/api/runs/{id}` | 任务详情（含场景、判据、回放帧、事件） |
| GET | `/api/runs/{id}/frames` | 分块拉取回放帧（`from` / `to` / `stride`） |
| GET | `/api/runs/{id}/metrics` | 迭代指标（鲁棒度曲线） |
| GET | `/api/runs/{id}/events` | 失败事件（自动补齐位置，供复现标注） |

## RSFuzz 复现实验

三种算法对应论文中的 A1/A2/A3：

| 算法 | 目录 | 入口 |
|---|---|---|
| Adaptive Swarm | `RSFuzz/Adaptive Swarm/` | `repro/sched.py` → `run_a1.py` |
| Pietro | `RSFuzz/Pietro/` | `repro/sched.py` → `batch_a2.m` |
| Howard | `RSFuzz/Howard/` | `repro/sched.py` → `batch_a3.m` |

```bash
cd RSFuzz
python repro/sched.py --algo a1 --size 4 --seeds 1-100 --strategies 2 --workers 6
matlab -batch "batch_a2"     # A2：MATLAB + Python
matlab -batch "batch_a3"     # A3：MATLAB + Python
```

结果写入 `repro/runs/<algo>/s<size>/<mode>/<seed>/`，再由 ETL 导入数据库。论文口径（规模、CTime、失败判据、A2 机间碰撞不计失败、A3 攻击链开关等）与本地实现细节见 `repro/` 下脚本注释。

## 配置项（`app/.env`）

| 变量 | 说明 |
|---|---|
| `RSFUZZ_DB_HOST` / `RSFUZZ_DB_PORT` | MySQL 地址与端口 |
| `RSFUZZ_DB_NAME` / `RSFUZZ_DB_USER` / `RSFUZZ_DB_PASSWORD` | 库名、账号、口令（口令必填） |
| `RSFUZZ_ARTIFACT_ROOT` | 实验产物根目录，指向 `RSFuzz/repro` |
| `RSFUZZ_API_HOST` / `RSFUZZ_API_PORT` | 服务监听地址与端口 |

优先级：真实环境变量 > `.env` > 代码缺省值。

## 已知限制

- 控制台提交仅登记批次（`status=running`），不会自动拉起 `sched.py`，实际实验需在 `RSFuzz/` 下按上表命令执行。
- 回放依赖 `task_run.trace_state`；未采集轨迹（`none`）的任务只能看结果，无法播放。
- 第三次判据（A3 攻击链）目前没有历史数据，界面会显示为空态。

## 致谢

本项目复现与扩展基于 RSFuzz（*A Robustness-Guided Swarm Fuzzing Framework Based on Behavioral Constraints*）及其三个开源集群算法实现，感谢上游作者与开源社区。
