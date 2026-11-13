<template>
  <div class="page page-wide" v-loading="loading">
    <div class="page-head">
      <div>
        <div class="crumb">
          <router-link to="/console/history">测试历史</router-link>
          <span>/</span>
          <span>批次 #{{ batchId }}</span>
        </div>
        <h1 class="page-title">批次分析 #{{ batchId }}</h1>
        <div class="head-chips">
          <AlgoTag :algo="batch.algo" />
          <span class="chip" :class="batch.status === 'done' ? 'chip-ok' : 'chip-ghost'">
            {{ statusText(batch.status) }}
          </span>
          <span class="chip chip-ghost">{{ batch.swarm_size }} 机</span>
          <span class="chip chip-ghost">{{ (batch.modes || []).map((m) => MODE[m] || m).join(' / ') }}</span>
          <span class="chip chip-ghost mono">seeds {{ batch.seed_from }}–{{ batch.seed_to }}</span>
        </div>
      </div>
      <el-button :icon="ArrowLeft" @click="router.push('/console/history')">返回测试历史</el-button>
    </div>

    <div class="stat-grid">
      <div v-for="s in statCards" :key="s.label" class="card stat">
        <p class="stat-label">{{ s.label }}</p>
        <p class="stat-value" :class="{ danger: s.danger }">{{ s.value }}</p>
        <p class="stat-foot">{{ s.foot }}</p>
      </div>
    </div>

    <div class="grid-2">
      <section class="card">
        <div class="card-head">
          <p class="card-title">批次基本信息</p>
          <span class="mono muted">{{ shortKey }}</span>
        </div>
        <div class="card-pad">
          <dl class="kv">
            <dt>批次编号</dt><dd>#{{ batch.id }}</dd>
            <dt>算法</dt><dd>{{ batch.algo }}</dd>
            <dt>集群规模</dt><dd>{{ batch.swarm_size }} 机</dd>
            <dt>测试模式</dt><dd>{{ (batch.modes || []).map((m) => MODE[m] || m).join(' / ') }}</dd>
            <dt>种子范围</dt><dd class="mono">{{ batch.seed_from }} – {{ batch.seed_to }}</dd>
            <dt>调度器</dt><dd>{{ batch.scheduler || '—' }}</dd>
            <dt>开始时间</dt><dd>{{ batch.started_at || '—' }}</dd>
            <dt>结束时间</dt><dd>{{ batch.finished_at || '进行中' }}</dd>
            <dt>任务统计</dt><dd>{{ batch.tasks }} 个任务，{{ batch.failed }} 个失败</dd>
            <dt>备注</dt><dd class="muted">{{ batch.note || '—' }}</dd>
          </dl>
        </div>
      </section>

      <section class="card">
        <div class="card-head">
          <p class="card-title">参数设定</p>
          <span class="muted">判据快照</span>
        </div>
        <div class="card-pad">
          <div v-for="c in criteria" :key="c.id" class="crit">
            <div class="crit-head">
              <span class="crit-name">{{ c.name }}</span>
              <span class="chip chip-ghost">{{ c.used_by }} 个任务使用</span>
            </div>
            <div class="switch-row">
              <span class="chip" :class="c.enable_timeout ? '' : 'chip-ghost'">① 超时 {{ c.enable_timeout ? 'ON' : 'OFF' }}</span>
              <span class="chip" :class="c.enable_obstacle ? '' : 'chip-ghost'">② 撞障碍 {{ c.enable_obstacle ? 'ON' : 'OFF' }}</span>
              <span class="chip" :class="c.enable_collision ? '' : 'chip-ghost'">② 机间碰撞 {{ c.enable_collision ? 'ON' : 'OFF' }}</span>
            </div>
            <dl class="kv small">
              <dt>超时倍数</dt><dd>{{ c.timeout_multiplier }} × CTime</dd>
              <dt>机间阈值</dt><dd>{{ c.drone_dist_thr ?? '未设置' }}{{ c.drone_dist_thr ? ' m' : '' }}</dd>
              <dt>障碍阈值</dt><dd>{{ c.obstacle_dist_thr ?? '未设置' }}{{ c.obstacle_dist_thr ? ' m' : '' }}</dd>
              <dt>候选点数</dt><dd>{{ c.candidate_count }}</dd>
              <dt>最大迭代</dt><dd>{{ c.max_iterations ?? '不限' }}</dd>
              <dt>最大时长</dt><dd>{{ c.max_sim_time ? c.max_sim_time + ' s' : '不限' }}</dd>
              <dt>攻击参数</dt><dd>{{ extraText(c.extra) }}</dd>
            </dl>
          </div>
          <p v-if="!criteria.length" class="muted">暂无判据快照。</p>
        </div>
      </section>
    </div>

    <section class="card scenes">
      <div class="card-head">
        <p class="card-title">场景快照</p>
        <span class="muted">{{ scenarios.length }} 个场景参与本批次</span>
      </div>
      <div class="scene-grid">
        <div v-for="s in scenarios" :key="s.id" class="scene">
          <div class="scene-pic">
            <SceneThumb
              :dim="s.dim"
              :bounds="s.bounds"
              :obstacles="geometryOf(s.id).obstacles"
              :targets="geometryOf(s.id).targets"
              :init-positions="geometryOf(s.id).init_positions"
            />
          </div>
          <div class="scene-info">
            <p class="scene-name">{{ s.name }}</p>
            <p class="scene-sub">
              {{ s.dim }}D · {{ s.obstacle_count }} 个障碍 · {{ s.source_type === 'builtin' ? '内置' : '自定义' }}
            </p>
            <p class="scene-sub mono">{{ boundsText(s.bounds) }}</p>
            <p class="scene-sub">本批次 {{ s.used_by }} 个任务使用</p>
          </div>
        </div>
      </div>
    </section>

    <div class="grid-2 charts">
      <section class="card">
        <div class="card-head"><p class="card-title">失败类型分布</p></div>
        <div class="card-pad">
          <EChart :option="failureOption" height="260px" />
        </div>
      </section>
      <section class="card">
        <div class="card-head"><p class="card-title">模式对比</p></div>
        <div class="card-pad">
          <EChart :option="modeOption" height="260px" />
        </div>
      </section>
      <section class="card">
        <div class="card-head"><p class="card-title">迭代轮数分布</p></div>
        <div class="card-pad">
          <EChart :option="iterOption" height="240px" />
        </div>
      </section>
      <section class="card">
        <div class="card-head"><p class="card-title">单任务耗时分布</p></div>
        <div class="card-pad">
          <EChart :option="wallOption" height="240px" />
        </div>
      </section>
    </div>

    <section class="card">
      <div class="card-head">
        <p class="card-title">任务明细</p>
        <span class="muted">点击行进入测试分析</span>
      </div>
      <el-table :data="tasks" size="small" @row-click="openRun" row-class-name="clickable">
        <el-table-column label="任务" width="90">
          <template #default="{ row }"><span class="mono">#{{ row.id }}</span></template>
        </el-table-column>
        <el-table-column label="模式" width="140">
          <template #default="{ row }">{{ row.mode_label }}</template>
        </el-table-column>
        <el-table-column label="种子" width="90">
          <template #default="{ row }"><span class="mono">{{ row.seed }}</span></template>
        </el-table-column>
        <el-table-column label="结果" width="140">
          <template #default="{ row }">
            <StatusTag :failed="row.failed" :failure-type="row.failure_type" :text="row.failed ? row.failure_label : ''" />
          </template>
        </el-table-column>
        <el-table-column label="命中判据" min-width="170">
          <template #default="{ row }">{{ criterionText(row.failure_criterion) }}</template>
        </el-table-column>
        <el-table-column label="迭代" width="90">
          <template #default="{ row }">{{ row.iterations ?? '—' }}</template>
        </el-table-column>
        <el-table-column label="耗时" width="110">
          <template #default="{ row }">{{ fmtWall(row.wall_s) }}</template>
        </el-table-column>
        <el-table-column label="回放帧" width="110">
          <template #default="{ row }">
            <span class="chip" :class="row.trace_state === 'full' ? 'chip-ok' : 'chip-ghost'">
              {{ row.trace_state === 'full' ? '可回放' : '不完整' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column width="110" align="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click.stop="openRun(row)">测试详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import { api } from '@/api'
import AlgoTag from '@/components/AlgoTag.vue'
import StatusTag from '@/components/StatusTag.vue'
import EChart from '@/components/EChart.vue'
import SceneThumb from '@/components/SceneThumb.vue'

const route = useRoute()
const router = useRouter()
const MODE = { na: 'NA 无攻击', sa: 'SA 单攻击者', ma: 'MA 多攻击者' }

const loading = ref(true)
const batchId = computed(() => route.params.id)
const batch = reactive({})
const tasks = ref([])
const criteria = ref([])
const scenarios = ref([])
const geometry = ref([])
const stats = reactive({
  tasks: 0,
  failed: 0,
  failure_rate: 0,
  total_wall_s: 0,
  avg_wall_s: 0,
  avg_iterations: null,
  failure_dist: [],
  modes: [],
  iteration_hist: [],
  wall_hist: [],
  criterion_dist: [],
})

const statCards = computed(() => [
  { label: '任务数', value: stats.tasks, foot: `${(batch.modes || []).length} 种模式` },
  { label: '失败复现', value: stats.failed, foot: `失败率 ${pct(stats.failure_rate)}`, danger: stats.failed > 0 },
  { label: '平均迭代', value: stats.avg_iterations ?? '—', foot: '每任务攻击轮数' },
  { label: '平均耗时', value: fmtWall(stats.avg_wall_s), foot: `累计 ${fmtWall(stats.total_wall_s)}` },
])

const shortKey = computed(() => (batch.batch_key ? batch.batch_key.slice(0, 10) + '…' : ''))

function pct(v) {
  return `${(Number(v || 0) * 100).toFixed(0)}%`
}

function fmtWall(v) {
  const s = Number(v || 0)
  if (!s) return '—'
  if (s >= 3600) return `${(s / 3600).toFixed(2)} h`
  if (s >= 60) return `${(s / 60).toFixed(1)} min`
  return `${s.toFixed(0)} s`
}

function statusText(s) {
  return { running: '进行中', done: '已完成', aborted: '已中止' }[s] || s
}

function criterionText(c) {
  return { 1: '① 任务超时', 2: '② 状态越界', 3: '③ 轨迹偏离' }[c] || '—'
}

function extraText(extra) {
  if (!extra || !Object.keys(extra).length) return '—'
  return Object.entries(extra)
    .map(([k, v]) => `${k}=${v}`)
    .join(' · ')
}

function geometryOf(id) {
  return geometry.value.find((g) => g.id === id) || { obstacles: [], targets: [], init_positions: [] }
}

function boundsText(b) {
  if (!b) return '—'
  return ['x', 'y', 'z']
    .filter((a) => Array.isArray(b[a]))
    .map((a) => `${a} ${b[a][0]}–${b[a][1]}`)
    .join('  ')
}

function openRun(row) {
  router.push(`/console/run/${row.id}`)
}

const axisStyle = {
  axisLabel: { color: '#8d99ac', fontSize: 10 },
  axisLine: { lineStyle: { color: '#e6ebf3' } },
  axisTick: { show: false },
}

const failureOption = computed(() => ({
  tooltip: { trigger: 'item' },
  legend: { bottom: 0, icon: 'circle', textStyle: { color: '#55637a', fontSize: 11 } },
  series: [
    {
      type: 'pie',
      radius: ['46%', '70%'],
      center: ['50%', '44%'],
      avoidLabelOverlap: true,
      itemStyle: { borderColor: '#fff', borderWidth: 2 },
      label: { formatter: '{b}\n{c}', color: '#55637a', fontSize: 11 },
      data: (stats.failure_dist || []).map((d) => ({
        name: d.label,
        value: d.count,
        itemStyle: { color: d.color },
      })),
    },
  ],
}))

const modeOption = computed(() => {
  const modes = stats.modes || []
  return {
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0, icon: 'roundRect', textStyle: { color: '#55637a', fontSize: 11 } },
    grid: { left: 40, right: 16, top: 16, bottom: 48 },
    xAxis: { type: 'category', data: modes.map((m) => m.mode.toUpperCase()), ...axisStyle },
    yAxis: { type: 'value', minInterval: 1, splitLine: { lineStyle: { color: '#f0f4f9' } }, ...axisStyle },
    series: [
      {
        name: '任务',
        type: 'bar',
        barWidth: 22,
        data: modes.map((m) => m.total),
        itemStyle: { color: '#c9d9ec', borderRadius: [4, 4, 0, 0] },
      },
      {
        name: '失败',
        type: 'bar',
        barWidth: 22,
        data: modes.map((m) => m.failed),
        itemStyle: { color: '#d9534f', borderRadius: [4, 4, 0, 0] },
      },
    ],
  }
})

function histOption(rows, color, unit) {
  return {
    tooltip: {
      trigger: 'axis',
      formatter: (p) => {
        const it = p[0]
        const r = rows[it.dataIndex]
        return `${r.from} – ${r.to} ${unit}<br/>任务 ${it.value} 个`
      },
    },
    grid: { left: 42, right: 16, top: 16, bottom: 30 },
    xAxis: {
      type: 'category',
      data: rows.map((r) => `${Math.round(r.from)}~${Math.round(r.to)}`),
      ...axisStyle,
    },
    yAxis: { type: 'value', minInterval: 1, splitLine: { lineStyle: { color: '#f0f4f9' } }, ...axisStyle },
    series: [
      {
        type: 'bar',
        barWidth: '58%',
        data: rows.map((r) => r.count),
        itemStyle: { color, borderRadius: [4, 4, 0, 0] },
      },
    ],
  }
}

const iterOption = computed(() => histOption(stats.iteration_hist || [], '#4a7fc1', '轮'))
const wallOption = computed(() => histOption(stats.wall_hist || [], '#7a9ec9', '秒'))

async function load() {
  loading.value = true
  try {
    const data = await api.batch(batchId.value)
    Object.assign(batch, data.batch)
    tasks.value = data.tasks
    criteria.value = data.criteria
    scenarios.value = data.scenarios
    geometry.value = data.scenario_geometry || []
    Object.assign(stats, data.stats)
  } catch (e) {
    ElMessage.error(e.message || '加载批次失败')
  } finally {
    loading.value = false
  }
}

watch(() => route.params.id, load)
onMounted(load)
</script>

<style scoped>
.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 18px;
  margin-bottom: 20px;
}

.stat {
  padding: 18px 22px;
}

.stat-label {
  margin: 0;
  color: var(--rs-text-3);
  font-size: 12px;
}

.stat-value {
  margin: 6px 0 2px;
  font-size: 26px;
  font-weight: 600;
  letter-spacing: -0.02em;
}

.stat-value.danger {
  color: var(--rs-danger);
}

.stat-foot {
  margin: 0;
  color: var(--rs-text-3);
  font-size: 12px;
}

.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 20px;
}

.crumb {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  color: var(--rs-text-3);
  font-size: 12px;
}

.crumb a {
  color: var(--rs-text-2);
}

.head-chips {
  display: flex;
  gap: 8px;
  margin-top: 10px;
  flex-wrap: wrap;
}

.crit + .crit {
  margin-top: 20px;
  padding-top: 18px;
  border-top: 1px solid var(--rs-line);
}

.crit-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}

.crit-name {
  font-size: 13px;
  font-weight: 600;
}

.switch-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.kv.small {
  grid-template-columns: 84px 1fr;
  font-size: 12.5px;
}

.scenes {
  margin-bottom: 20px;
}

.scene-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 18px;
  padding: 20px 22px;
}

.scene {
  display: flex;
  gap: 14px;
  padding: 12px;
  border: 1px solid var(--rs-line);
  border-radius: 12px;
  background: var(--rs-surface-2);
}

.scene-pic {
  width: 160px;
  height: 120px;
  flex: 0 0 160px;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
}

.scene-info {
  min-width: 0;
}

.scene-name {
  margin: 2px 0 4px;
  font-size: 13px;
  font-weight: 600;
}

.scene-sub {
  margin: 0 0 2px;
  color: var(--rs-text-3);
  font-size: 11.5px;
  line-height: 1.6;
}

.charts {
  margin-bottom: 20px;
}

:deep(.clickable) {
  cursor: pointer;
}

@media (max-width: 1180px) {
  .grid-2 {
    grid-template-columns: 1fr;
  }

  .stat-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
