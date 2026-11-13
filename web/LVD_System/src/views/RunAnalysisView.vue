<template>
  <div class="page page-wide analysis" v-loading="loading">
    <div class="page-head">
      <div>
        <div class="crumb">
          <router-link to="/console/history">测试历史</router-link>
          <span>/</span>
          <router-link v-if="run.batch_id" :to="`/console/batch/${run.batch_id}`">
            批次 #{{ run.batch_id }}
          </router-link>
          <span>/</span>
          <span>测试 #{{ run.id }}</span>
        </div>
        <h1 class="page-title">测试分析 #{{ run.id }}</h1>
        <div class="head-chips">
          <AlgoTag :algo="run.algo" />
          <span class="chip chip-ghost">{{ run.mode_label }}</span>
          <span class="chip chip-ghost">{{ run.swarm_size }} 机</span>
          <span class="chip chip-ghost mono">seed {{ run.seed }}</span>
          <StatusTag
            :failed="run.failed"
            :failure-type="run.failure_type"
            :text="run.failed ? run.failure_label : '未复现失败'"
          />
          <span class="chip chip-ghost">{{ run.trace_state === 'full' ? '逐帧回放可用' : '回放数据不完整' }}</span>
        </div>
      </div>
      <div class="row">
        <el-button :icon="ArrowLeft" @click="back">返回</el-button>
        <el-button v-if="neighbors.next" text type="primary" @click="goRun(neighbors.next)">
          下一条任务 →
        </el-button>
      </div>
    </div>

    <div v-if="run.failed" class="banner">
      <el-icon class="banner-icon"><WarningFilled /></el-icon>
      <div>
        <b>已复现失败：{{ run.failure_label }}</b>
        <span class="banner-sub">
          命中判据 {{ criterionText(run.failure_criterion) }}
          <template v-if="primaryEvent">
            · 第 {{ primaryEvent.step }} 帧 · 最近无人机 {{ primaryEvent.nearest_agent ?? '—' }}
            · 最小机间距离 {{ fmt(primaryEvent.min_drone_dist) }} m
          </template>
        </span>
      </div>
    </div>

    <div class="layout">
      <div class="col-main">
        <section class="card stage-card">
          <div class="stage-toolbar">
            <div class="row">
              <el-radio-group v-model="viewMode" size="small">
                <el-radio-button value="3d">3D 透视</el-radio-button>
                <el-radio-button value="top">2D 正交</el-radio-button>
              </el-radio-group>
              <span class="dim-note">{{ (scene.dim || 2) === 3 ? '三维场景' : '二维场景' }}</span>
            </div>
            <div class="row">
              <el-switch v-model="showObstacles" size="small" active-text="障碍" />
              <el-switch v-model="showTrail" size="small" active-text="轨迹" />
            </div>
          </div>

          <div class="stage-wrap">
            <TrackStage
              :scene="scene"
              :frames="frames"
              :progress="cursor"
              :view-mode="viewMode"
              :show-obstacles="showObstacles"
              :show-trail="showTrail"
              :markers="stageMarkers"
            />
          </div>

          <div class="playbar">
            <div class="play-row">
              <el-button class="play-btn" type="primary" circle :icon="playing ? VideoPause : VideoPlay" @click="togglePlay" />
              <span class="step-readout mono">
                STEP {{ currentStep }} / {{ lastStep }}
                <em v-if="currentFrame?.sim_time">· t={{ fmt(currentFrame.sim_time) }}s</em>
              </span>
              <div class="speed">
                <span class="muted">速度</span>
                <el-select v-model="speed" size="small" style="width: 82px">
                  <el-option :value="0.5" label="0.5×" />
                  <el-option :value="1" label="1×" />
                  <el-option :value="2" label="2×" />
                  <el-option :value="4" label="4×" />
                </el-select>
              </div>
            </div>

            <div class="timeline">
              <div class="track">
                <div class="track-fill" :style="{ width: progressPct + '%' }" />
                <span
                  v-for="m in timelineMarkers"
                  :key="m.key"
                  class="node"
                  :class="m.kind"
                  :style="{ left: m.left + '%' }"
                  :title="`${m.label} · step ${m.step}`"
                  @click.stop="seek(m.index)"
                />
                <span class="playhead" :style="{ left: progressPct + '%' }" />
              </div>
              <div class="timeline-labels">
                <span v-for="m in timelineMarkers" :key="'l' + m.key" :style="{ left: m.left + '%' }">
                  {{ m.short }}
                </span>
              </div>
            </div>

            <el-slider
              v-model="cursor"
              :min="0"
              :max="Math.max(0, frames.length - 1)"
              :step="1"
              :show-tooltip="false"
              @input="onScrub"
            />
          </div>
        </section>

        <section class="card chart-card">
          <div class="card-head">
            <div>
              <p class="card-title">鲁棒度演化</p>
              <p class="card-hint">攻击者每轮采样的最优鲁棒度，竖线对应当前时间轴位置</p>
            </div>
            <div class="row chart-meta">
              <span class="chip chip-ghost">峰值 {{ fmt(metricStats.max) }}</span>
              <span class="chip chip-ghost">均值 {{ fmt(metricStats.avg) }}</span>
            </div>
          </div>
          <div class="card-pad">
            <EChart :option="robustnessOption" height="240px" />
          </div>
        </section>

        <section class="card">
          <div class="card-head">
            <div>
              <p class="card-title">当前帧状态</p>
              <p class="card-hint">拖动时间轴或点击关键节点，可查看该帧的编队位置与攻击者鲁棒度</p>
            </div>
            <span class="mono muted">step {{ currentStep }}</span>
          </div>
          <el-table :data="agentRows" size="small" max-height="260">
            <el-table-column label="编号" width="90">
              <template #default="{ row }">
                <span class="mono">{{ row.label }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="kindText" label="类型" width="100" />
            <el-table-column label="x" width="110">
              <template #default="{ row }"><span class="mono">{{ fmt(row.p?.[0]) }}</span></template>
            </el-table-column>
            <el-table-column label="y" width="110">
              <template #default="{ row }"><span class="mono">{{ fmt(row.p?.[1]) }}</span></template>
            </el-table-column>
            <el-table-column label="z" width="110">
              <template #default="{ row }"><span class="mono">{{ fmt(row.p?.[2]) }}</span></template>
            </el-table-column>
            <el-table-column label="鲁棒度" min-width="110">
              <template #default="{ row }">
                <span v-if="row.rob !== null" class="mono" :class="{ 'rob-hot': row.rob > 0 }">{{ fmt(row.rob) }}</span>
                <span v-else class="muted">—</span>
              </template>
            </el-table-column>
          </el-table>
        </section>
      </div>

      <aside class="col-side">
        <section class="card card-pad">
          <p class="card-title">任务信息</p>
          <div class="divider" />
          <dl class="kv">
            <dt>算法</dt><dd>{{ run.algo }}</dd>
            <dt>场景</dt><dd>{{ run.scenario_name || '—' }}</dd>
            <dt>批次</dt><dd><router-link :to="`/console/batch/${run.batch_id}`">#{{ run.batch_id }}</router-link></dd>
            <dt>模式 / 种子</dt><dd>{{ run.mode_label }} · {{ run.seed }}</dd>
            <dt>迭代轮数</dt><dd>{{ run.iterations ?? '—' }}</dd>
            <dt>墙钟耗时</dt><dd>{{ fmtWall(run.wall_s) }}</dd>
            <dt>回放帧数</dt><dd>{{ frames.length }} 帧</dd>
            <dt>创建时间</dt><dd class="muted">{{ run.created_at }}</dd>
          </dl>
          <div class="divider" />
          <p class="side-label">判据参数</p>
          <dl class="kv small">
            <dt>超时</dt><dd>{{ criteria.enable_timeout ? `${criteria.timeout_multiplier} × CTime` : '未启用' }}</dd>
            <dt>撞障碍</dt><dd>{{ criteria.enable_obstacle ? thrText(criteria.obstacle_dist_thr, '多边形内点判定') : '未启用' }}</dd>
            <dt>机间碰撞</dt><dd>{{ criteria.enable_collision ? thrText(criteria.drone_dist_thr, '未设阈值') : '未启用' }}</dd>
            <dt>候选点数</dt><dd>{{ criteria.candidate_count ?? '—' }}</dd>
          </dl>
        </section>

        <section class="card">
          <div class="card-head">
            <p class="card-title">关键事件</p>
            <span class="muted mono">{{ events.length }} 条</span>
          </div>
          <div class="event-list">
            <button
              v-for="e in events"
              :key="e.id"
              class="event"
              :class="{ active: currentStep === e.step }"
              @click="seek(e.index)"
            >
              <span class="event-dot" :style="{ background: e.color }" />
              <span class="event-body">
                <b>{{ e.title }}</b>
                <small>{{ e.criterion_label }} · step {{ e.step }}<template v-if="e.sim_time"> · t={{ fmt(e.sim_time) }}s</template></small>
                <small v-if="e.dist">最小机间距离 {{ e.dist }} m · 最近无人机 {{ e.nearest_agent ?? '—' }}</small>
              </span>
              <el-icon class="event-go"><ArrowRight /></el-icon>
            </button>
            <p v-if="!events.length" class="event-empty">
              该任务未触发失败判据{{ run.failed ? '（明细缺失）' : '，整段轨迹可正常回放' }}。
            </p>
          </div>
        </section>

        <section class="card card-pad">
          <p class="card-title">场景复现</p>
          <div class="divider" />
          <div class="scene-thumb">
            <SceneThumb
              :dim="scene.dim || 2"
              :bounds="scene.bounds"
              :obstacles="scene.obstacles"
              :targets="scene.targets"
              :init-positions="scene.init_positions"
              :markers="stageMarkers"
            />
          </div>
          <dl class="kv small scene-kv">
            <dt>边界</dt><dd class="mono">{{ boundsText }}</dd>
            <dt>障碍</dt><dd>{{ (scene.obstacles || []).length }} 个</dd>
            <dt>目标点</dt><dd>{{ (scene.targets || []).length }} 个</dd>
            <dt>场景来源</dt><dd>{{ scene.source_type === 'custom_generated' ? '自定义生成' : '内置地图' }}</dd>
          </dl>
          <el-button class="scene-link" text type="primary" @click="router.push('/console/history')">
            查看同批次其他任务 →
          </el-button>
        </section>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, ArrowRight, VideoPause, VideoPlay, WarningFilled } from '@element-plus/icons-vue'
import { api } from '@/api'
import AlgoTag from '@/components/AlgoTag.vue'
import StatusTag from '@/components/StatusTag.vue'
import EChart from '@/components/EChart.vue'
import SceneThumb from '@/components/SceneThumb.vue'
import TrackStage from '@/components/TrackStage.vue'

const route = useRoute()
const router = useRouter()

const loading = ref(true)
const run = reactive({})
const scene = reactive({})
const criteria = reactive({})
const frames = ref([])
const metrics = ref({ items: [], min: null, max: null, avg: null })
const neighbors = reactive({ prev: null, next: null })

const viewMode = ref('3d')
const showObstacles = ref(true)
const showTrail = ref(true)
const playing = ref(false)
const speed = ref(1)
const cursor = ref(0)

let raf = null
let lastTs = 0

const EVENT_COLORS = {
  obstacle: '#e8833a',
  drone_collision: '#d9534f',
  boundary: '#8262c9',
  timeout: '#4a6fa5',
  custom: '#38a3a5',
}

/**
 * 事件记录的 step 可能比最后一帧还大（判据在仿真结束后才写入），
 * 这里取“不大于该 step 的最后一帧”，避免越界回落到第 0 帧。
 */
function indexForStep(step) {
  const list = frames.value
  if (!list.length) return 0
  let idx = 0
  for (let i = 0; i < list.length; i++) {
    if (list[i].step <= step) idx = i
    else break
  }
  return idx
}

const lastStep = computed(() => (frames.value.length ? frames.value[frames.value.length - 1].step : 0))
const currentIndex = computed(() => Math.max(0, Math.min(frames.value.length - 1, Math.round(cursor.value))))
const currentFrame = computed(() => frames.value[currentIndex.value] || null)
const currentStep = computed(() => currentFrame.value?.step ?? 0)
const progressPct = computed(() => {
  const max = Math.max(1, frames.value.length - 1)
  return Math.min(100, (cursor.value / max) * 100)
})

function fmt(v) {
  if (v === null || v === undefined || v === '') return '—'
  const n = Number(v)
  if (Number.isNaN(n)) return String(v)
  return Math.abs(n) >= 100 ? n.toFixed(1) : n.toFixed(2)
}

function fmtWall(v) {
  const s = Number(v || 0)
  if (!s) return '—'
  if (s >= 3600) return `${(s / 3600).toFixed(2)} h`
  if (s >= 60) return `${(s / 60).toFixed(1)} min`
  return `${s.toFixed(0)} s`
}

function thrText(v, fallback) {
  return v === null || v === undefined ? fallback : `${v} m 内`
}

function criterionText(c) {
  return { 1: '① 任务超时', 2: '② 状态越界', 3: '③ 轨迹偏离' }[c] || '—'
}

const events = computed(() => {
  const list = (run.events || []).map((e) => ({
    ...e,
    index: indexForStep(e.step),
    color: EVENT_COLORS[e.type] || '#d9534f',
    title: e.label || e.criterion_label,
    dist: e.min_drone_dist === null || e.min_drone_dist === undefined ? null : fmt(e.min_drone_dist),
  }))
  if (!run.failed && frames.value.length) {
    // 成功任务：把最后一帧作为“任务结束”节点，便于时间轴对齐
    list.push({
      id: 'end',
      step: lastStep.value,
      index: frames.value.length - 1,
      color: '#2f9e73',
      title: endTitle.value,
      criterion_label: '任务正常结束',
      nearest_agent: null,
      dist: null,
    })
  }
  return list
})

const endTitle = computed(() => {
  const msg = run.result?.message || ''
  return msg.includes('到达') ? '无人机到达目标' : '任务正常结束'
})

const primaryEvent = computed(() => (run.events || [])[0] || null)

const timelineMarkers = computed(() => {
  const max = Math.max(1, frames.value.length - 1)
  const list = []
  frames.value.length &&
    list.push({
      key: 'takeoff',
      kind: 'takeoff',
      short: '起飞',
      label: '起飞（初始编队）',
      step: frames.value[0].step,
      index: 0,
      left: 0,
    })
  for (const e of events.value) {
    const short = e.title.replace(/（.*?）/g, '').slice(0, 6)
    list.push({
      key: `${e.id}-${e.step}`,
      kind: e.color === '#2f9e73' ? 'success' : 'failure',
      short,
      label: `${e.title}（step ${e.step}）`,
      step: e.step,
      index: e.index,
      left: Math.max(0, Math.min(100, (e.index / max) * 100)),
    })
  }
  return list
})

const stageMarkers = computed(() =>
  (run.events || [])
    .filter((e) => Array.isArray(e.position))
    .map((e) => ({
      step: e.step,
      position: e.position,
      // SceneThumb 用 p，TrackStage 用 position，这里同时给出，避免两套约定不一致
      p: e.position,
      color: EVENT_COLORS[e.type] || '#d9534f',
      label: e.label,
    })),
)

const agentRows = computed(() => {
  const f = currentFrame.value
  if (!f) return []
  const attacker = (f.agents || []).find((a) => a.k === 'attacker')
  const rob = attackerRobustness(attacker)
  return (f.agents || []).map((a) => ({
    label: a.k === 'attacker' ? `ATT-${a.id}` : `UAV-${a.id}`,
    kindText: a.k === 'attacker' ? '攻击者' : '无人机',
    p: a.p,
    rob: a.k === 'attacker' ? rob : null,
  }))
})

const metricStats = computed(() => ({
  min: metrics.value.min,
  max: metrics.value.max,
  avg: metrics.value.avg,
}))

const metricCursor = computed(() => {
  const items = metrics.value.items || []
  if (!items.length) return null
  let idx = 0
  items.forEach((m, i) => {
    const step = m.extra?.step ?? m.iter
    if (step <= currentStep.value) idx = i
  })
  return idx
})

const robustnessOption = computed(() => {
  const items = metrics.value.items || []
  const xs = items.map((m) => (m.extra?.step ?? m.iter))
  const ys = items.map((m) => m.robustness)
  const cursorIdx = metricCursor.value
  return {
    grid: { left: 44, right: 16, top: 18, bottom: 28 },
    tooltip: { trigger: 'axis', valueFormatter: (v) => Number(v).toFixed(4) },
    xAxis: {
      type: 'category',
      data: xs,
      name: 'step',
      nameGap: 22,
      axisLine: { lineStyle: { color: '#e6ebf3' } },
      axisLabel: { color: '#8d99ac', fontSize: 10 },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      scale: true,
      splitLine: { lineStyle: { color: '#f0f4f9' } },
      axisLabel: { color: '#8d99ac', fontSize: 10 },
    },
    series: [
      {
        type: 'line',
        data: ys,
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#2f6fbf', width: 1.8 },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(47,111,191,0.20)' },
              { offset: 1, color: 'rgba(47,111,191,0)' },
            ],
          },
        },
        markLine:
          cursorIdx === null
            ? undefined
            : {
                silent: true,
                symbol: 'none',
                data: [{ xAxis: cursorIdx }],
                lineStyle: { color: '#d9534f', width: 1.2, type: 'dashed' },
                label: { show: false },
              },
      },
    ],
  }
})

const boundsText = computed(() => {
  const b = scene.bounds || {}
  const parts = ['x', 'y', 'z'].filter((a) => Array.isArray(b[a]))
  return parts.map((a) => `${a}: ${b[a][0]}–${b[a][1]}`).join('  ') || '—'
})

function attackerRobustness(attacker) {
  if (!attacker) return null
  const items = metrics.value.items || []
  const idx = metricCursor.value
  if (idx === null || !items[idx]) return null
  return items[idx].robustness
}

function seek(index) {
  cursor.value = Math.max(0, Math.min(frames.value.length - 1, index))
}

function onScrub() {
  stopPlay()
}

function togglePlay() {
  if (playing.value) return stopPlay()
  if (currentIndex.value >= frames.value.length - 1) cursor.value = 0
  playing.value = true
  lastTs = 0
  raf = requestAnimationFrame(tick)
}

function tick(ts) {
  if (!playing.value) return
  if (!lastTs) lastTs = ts
  const dt = (ts - lastTs) / 1000
  lastTs = ts
  const next = cursor.value + dt * 24 * speed.value
  if (next >= frames.value.length - 1) {
    cursor.value = frames.value.length - 1
    stopPlay()
    return
  }
  cursor.value = next
  raf = requestAnimationFrame(tick)
}

function stopPlay() {
  playing.value = false
  if (raf) cancelAnimationFrame(raf)
  raf = null
}

// 上一条 / 下一条：同一批次内的任务
async function loadNeighbors() {
  if (!run.batch_id) return
  try {
    const data = await api.runs({ batch_id: run.batch_id, page_size: 200 })
    const ids = data.items.map((x) => x.id).sort((a, b) => a - b)
    const i = ids.indexOf(run.id)
    neighbors.prev = i > 0 ? ids[i - 1] : null
    neighbors.next = i >= 0 && i < ids.length - 1 ? ids[i + 1] : null
  } catch {
    neighbors.prev = null
    neighbors.next = null
  }
}

function goRun(id) {
  router.push(`/console/run/${id}`)
}

function back() {
  if (run.batch_id) router.push(`/console/batch/${run.batch_id}`)
  else router.push('/console/history')
}

async function load() {
  loading.value = true
  stopPlay()
  cursor.value = 0
  try {
    const id = Number(route.params.id)
    const detail = await api.run(id)
    Object.assign(run, detail.run)
    run.events = detail.events || []
    run.result = detail.result
    run.scenario_name = detail.run.scenario_name
    Object.assign(scene, detail.scenario || {})
    Object.assign(criteria, detail.criteria || {})
    const frameData = await api.frames(id, { from: 0, stride: 1 })
    frames.value = frameData.frames || []
    const metricData = await api.metrics(id)
    metrics.value = metricData
    viewMode.value = (scene.dim || 2) === 3 ? '3d' : 'top'
    await loadNeighbors()
  } catch (e) {
    ElMessage.error(e.message || '加载任务失败')
  } finally {
    loading.value = false
  }
}

watch(() => route.params.id, load)
onMounted(load)
onBeforeUnmount(stopPlay)
</script>

<style scoped>
.analysis {
  padding: 26px 32px 56px;
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
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  flex-wrap: wrap;
}

.banner {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 18px;
  padding: 14px 18px;
  border: 1px solid #f3d7d5;
  border-radius: 12px;
  background: #fdf4f3;
  color: #8f3330;
}

.banner-icon {
  font-size: 20px;
  color: var(--rs-danger);
}

.banner-sub {
  display: block;
  margin-top: 2px;
  color: #a65955;
  font-size: 12.5px;
}

.layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 372px;
  gap: 20px;
  align-items: start;
}

.col-main,
.col-side {
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-width: 0;
}

.stage-card {
  overflow: hidden;
}

.stage-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 18px;
  border-bottom: 1px solid var(--rs-line);
}

.dim-note {
  color: var(--rs-text-3);
  font-size: 12px;
}

.stage-wrap {
  height: 500px;
  padding: 12px;
}

.playbar {
  padding: 4px 20px 16px;
  border-top: 1px solid var(--rs-line);
}

.play-row {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px 0 6px;
}

.play-btn {
  width: 40px;
  height: 40px;
  font-size: 17px;
}

.step-readout {
  color: var(--rs-text-2);
  font-size: 12px;
  letter-spacing: 0.04em;
}

.step-readout em {
  margin-left: 6px;
  color: var(--rs-text-3);
  font-style: normal;
}

.speed {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
  font-size: 12px;
}

.timeline {
  position: relative;
  margin: 12px 6px 4px;
  height: 38px;
  cursor: pointer;
}

.track {
  position: relative;
  top: 8px;
  height: 6px;
  border-radius: 4px;
  background: #eef2f8;
}

.track-fill {
  position: absolute;
  left: 0;
  top: 0;
  height: 100%;
  border-radius: 4px;
  background: linear-gradient(90deg, #9dc0e8, #2f6fbf);
}

.node {
  position: absolute;
  top: 50%;
  width: 9px;
  height: 9px;
  margin-left: -4.5px;
  border-radius: 50%;
  transform: translateY(-50%);
  border: 1.5px solid #fff;
  box-shadow: 0 0 0 1px rgba(22, 32, 46, 0.08);
  z-index: 2;
}

.node.takeoff {
  background: #4cc38a;
}

.node.failure {
  background: #d9534f;
}

.node.success {
  background: #2f9e73;
}

.playhead {
  position: absolute;
  top: -7px;
  width: 2px;
  height: 20px;
  margin-left: -1px;
  background: #12294a;
  border-radius: 2px;
}

.timeline-labels {
  position: absolute;
  inset: 20px 0 auto 0;
  height: 16px;
}

.timeline-labels span {
  position: absolute;
  transform: translateX(-50%);
  color: var(--rs-text-3);
  font-size: 10.5px;
  white-space: nowrap;
}

.chart-meta {
  gap: 8px;
}

.rob-hot {
  color: #c0453f;
}

.side-label {
  margin: 0 0 8px;
  color: var(--rs-text-3);
  font-size: 12px;
}

.kv.small {
  grid-template-columns: 74px 1fr;
  font-size: 12.5px;
}

.event-list {
  max-height: 320px;
  overflow: auto;
  padding: 8px;
}

.event {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  width: 100%;
  padding: 10px 12px;
  margin-bottom: 6px;
  border: 1px solid transparent;
  border-radius: 10px;
  background: var(--rs-surface-2);
  text-align: left;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}

.event:hover,
.event.active {
  background: #f2f7fd;
  border-color: #d7e4f4;
}

.event-dot {
  width: 8px;
  height: 8px;
  margin-top: 6px;
  border-radius: 50%;
  flex: 0 0 auto;
}

.event-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.event-body b {
  font-size: 13px;
  font-weight: 600;
}

.event-body small {
  color: var(--rs-text-3);
  font-size: 11.5px;
  line-height: 1.55;
}

.event-go {
  margin-left: auto;
  color: var(--rs-text-3);
  font-size: 12px;
}

.event-empty {
  margin: 10px;
  color: var(--rs-text-3);
  font-size: 12.5px;
  line-height: 1.8;
}

.scene-thumb {
  height: 200px;
  border: 1px solid var(--rs-line);
  border-radius: 10px;
  overflow: hidden;
}

.scene-kv {
  margin-top: 14px;
}

.scene-link {
  margin-top: 10px;
  padding: 0;
}

@media (max-width: 1280px) {
  .layout {
    grid-template-columns: 1fr;
  }

  .col-side {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
