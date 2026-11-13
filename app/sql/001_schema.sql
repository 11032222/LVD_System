-- ============================================================================
-- RSFuzz 测试管理平台 - 数据库结构（MySQL 9.x）
-- 字符集 utf8mb4 / 引擎 InnoDB
-- 说明：
--   1. 值域约束保留 CHECK，但不使用固定值枚举（集群数量、地图、阈值均可自定义）
--   2. 完整性约束（唯一键 / 外键 / NOT NULL）全部保留
--   3. artifact 的唯一键用 rel_path 全局唯一，避免复合唯一键中 NULL 导致失效
-- ============================================================================

CREATE DATABASE IF NOT EXISTS rsfuzz
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_0900_ai_ci;
USE rsfuzz;

-- ---------------------------------------------------------------------------
-- 1. scenario 场景（内置 + 自定义地图）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS scenario (
  id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  algo            VARCHAR(32)        NOT NULL COMMENT 'Adaptive Swarm / Pietro / Howard',
  swarm_size      SMALLINT UNSIGNED  NOT NULL COMMENT '该场景配置的集群规模',
  slug            VARCHAR(64)        NOT NULL COMMENT '场景标识，同算法内唯一',
  name            VARCHAR(128)       NOT NULL COMMENT '展示名',
  scene_hash      CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT '归一化几何哈希',
  dim             TINYINT UNSIGNED   NOT NULL COMMENT '2 或 3，渲染器能力约束',
  bounds          JSON               NOT NULL COMMENT '{"x":[min,max],"y":[...],"z":[...]}',
  obstacles       JSON               NOT NULL COMMENT '[{"kind":"polygon","pts":[[x,y],...]},{"kind":"sphere","c":[x,y,z],"r":4}]',
  start_pose      JSON               NULL,
  goal            JSON               NULL,
  waypoints       JSON               NULL,
  init_positions  JSON               NOT NULL COMMENT 'N 架初始位姿',
  source_type     VARCHAR(16)        NOT NULL DEFAULT 'builtin',
  map_format      VARCHAR(16)        NOT NULL DEFAULT 'geometry_json',
  map_artifact_id BIGINT UNSIGNED    NULL COMMENT '自定义上传原件(.mat/.png)，逻辑关联 artifact.id',
  overrides       JSON               NULL COMMENT '仅覆盖部分字段时使用',
  is_public       TINYINT(1)         NOT NULL DEFAULT 1,
  created_by      VARCHAR(64)        NULL,
  created_at      DATETIME(3)        NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  UNIQUE KEY uk_sc_algo_hash (algo, scene_hash),
  UNIQUE KEY uk_sc_algo_slug (algo, slug),
  KEY idx_sc_builtin (algo, source_type),
  CONSTRAINT ck_sc_algo   CHECK (algo IN ('Adaptive Swarm','Pietro','Howard')),
  CONSTRAINT ck_sc_dim    CHECK (dim IN (2,3)),
  CONSTRAINT ck_sc_size   CHECK (swarm_size BETWEEN 1 AND 64),
  CONSTRAINT ck_sc_source CHECK (source_type IN ('builtin','custom_upload','custom_generated')),
  CONSTRAINT ck_sc_mfmt   CHECK (map_format IN ('geometry_json','mat','image'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='测试场景（含自定义地图）';

-- ---------------------------------------------------------------------------
-- 2. criteria_profile 判据与攻击参数
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS criteria_profile (
  id                 BIGINT UNSIGNED   NOT NULL AUTO_INCREMENT,
  name               VARCHAR(64)       NOT NULL,
  params_hash        CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  profile_kind       VARCHAR(16)       NOT NULL DEFAULT 'paper',
  is_default         TINYINT(1)        NOT NULL DEFAULT 0,
  description        VARCHAR(255)      NULL,
  obstacle_dist_thr  DOUBLE            NULL COMMENT 'NULL=该判据未启用',
  drone_dist_thr     DOUBLE            NULL,
  timeout_multiplier DOUBLE            NOT NULL DEFAULT 2.0,
  enable_obstacle    TINYINT(1)        NOT NULL DEFAULT 1,
  enable_collision   TINYINT(1)        NOT NULL DEFAULT 1,
  enable_timeout     TINYINT(1)        NOT NULL DEFAULT 1,
  candidate_count    SMALLINT UNSIGNED NOT NULL DEFAULT 20,
  reach_radius       DOUBLE            NULL COMMENT 'NULL=MA 瞬移',
  sample_sigma       DOUBLE            NULL,
  max_iterations     INT UNSIGNED      NULL,
  max_sim_time       DOUBLE            NULL,
  extra              JSON              NULL COMMENT 'a3_link / waypoints_mode 等',
  created_at         DATETIME(3)       NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  UNIQUE KEY uk_cp_hash (params_hash),
  UNIQUE KEY uk_cp_name (name),
  KEY idx_cp_kind (profile_kind, is_default),
  CONSTRAINT ck_cp_kind  CHECK (profile_kind IN ('paper','custom')),
  CONSTRAINT ck_cp_obst  CHECK (obstacle_dist_thr IS NULL OR obstacle_dist_thr > 0),
  CONSTRAINT ck_cp_drone CHECK (drone_dist_thr IS NULL OR drone_dist_thr > 0),
  CONSTRAINT ck_cp_mult  CHECK (timeout_multiplier > 0),
  CONSTRAINT ck_cp_cand  CHECK (candidate_count BETWEEN 1 AND 1000),
  CONSTRAINT ck_cp_sigma CHECK (sample_sigma IS NULL OR sample_sigma > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='判据与攻击参数配置';

-- ---------------------------------------------------------------------------
-- 3. batch 批次
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS batch (
  id              BIGINT UNSIGNED   NOT NULL AUTO_INCREMENT,
  batch_key       CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  algo            VARCHAR(32)       NOT NULL,
  swarm_size      SMALLINT UNSIGNED NOT NULL,
  modes           JSON              NOT NULL COMMENT '["na","sa","ma"]',
  seed_from       INT UNSIGNED      NOT NULL,
  seed_to         INT UNSIGNED      NOT NULL,
  scheduler       VARCHAR(32)       NOT NULL DEFAULT 'sched.py',
  host            VARCHAR(64)       NULL,
  git_rev         VARCHAR(40)       NULL,
  started_at      DATETIME(3)       NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  finished_at     DATETIME(3)       NULL,
  status          VARCHAR(16)       NOT NULL DEFAULT 'running',
  config_snapshot JSON              NULL COMMENT '调度器环境变量快照',
  note            VARCHAR(512)      NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_bt_key (batch_key),
  KEY idx_bt_algo (algo, swarm_size, started_at),
  CONSTRAINT ck_bt_algo   CHECK (algo IN ('Adaptive Swarm','Pietro','Howard')),
  CONSTRAINT ck_bt_size   CHECK (swarm_size BETWEEN 1 AND 64),
  CONSTRAINT ck_bt_seed   CHECK (seed_from <= seed_to),
  CONSTRAINT ck_bt_status CHECK (status IN ('running','done','aborted'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='一批调度运行';

-- ---------------------------------------------------------------------------
-- 4. task_run 单任务（核心）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS task_run (
  id                BIGINT UNSIGNED   NOT NULL AUTO_INCREMENT,
  batch_id          BIGINT UNSIGNED   NOT NULL,
  scenario_id       BIGINT UNSIGNED   NOT NULL,
  criteria_id       BIGINT UNSIGNED   NOT NULL,
  algo              VARCHAR(32)       NOT NULL,
  mode              VARCHAR(8)        NOT NULL,
  variant           VARCHAR(16)       NOT NULL DEFAULT '',
  seed              INT UNSIGNED      NOT NULL,
  swarm_size        SMALLINT UNSIGNED NOT NULL,
  size_tier         VARCHAR(16)       NULL COMMENT 'paper-4 等标签，自定义时为 NULL',
  replay_key        CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  status            VARCHAR(16)       NOT NULL DEFAULT 'ok',
  failed            TINYINT(1)        NOT NULL DEFAULT 0,
  failure_type      VARCHAR(24)       NULL,
  failure_label     VARCHAR(64)       NULL COMMENT '自由文本失败描述',
  failure_criterion TINYINT UNSIGNED  NULL,
  crashed           TINYINT(1)        NOT NULL DEFAULT 0,
  timed_out         TINYINT(1)        NOT NULL DEFAULT 0,
  arrived           TINYINT(1)        NOT NULL DEFAULT 0,
  iterations        INT UNSIGNED      NULL,
  sim_time          DOUBLE            NULL,
  wall_s            DOUBLE            NOT NULL DEFAULT 0,
  ctime_ref         DOUBLE            NULL,
  final_max_dist    DOUBLE            NULL,
  final_mean_dist   DOUBLE            NULL,
  within2           SMALLINT UNSIGNED NULL,
  within01          SMALLINT UNSIGNED NULL,
  agent_total       SMALLINT UNSIGNED NULL,
  error_message     VARCHAR(512)      NULL,
  result_json       JSON              NULL COMMENT '原始 result.json 全量',
  trace_state       VARCHAR(8)        NOT NULL DEFAULT 'none',
  created_at        DATETIME(3)       NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  UNIQUE KEY uk_tr_replay (replay_key),
  KEY idx_tr_batch (batch_id, mode),
  KEY idx_tr_group (algo, swarm_size, mode, failed),
  KEY idx_tr_pair (algo, swarm_size, seed, mode),
  KEY idx_tr_ftype (failed, failure_type),
  KEY idx_tr_trace (trace_state),
  KEY idx_tr_scenario (scenario_id),
  KEY idx_tr_criteria (criteria_id),
  CONSTRAINT fk_tr_batch    FOREIGN KEY (batch_id)    REFERENCES batch(id)            ON DELETE CASCADE,
  CONSTRAINT fk_tr_scenario FOREIGN KEY (scenario_id) REFERENCES scenario(id)         ON DELETE RESTRICT,
  CONSTRAINT fk_tr_criteria FOREIGN KEY (criteria_id) REFERENCES criteria_profile(id) ON DELETE RESTRICT,
  CONSTRAINT ck_tr_algo   CHECK (algo IN ('Adaptive Swarm','Pietro','Howard')),
  CONSTRAINT ck_tr_mode   CHECK (mode IN ('na','sa','ma')),
  CONSTRAINT ck_tr_size   CHECK (swarm_size BETWEEN 1 AND 64),
  CONSTRAINT ck_tr_status CHECK (status IN ('ok','task_timeout','startup_fail')),
  CONSTRAINT ck_tr_ftype  CHECK (failure_type IS NULL OR failure_type IN ('obstacle','drone_collision','boundary','timeout','none','custom')),
  CONSTRAINT ck_tr_crit   CHECK (failure_criterion IS NULL OR failure_criterion IN (1,2,3)),
  CONSTRAINT ck_tr_trace  CHECK (trace_state IN ('none','partial','full'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='单次测试任务';

-- ---------------------------------------------------------------------------
-- 5. failure_event 失败明细
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS failure_event (
  id             BIGINT UNSIGNED   NOT NULL AUTO_INCREMENT,
  task_run_id    BIGINT UNSIGNED   NOT NULL,
  criterion      TINYINT UNSIGNED  NOT NULL,
  step           INT UNSIGNED      NOT NULL,
  sim_time       DOUBLE            NULL,
  agent_a        SMALLINT UNSIGNED NULL,
  agent_b        SMALLINT UNSIGNED NULL COMMENT '机间碰撞的对方',
  position       JSON              NULL,
  min_obst_dist  DOUBLE            NULL,
  min_drone_dist DOUBLE            NULL,
  detail         JSON              NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_fe (task_run_id, criterion, step),
  KEY idx_fe_crit (criterion, step),
  KEY idx_fe_time (task_run_id, sim_time),
  CONSTRAINT fk_fe_run FOREIGN KEY (task_run_id) REFERENCES task_run(id) ON DELETE CASCADE,
  CONSTRAINT ck_fe_crit CHECK (criterion IN (1,2,3))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='失败事件明细';

-- ---------------------------------------------------------------------------
-- 6. iteration_metric 每轮鲁棒度（绘图用）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS iteration_metric (
  id           BIGINT UNSIGNED   NOT NULL AUTO_INCREMENT,
  task_run_id  BIGINT UNSIGNED   NOT NULL,
  iter         SMALLINT UNSIGNED NOT NULL,
  sim_time     DOUBLE            NULL,
  attacker_pos JSON              NOT NULL COMMENT '[x,y,z]',
  robustness   DOUBLE            NOT NULL,
  victim_agent SMALLINT UNSIGNED NULL,
  candidates   SMALLINT UNSIGNED NOT NULL DEFAULT 20,
  chosen_rank  SMALLINT UNSIGNED NULL,
  extra        JSON              NULL COMMENT '候选鲁棒度数组（可选）',
  PRIMARY KEY (id),
  UNIQUE KEY uk_im (task_run_id, iter),
  KEY idx_im_rob (task_run_id, robustness),
  CONSTRAINT fk_im_run FOREIGN KEY (task_run_id) REFERENCES task_run(id) ON DELETE CASCADE,
  CONSTRAINT ck_im_iter CHECK (iter >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='每轮鲁棒度';

-- ---------------------------------------------------------------------------
-- 7. trace_frame 逐帧状态（回放用）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS trace_frame (
  id          BIGINT UNSIGNED   NOT NULL AUTO_INCREMENT,
  task_run_id BIGINT UNSIGNED   NOT NULL,
  step        SMALLINT UNSIGNED NOT NULL,
  sim_time    DOUBLE            NULL,
  agents      JSON              NOT NULL COMMENT '[{"k":"uav","id":0,"p":[x,y,z],"v":[...]},{"k":"attacker","id":9,"p":[...],"rob":1.02}]',
  PRIMARY KEY (id),
  UNIQUE KEY uk_tf (task_run_id, step),
  CONSTRAINT fk_tf_run FOREIGN KEY (task_run_id) REFERENCES task_run(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='逐帧状态，回放用';

-- ---------------------------------------------------------------------------
-- 8. artifact 文件产物（task_run 或 scenario 单一归属）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS artifact (
  id          BIGINT UNSIGNED   NOT NULL AUTO_INCREMENT,
  task_run_id BIGINT UNSIGNED   NULL,
  scenario_id BIGINT UNSIGNED   NULL,
  kind        VARCHAR(24)       NOT NULL,
  rel_path    VARCHAR(512)      NOT NULL,
  sha256      CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  bytes       BIGINT UNSIGNED   NOT NULL DEFAULT 0,
  mime        VARCHAR(64)       NULL,
  created_at  DATETIME(3)       NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  UNIQUE KEY uk_art_path (rel_path),
  KEY idx_art_run (task_run_id),
  KEY idx_art_scenario (scenario_id),
  KEY idx_art_sha (sha256),
  CONSTRAINT fk_art_run FOREIGN KEY (task_run_id) REFERENCES task_run(id) ON DELETE CASCADE,
  CONSTRAINT fk_art_sc  FOREIGN KEY (scenario_id) REFERENCES scenario(id) ON DELETE CASCADE,
  CONSTRAINT ck_art_owner CHECK (
    (task_run_id IS NOT NULL AND scenario_id IS NULL) OR
    (task_run_id IS NULL AND scenario_id IS NOT NULL)
  ),
  -- [AI-MOD 2026-11-12] 增加 result_json / log：导入器需要登记每次任务的 result.json 与 MATLAB 日志
  CONSTRAINT ck_art_kind CHECK (kind IN ('res_txt','res_jpg','result_json','log','iteration_log','trace_jsonl','map_raw'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='不可查询的原始文件';

-- ---------------------------------------------------------------------------
-- 9. import_log 导入账本
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS import_log (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  source_root VARCHAR(512)    NOT NULL,
  file_count  INT UNSIGNED    NOT NULL DEFAULT 0,
  inserted    INT UNSIGNED    NOT NULL DEFAULT 0,
  updated     INT UNSIGNED    NOT NULL DEFAULT 0,
  skipped     INT UNSIGNED    NOT NULL DEFAULT 0,
  started_at  DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  finished_at DATETIME(3)     NULL,
  status      VARCHAR(16)     NOT NULL DEFAULT 'running',
  note        VARCHAR(512)    NULL,
  PRIMARY KEY (id),
  KEY idx_il_root (source_root(191), started_at),
  CONSTRAINT ck_il_status CHECK (status IN ('running','ok','partial','error'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='导入批次记录';

-- ---------------------------------------------------------------------------
-- 10. schema_meta 版本标记
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schema_meta (
  schema_version VARCHAR(16) NOT NULL,
  applied_at     DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (schema_version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT IGNORE INTO schema_meta (schema_version, applied_at) VALUES ('1.0.0', CURRENT_TIMESTAMP(3));
