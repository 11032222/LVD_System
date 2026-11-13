<template>
  <div class="page">
    <div class="card filter">
      <div class="filter-row">
        <el-select v-model="filters.algo" placeholder="全部算法" clearable style="width: 190px">
          <el-option v-for="a in algoOptions" :key="a" :label="a" :value="a" />
        </el-select>
        <el-select v-model="filters.status" placeholder="全部状态" clearable style="width: 150px">
          <el-option label="进行中" value="running" />
          <el-option label="已完成" value="done" />
          <el-option label="已中止" value="aborted" />
        </el-select>
        <el-input
          v-model="filters.q"
          placeholder="批次号 / 备注关键字"
          clearable
          style="width: 230px"
          @keyup.enter="reload"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-button type="primary" :icon="Search" @click="reload">查询</el-button>
        <el-button :icon="RefreshLeft" @click="reset">重置</el-button>
        <span class="summary">共 {{ total }} 个批次 · 按开始时间倒序</span>
      </div>
    </div>

    <div v-loading="loading" class="list">
      <article v-for="b in batches" :key="b.id" class="batch card">
        <header class="batch-head">
          <div class="batch-id">
            <span class="mono">BATCH #{{ b.id }}</span>
            <AlgoTag :algo="b.algo" />
            <span class="chip" :class="statusClass(b.status)">{{ statusText(b.status) }}</span>
            <span v-if="b.note" class="note">{{ b.note }}</span>
          </div>
          <div class="batch-actions">
            <span class="muted time">{{ b.started_at || '—' }}</span>
            <el-button type="primary" plain :icon="DataAnalysis" @click="openBatch(b.id)">
              批次详情
            </el-button>
          </div>
        </header>

        <div class="batch-meta">
          <div><span>集群规模</span><b>{{ b.swarm_size }} 机</b></div>
          <div>
            <span>测试模式</span>
            <b>{{ (b.modes || []).map((m) => MODE[m] || m).join(' / ') || '—' }}</b>
          </div>
          <div><span>种子范围</span><b class="mono">{{ b.seed_from }} – {{ b.seed_to }}</b></div>
          <div><span>任务数</span><b>{{ b.tasks }}</b></div>
          <div>
            <span>失败复现</span>
            <b :class="{ danger: b.failed > 0 }">{{ b.failed }} / {{ b.tasks }}</b>
          </div>
          <div class="rate">
            <span>失败率</span>
            <b :class="{ danger: b.failure_rate >= 0.5 }">{{ pct(b.failure_rate) }}</b>
          </div>
        </div>

        <el-table :data="b.items" size="small" style="width: 100%" @row-click="openRun" row-class-name="clickable">
          <el-table-column label="任务" width="92">
            <template #default="{ row }"><span class="mono">#{{ row.id }}</span></template>
          </el-table-column>
          <el-table-column label="模式" width="122">
            <template #default="{ row }">
              <span>{{ row.mode_label }}</span>
              <span v-if="row.variant" class="chip chip-ghost tiny">{{ row.variant }}</span>
            </template>
          </el-table-column>
          <el-table-column label="种子" width="82">
            <template #default="{ row }"><span class="mono">{{ row.seed }}</span></template>
          </el-table-column>
          <el-table-column label="结果" width="132">
            <template #default="{ row }">
              <StatusTag
                :failed="row.failed"
                :failure-type="row.failure_type"
                :text="row.failed ? row.failure_label : ''"
              />
            </template>
          </el-table-column>
          <el-table-column label="命中判据" min-width="170">
            <template #default="{ row }">
              <span v-if="row.failure_criterion" class="muted">{{ criterionText(row.failure_criterion) }}</span>
              <span v-else class="muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="迭代" width="76">
            <template #default="{ row }">{{ row.iterations ?? '—' }}</template>
          </el-table-column>
          <el-table-column label="耗时" width="96">
            <template #default="{ row }">{{ row.wall_s ? fmtWall(row.wall_s) : '—' }}</template>
          </el-table-column>
          <el-table-column label="回放" width="92">
            <template #default="{ row }">
              <span class="chip" :class="row.trace_state === 'full' ? 'chip-ok' : 'chip-ghost'">
                {{ row.trace_state === 'full' ? '逐帧' : row.trace_state === 'partial' ? '部分' : '无' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column width="108" align="right">
            <template #default="{ row }">
              <el-button text type="primary" size="small" @click.stop="openRun(row)">测试详情</el-button>
            </template>
          </el-table-column>
          <template #empty>
            <p class="empty">该批次还没有导入任务结果，调度器执行完成后会自动出现。</p>
          </template>
        </el-table>
      </article>

      <div v-if="!loading && !batches.length" class="card empty-card">
        <el-icon class="empty-icon"><Document /></el-icon>
        <p>没有符合条件的测试批次</p>
        <el-button type="primary" @click="router.push('/console/test')">去提交一轮测试</el-button>
      </div>
    </div>

    <div v-if="pages > 1" class="pager">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next"
        background
        @current-change="load"
      />
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { DataAnalysis, Document, RefreshLeft, Search } from '@element-plus/icons-vue'
import { api } from '@/api'
import AlgoTag from '@/components/AlgoTag.vue'
import StatusTag from '@/components/StatusTag.vue'

const route = useRoute()
const router = useRouter()

const MODE = { na: 'NA', sa: 'SA', ma: 'MA' }

const filters = reactive({ algo: route.query.algo || '', status: '', q: '' })
const batches = ref([])
const total = ref(0)
const pages = ref(0)
const page = ref(1)
const pageSize = 10
const loading = ref(false)
const algoOptions = ['Adaptive Swarm', 'Pietro', 'Howard']

function pct(v) {
  return `${(Number(v || 0) * 100).toFixed(0)}%`
}

function fmtWall(v) {
  const s = Number(v || 0)
  if (s >= 3600) return `${(s / 3600).toFixed(1)} h`
  if (s >= 60) return `${(s / 60).toFixed(1)} min`
  return `${s.toFixed(0)} s`
}

function statusText(s) {
  return { running: '进行中', done: '已完成', aborted: '已中止' }[s] || s
}

function statusClass(s) {
  return { running: 'chip', done: 'chip-ok', aborted: 'chip-danger' }[s] || 'chip-ghost'
}

function criterionText(c) {
  return { 1: '① 任务超时', 2: '② 状态越界', 3: '③ 轨迹偏离' }[c] || `判据 ${c}`
}

function openBatch(id) {
  router.push(`/console/batch/${id}`)
}

function openRun(row) {
  router.push(`/console/run/${row.id}`)
}

async function load() {
  loading.value = true
  try {
    const data = await api.batches({
      algo: filters.algo || undefined,
      status: filters.status || undefined,
      q: filters.q || undefined,
      page: page.value,
      page_size: pageSize,
    })
    const detail = await Promise.all(data.items.map((b) => api.batch(b.id)))
    batches.value = data.items.map((b, i) => ({ ...b, items: detail[i].tasks }))
    total.value = data.total
    pages.value = data.pages
  } catch (e) {
    ElMessage.error(e.message || '查询失败')
    batches.value = []
  } finally {
    loading.value = false
  }
}

function reload() {
  page.value = 1
  load()
}

function reset() {
  filters.algo = ''
  filters.status = ''
  filters.q = ''
  reload()
}

onMounted(load)
</script>

<style scoped>
.filter {
  padding: 14px 18px;
  margin-bottom: 20px;
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.summary {
  margin-left: auto;
  color: var(--rs-text-3);
  font-size: 12.5px;
}

.list {
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-height: 120px;
}

.batch {
  overflow: hidden;
}

.batch-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 22px;
  border-bottom: 1px solid var(--rs-line);
}

.batch-id {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.batch-id .mono {
  color: var(--rs-text-2);
  font-size: 12.5px;
  letter-spacing: 0.03em;
}

.note {
  color: var(--rs-text-3);
  font-size: 12px;
}

.batch-actions {
  display: flex;
  align-items: center;
  gap: 14px;
}

.time {
  font-size: 12px;
}

.batch-meta {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
  padding: 16px 22px;
  background: var(--rs-surface-2);
}

.batch-meta div {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.batch-meta span {
  color: var(--rs-text-3);
  font-size: 11.5px;
}

.batch-meta b {
  font-size: 13.5px;
  font-weight: 600;
}

.batch-meta b.danger {
  color: var(--rs-danger);
}

.batch :deep(.el-table) {
  --el-table-border-color: transparent;
}

.batch :deep(.clickable) {
  cursor: pointer;
}

.tiny {
  margin-left: 6px;
  padding: 0 6px;
  height: 18px;
  font-size: 11px;
}

.empty {
  margin: 8px 0;
  color: var(--rs-text-3);
  font-size: 12.5px;
}

.empty-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 56px;
  color: var(--rs-text-2);
}

.empty-icon {
  font-size: 30px;
  color: var(--rs-text-3);
}

.pager {
  display: flex;
  justify-content: center;
  margin-top: 26px;
}

@media (max-width: 1080px) {
  .batch-meta {
    grid-template-columns: repeat(3, 1fr);
  }
}
</style>
