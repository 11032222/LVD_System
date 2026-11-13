<template>
  <div class="home">
    <header class="navbar">
      <div class="nav-inner">
        <router-link to="/" class="brand">
          <span class="brand-mark">
            <svg viewBox="0 0 32 32" width="24" height="24" aria-hidden="true">
              <path d="M16 3 28 10v12L16 29 4 22V10Z" fill="none" stroke="#fff" stroke-width="1.6" opacity=".55" />
              <circle cx="16" cy="16" r="4.2" fill="#fff" />
              <circle cx="16" cy="6.4" r="2" fill="#8fb8ea" />
              <circle cx="24.4" cy="21" r="2" fill="#8fb8ea" />
              <circle cx="7.6" cy="21" r="2" fill="#8fb8ea" />
              <path d="M16 12V8.4M19.6 18.2l3 1.6M12.4 18.2l-3 1.6" stroke="#8fb8ea" stroke-width="1.4" />
            </svg>
          </span>
          <span class="brand-text">
            <strong>无人机集群算法逻辑漏洞发现系统</strong>
            <small>RSFuzz · Robustness-Guided Swarm Fuzzing</small>
          </span>
        </router-link>
        <nav class="nav-links">
          <a href="#algorithms">算法</a>
          <a href="#pipeline">流程</a>
          <router-link to="/console/history">测试历史</router-link>
          <el-button type="primary" @click="router.push('/console/test')">进入控制台</el-button>
        </nav>
      </div>
    </header>

    <section class="hero">
      <div class="hero-inner">
        <div class="hero-copy">
          <span class="eyebrow">行为约束驱动的集群鲁棒性测试</span>
          <h1>发现集群算法里<br />那些“跑不到”的逻辑漏洞</h1>
          <p class="lede">
            以鲁棒度引导的模糊测试为核心：在 2D / 3D 场景中注入单点与多点攻击者，
            用超时、越界、轨迹偏离三类判据自动捕获失败，并把每一次失败完整复现为
            轨迹、场景与时间轴。
          </p>
          <div class="hero-actions">
            <el-button type="primary" size="large" @click="router.push('/console/test')">
              开始一轮测试
              <el-icon class="el-icon--right"><Right /></el-icon>
            </el-button>
            <el-button size="large" @click="router.push('/console/history')">查看测试历史</el-button>
          </div>
          <div class="hero-meta">
            <span><b>3</b> 套集群算法</span>
            <i />
            <span><b>①②③</b> 三类失败判据</span>
            <i />
            <span><b>逐帧</b> 轨迹回放</span>
          </div>
        </div>

        <div class="hero-art">
          <svg viewBox="0 0 560 400" role="img" aria-label="集群攻击示意">
            <defs>
              <pattern id="hero-grid" width="28" height="28" patternUnits="userSpaceOnUse">
                <path d="M28 0H0V28" fill="none" stroke="#e7edf6" stroke-width="1" />
              </pattern>
              <linearGradient id="hero-fade" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stop-color="#eaf1fb" />
                <stop offset="100%" stop-color="#ffffff" stop-opacity="0" />
              </linearGradient>
            </defs>
            <rect width="560" height="400" rx="18" fill="url(#hero-grid)" />
            <rect width="560" height="400" rx="18" fill="url(#hero-fade)" />

            <polygon
              points="120,90 210,70 235,140 165,175 108,150"
              fill="#1f4e8c"
              fill-opacity="0.12"
              stroke="#1f4e8c"
              stroke-opacity="0.5"
            />
            <polygon
              points="360,230 440,215 470,285 395,320 345,290"
              fill="#1f4e8c"
              fill-opacity="0.09"
              stroke="#1f4e8c"
              stroke-opacity="0.35"
            />

            <g class="net" stroke="#2f6fbf" stroke-opacity="0.35" stroke-width="1.2">
              <path d="M300 130 L352 172 L330 236 L268 246 L232 186 Z" fill="none" />
              <path d="M300 130 L330 236 M352 172 L268 246 M232 186 L330 236" fill="none" />
            </g>

            <g class="drones">
              <circle cx="300" cy="130" r="7" fill="#fff" stroke="#2f6fbf" stroke-width="2" />
              <circle cx="352" cy="172" r="7" fill="#fff" stroke="#2f6fbf" stroke-width="2" />
              <circle cx="330" cy="236" r="7" fill="#fff" stroke="#2f6fbf" stroke-width="2" />
              <circle cx="268" cy="246" r="7" fill="#fff" stroke="#2f6fbf" stroke-width="2" />
              <circle cx="232" cy="186" r="7" fill="#fff" stroke="#2f6fbf" stroke-width="2" />
            </g>

            <circle cx="470" cy="120" r="9" fill="#2f9e73" fill-opacity="0.18" stroke="#2f9e73" stroke-width="1.5" />
            <circle cx="470" cy="120" r="3" fill="#2f9e73" />
            <text x="484" y="124" fill="#2f9e73" font-size="11">目标</text>

            <path
              class="attack-path"
              d="M88 300 C 150 268, 196 250, 268 246"
              fill="none"
              stroke="#d9534f"
              stroke-width="2"
              stroke-dasharray="7 6"
            />
            <path
              class="attack-path-2"
              d="M268 246 C 300 268, 318 262, 340 284"
              fill="none"
              stroke="#d9534f"
              stroke-width="1.6"
              stroke-dasharray="5 7"
              stroke-opacity="0.5"
            />
            <g>
              <circle cx="88" cy="300" r="12" fill="#d9534f" fill-opacity="0.14" />
              <circle cx="88" cy="300" r="5" fill="#d9534f" />
              <text x="106" y="305" fill="#c0453f" font-size="11">攻击者</text>
            </g>

            <g class="marker-fail">
              <circle cx="268" cy="246" r="16" fill="none" stroke="#d9534f" stroke-width="1.4" stroke-opacity="0.45" />
              <circle cx="268" cy="246" r="24" fill="none" stroke="#d9534f" stroke-width="1" stroke-opacity="0.22" />
            </g>

            <g fill="#8d99ac" font-size="10.5" font-family="monospace">
              <text x="28" y="376">criterion ②  min_drone_dist &lt; 0.07 m</text>
              <text x="380" y="46">criterion ①  2 × CTime</text>
            </g>
          </svg>
        </div>
      </div>
    </section>

    <section class="stats">
      <div v-for="s in statCards" :key="s.label" class="stat-card">
        <p class="stat-label">{{ s.label }}</p>
        <p class="stat-value">
          {{ s.value }}<span v-if="s.unit">{{ s.unit }}</span>
        </p>
        <p class="stat-foot">{{ s.foot }}</p>
      </div>
    </section>

    <section id="algorithms" class="block">
      <div class="block-head">
        <div>
          <h2>三套集群算法，同一套判定口径</h2>
          <p class="block-sub">覆盖二维与三维场景，规模档位取自论文表格，也可自定义。</p>
        </div>
        <router-link to="/console/history" class="link-more">全部历史记录 →</router-link>
      </div>
      <div class="algo-grid">
        <article v-for="a in algoCards" :key="a.name" class="algo-card">
          <header>
            <AlgoTag :algo="a.name" />
            <span class="dim-chip">{{ a.dim }}D</span>
          </header>
          <h3>{{ a.label }}</h3>
          <p class="algo-desc">{{ a.summary }}</p>
          <div class="algo-metrics">
            <div>
              <span>任务</span>
              <b>{{ a.runs }}</b>
            </div>
            <div>
              <span>失败率</span>
              <b :class="{ danger: a.failure_rate >= 0.5 }">{{ pct(a.failure_rate) }}</b>
            </div>
            <div>
              <span>规模档位</span>
              <b>{{ a.paper_sizes.join(' / ') }} 机</b>
            </div>
          </div>
          <router-link class="algo-link" :to="{ path: '/console/history', query: { algo: a.name } }">
            查看该算法的测试记录
            <el-icon><Right /></el-icon>
          </router-link>
        </article>
      </div>
    </section>

    <section id="pipeline" class="block">
      <div class="block-head">
        <div>
          <h2>从场景到复现的闭环</h2>
          <p class="block-sub">每一步都可回到数据库中的原始帧，结论可复查。</p>
        </div>
      </div>
      <ol class="pipeline">
        <li v-for="(step, i) in pipeline" :key="step.title">
          <span class="step-no">{{ String(i + 1).padStart(2, '0') }}</span>
          <h3>{{ step.title }}</h3>
          <p>{{ step.desc }}</p>
        </li>
      </ol>
    </section>

    <section class="block">
      <div class="block-head">
        <div>
          <h2>最近的测试任务</h2>
          <p class="block-sub">点击任意任务进入测试分析，查看该次运行的轨迹与判据命中过程。</p>
        </div>
        <router-link to="/console/history" class="link-more">按批次浏览 →</router-link>
      </div>
      <div class="card recent">
        <el-table :data="overview.recent_runs" style="width: 100%" @row-click="openRun" row-class-name="clickable">
          <el-table-column label="任务" width="86">
            <template #default="{ row }">
              <span class="mono">#{{ row.id }}</span>
            </template>
          </el-table-column>
          <el-table-column label="算法" width="150">
            <template #default="{ row }"><AlgoTag :algo="row.algo" /></template>
          </el-table-column>
          <el-table-column label="模式" width="90">
            <template #default="{ row }">{{ row.mode_label }}</template>
          </el-table-column>
          <el-table-column label="规模" width="80">
            <template #default="{ row }">{{ row.swarm_size }} 机</template>
          </el-table-column>
          <el-table-column label="种子" width="80">
            <template #default="{ row }"><span class="mono">{{ row.seed }}</span></template>
          </el-table-column>
          <el-table-column label="结果" width="130">
            <template #default="{ row }">
              <StatusTag :failed="row.failed" :failure-type="row.failure_type" :text="row.failed ? row.failure_label : ''" />
            </template>
          </el-table-column>
          <el-table-column label="迭代" width="80">
            <template #default="{ row }">{{ row.iterations ?? '—' }}</template>
          </el-table-column>
          <el-table-column label="完成时间" min-width="150">
            <template #default="{ row }"><span class="muted">{{ row.created_at }}</span></template>
          </el-table-column>
          <el-table-column width="110" align="right">
            <template #default="{ row }">
              <el-button text type="primary" size="small">测试详情</el-button>
            </template>
          </el-table-column>
          <template #empty>暂无测试任务，先去控制台提交一轮。</template>
        </el-table>
      </div>
    </section>

    <footer class="footer">
      <span>RSFuzz · 无人机集群算法逻辑漏洞发现系统</span>
      <span class="muted">数据源：MySQL rsfuzz · 采集产物：repro/runs</span>
    </footer>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Right } from '@element-plus/icons-vue'
import { api } from '@/api'
import AlgoTag from '@/components/AlgoTag.vue'
import StatusTag from '@/components/StatusTag.vue'

const router = useRouter()
const overview = reactive({ counts: {}, algos: [], failure_types: [], activity: [], recent_runs: [] })
const meta = ref(null)
const loading = ref(false)

const ALGO_DESC = {
  'Adaptive Swarm': '二维自适应集群，攻击者按鲁棒度梯度逐步逼近，复现机间碰撞与超时。',
  Pietro: '二维多边形障碍地图，countMatrix 箱式碰撞判定，适合密集障碍场景。',
  Howard: '三维球形障碍与三轴边界，支持攻击链、多攻击者协同与航点模式。',
}
const ALGO_LABEL = {
  'Adaptive Swarm': '自适应集群（Adaptive Swarm）',
  Pietro: 'Pietro 集群',
  Howard: 'Howard 集群',
}

const statCards = computed(() => [
  {
    label: '测试批次',
    value: overview.counts.batches ?? 0,
    foot: `${overview.counts.running_batches ?? 0} 个批次进行中`,
  },
  {
    label: '测试任务',
    value: overview.counts.runs ?? 0,
    foot: `${overview.counts.scenarios ?? 0} 个场景参与`,
  },
  {
    label: '失败复现率',
    value: pct(overview.counts.failure_rate),
    foot: `${overview.counts.failed ?? 0} 个任务命中判据`,
  },
  {
    label: '回放帧 / 鲁棒度点',
    value: overview.counts.frames ?? 0,
    foot: `${overview.counts.iterations ?? 0} 条迭代鲁棒度`,
  },
])

const algoCards = computed(() =>
  (meta.value?.algorithms || []).map((a) => {
    const stat = (overview.algos || []).find((x) => x.algo === a.name) || {}
    return {
      name: a.name,
      label: ALGO_LABEL[a.name] || a.name,
      dim: a.dim,
      summary: ALGO_DESC[a.name] || a.summary,
      paper_sizes: a.paper_sizes,
      runs: stat.runs ?? 0,
      failure_rate: stat.failure_rate ?? 0,
    }
  }),
)

const pipeline = [
  { title: '场景构建', desc: '内置论文地图，或按边界 / 多边形 / 球体生成自定义场景，几何哈希去重。' },
  { title: '种子调度', desc: '连续区间或随机抽取固定种子，NA / SA / MA 共用同一批种子做配对比较。' },
  { title: '判据捕获', desc: '超时、越界（撞障碍 / 机间碰撞）、轨迹偏离三类判据逐帧监控并落库。' },
  { title: '轨迹复现', desc: '三维回放叠加时间轴，起飞点、碰撞点、失败点与鲁棒度曲线同步定位。' },
]

function pct(v) {
  const n = Number(v || 0)
  return `${(n * 100).toFixed(0)}%`
}

function openRun(row) {
  router.push(`/console/run/${row.id}`)
}

async function load() {
  loading.value = true
  try {
    const [ov, m] = await Promise.all([api.overview(), api.meta()])
    Object.assign(overview, ov)
    meta.value = m
  } catch (e) {
    ElMessage.error(e.message || '加载概览失败')
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.home {
  min-height: 100vh;
  background:
    radial-gradient(1200px 600px at 78% -10%, #e9f0fb 0%, rgba(233, 240, 251, 0) 60%),
    var(--rs-bg);
}

.navbar {
  position: sticky;
  top: 0;
  z-index: 20;
  background: rgba(255, 255, 255, 0.86);
  border-bottom: 1px solid var(--rs-line);
  backdrop-filter: blur(12px);
}

.nav-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  max-width: 1240px;
  margin: 0 auto;
  padding: 14px 32px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 11px;
  color: var(--rs-text);
}

.brand-mark {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  border-radius: 11px;
  background: linear-gradient(145deg, #1f4e8c, #16365f);
  box-shadow: 0 6px 14px rgba(31, 78, 140, 0.24);
}

.brand-text {
  display: flex;
  flex-direction: column;
  line-height: 1.35;
}

.brand-text strong {
  font-size: 14.5px;
  letter-spacing: 0.01em;
}

.brand-text small {
  font-size: 11px;
  color: var(--rs-text-3);
  letter-spacing: 0.03em;
}

.nav-links {
  display: flex;
  align-items: center;
  gap: 26px;
  font-size: 13.5px;
}

.nav-links a {
  color: var(--rs-text-2);
}

.nav-links a:hover {
  color: var(--rs-primary);
}

.hero {
  padding: 64px 32px 24px;
}

.hero-inner {
  display: grid;
  grid-template-columns: minmax(360px, 1fr) minmax(420px, 540px);
  align-items: center;
  gap: 56px;
  max-width: 1240px;
  margin: 0 auto;
}

.eyebrow {
  display: inline-block;
  padding: 5px 12px;
  border-radius: 999px;
  background: var(--rs-primary-soft);
  color: var(--rs-primary);
  font-size: 12px;
  letter-spacing: 0.04em;
}

.hero h1 {
  margin: 20px 0 18px;
  font-size: 44px;
  line-height: 1.24;
  letter-spacing: -0.02em;
  color: #10203a;
}

.lede {
  max-width: 560px;
  margin: 0;
  color: var(--rs-text-2);
  font-size: 14.5px;
  line-height: 1.9;
}

.hero-actions {
  display: flex;
  gap: 12px;
  margin-top: 30px;
}

.hero-meta {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-top: 30px;
  color: var(--rs-text-3);
  font-size: 12.5px;
}

.hero-meta b {
  color: var(--rs-primary);
  font-weight: 600;
}

.hero-meta i {
  width: 1px;
  height: 12px;
  background: var(--rs-line-strong);
}

.hero-art svg {
  width: 100%;
  height: auto;
  filter: drop-shadow(0 18px 36px rgba(31, 78, 140, 0.08));
}

.attack-path {
  animation: dash 3.4s linear infinite;
}

.attack-path-2 {
  animation: dash 5s linear infinite reverse;
}

@keyframes dash {
  to {
    stroke-dashoffset: -52;
  }
}

.marker-fail circle {
  animation: pulse 2.6s ease-out infinite;
  transform-origin: 268px 246px;
}

@keyframes pulse {
  0% {
    opacity: 0.9;
    transform: scale(0.7);
  }
  70% {
    opacity: 0;
    transform: scale(1.4);
  }
  100% {
    opacity: 0;
  }
}

.stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 18px;
  max-width: 1240px;
  margin: 34px auto 0;
  padding: 0 32px;
}

.stat-card {
  padding: 20px 22px;
  background: var(--rs-surface);
  border: 1px solid var(--rs-line);
  border-radius: var(--rs-radius);
  box-shadow: var(--rs-shadow);
}

.stat-label {
  margin: 0;
  color: var(--rs-text-3);
  font-size: 12px;
  letter-spacing: 0.03em;
}

.stat-value {
  margin: 8px 0 4px;
  font-size: 30px;
  font-weight: 600;
  letter-spacing: -0.02em;
  color: #10203a;
}

.stat-value span {
  margin-left: 4px;
  font-size: 13px;
  font-weight: 500;
  color: var(--rs-text-3);
}

.stat-foot {
  margin: 0;
  color: var(--rs-text-3);
  font-size: 12px;
}

.block {
  max-width: 1240px;
  margin: 0 auto;
  padding: 56px 32px 0;
}

.block-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 22px;
}

.block-head h2 {
  font-size: 22px;
  letter-spacing: -0.01em;
}

.block-sub {
  margin: 6px 0 0;
  color: var(--rs-text-2);
  font-size: 13px;
}

.link-more {
  font-size: 13px;
  white-space: nowrap;
}

.algo-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}

.algo-card {
  padding: 24px;
  background: var(--rs-surface);
  border: 1px solid var(--rs-line);
  border-radius: var(--rs-radius);
  box-shadow: var(--rs-shadow);
  transition: transform 0.2s, box-shadow 0.2s;
}

.algo-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 14px 32px rgba(22, 32, 46, 0.08);
}

.algo-card header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.dim-chip {
  padding: 2px 8px;
  border: 1px solid var(--rs-line);
  border-radius: 5px;
  color: var(--rs-text-3);
  font-size: 11px;
  letter-spacing: 0.04em;
}

.algo-card h3 {
  font-size: 16px;
  margin-bottom: 8px;
}

.algo-desc {
  min-height: 66px;
  margin: 0 0 16px;
  color: var(--rs-text-2);
  font-size: 13px;
  line-height: 1.75;
}

.algo-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  padding: 14px 0;
  border-top: 1px solid var(--rs-line);
}

.algo-metrics div {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.algo-metrics span {
  color: var(--rs-text-3);
  font-size: 11.5px;
}

.algo-metrics b {
  font-size: 14px;
  font-weight: 600;
}

.algo-metrics b.danger {
  color: var(--rs-danger);
}

.algo-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 6px;
  font-size: 12.5px;
}

.pipeline {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 18px;
  margin: 0;
  padding: 0;
  list-style: none;
  counter-reset: none;
}

.pipeline li {
  position: relative;
  padding: 22px;
  background: var(--rs-surface);
  border: 1px solid var(--rs-line);
  border-radius: var(--rs-radius);
}

.pipeline li::after {
  content: '';
  position: absolute;
  top: 40px;
  right: -18px;
  width: 18px;
  height: 1px;
  background: var(--rs-line-strong);
}

.pipeline li:last-child::after {
  display: none;
}

.step-no {
  display: inline-block;
  margin-bottom: 12px;
  color: var(--rs-primary);
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  letter-spacing: 0.1em;
}

.pipeline h3 {
  font-size: 14.5px;
  margin-bottom: 6px;
}

.pipeline p {
  margin: 0;
  color: var(--rs-text-2);
  font-size: 12.5px;
  line-height: 1.75;
}

.recent {
  overflow: hidden;
}

.recent :deep(.clickable) {
  cursor: pointer;
}

.footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  max-width: 1240px;
  margin: 72px auto 0;
  padding: 26px 32px 40px;
  border-top: 1px solid var(--rs-line);
  color: var(--rs-text-2);
  font-size: 12px;
}

@media (max-width: 1080px) {
  .hero-inner {
    grid-template-columns: 1fr;
  }

  .hero-art {
    display: none;
  }

  .stats,
  .algo-grid,
  .pipeline {
    grid-template-columns: repeat(2, 1fr);
  }

  .pipeline li::after {
    display: none;
  }
}

@media (max-width: 720px) {
  .nav-links a:not(.el-button) {
    display: none;
  }

  .hero h1 {
    font-size: 32px;
  }

  .stats,
  .algo-grid,
  .pipeline {
    grid-template-columns: 1fr;
  }
}
</style>
