<template>
  <div class="shell">
    <aside class="side">
      <router-link to="/" class="brand">
        <span class="brand-mark">
          <svg viewBox="0 0 32 32" width="26" height="26" aria-hidden="true">
            <path d="M16 3 28 10v12L16 29 4 22V10Z" fill="none" stroke="#fff" stroke-width="1.6" opacity=".55" />
            <circle cx="16" cy="16" r="4.2" fill="#fff" />
            <circle cx="16" cy="6.4" r="2" fill="#8fb8ea" />
            <circle cx="24.4" cy="21" r="2" fill="#8fb8ea" />
            <circle cx="7.6" cy="21" r="2" fill="#8fb8ea" />
            <path d="M16 12V8.4M19.6 18.2l3 1.6M12.4 18.2l-3 1.6" stroke="#8fb8ea" stroke-width="1.4" />
          </svg>
        </span>
        <span class="brand-text">
          <strong>无人机集群</strong>
          <small>逻辑漏洞发现系统</small>
        </span>
      </router-link>

      <nav class="nav">
        <p class="nav-label">测试</p>
        <router-link
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="nav-item"
          :class="{ active: isActive(item) }"
        >
          <el-icon class="nav-icon"><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </router-link>

        <p class="nav-label">分析视图</p>
        <router-link v-if="currentRun" :to="`/console/run/${currentRun}`" class="nav-item active">
          <el-icon class="nav-icon"><DataLine /></el-icon>
          <span>测试分析 #{{ currentRun }}</span>
        </router-link>
        <router-link v-if="currentBatch" :to="`/console/batch/${currentBatch}`" class="nav-item" :class="{ active: isBatchActive }">
          <el-icon class="nav-icon"><Histogram /></el-icon>
          <span>批次分析 #{{ currentBatch }}</span>
        </router-link>
        <p v-if="!currentRun && !currentBatch" class="nav-empty">从测试历史进入详情后，这里会保留当前分析上下文。</p>
      </nav>

      <div class="side-foot">
        <div class="foot-line">
          <span class="dot" :class="online ? 'on' : 'off'" />
          <span>{{ online ? 'API 已连接' : 'API 未连接' }}</span>
        </div>
        <p class="mono">RSFuzz · schema 1.0.0</p>
      </div>
    </aside>

    <div class="main">
      <header class="topbar">
        <div>
          <h1 class="top-title">{{ title }}</h1>
          <p class="top-sub">{{ subtitle }}</p>
        </div>
        <div class="top-actions">
          <el-button text :icon="Refresh" @click="refresh" :loading="loading">刷新</el-button>
          <el-button :icon="House" @click="router.push('/')">返回首页</el-button>
        </div>
      </header>
      <main class="content">
        <router-view v-slot="{ Component }">
          <component :is="Component" :ref="setViewRef" />
        </router-view>
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { DataLine, Histogram, House, Refresh } from '@element-plus/icons-vue'
import { api } from '@/api'

const route = useRoute()
const router = useRouter()

const navItems = [
  { to: '/console/test', label: '测试控制台', icon: 'Monitor' },
  { to: '/console/history', label: '测试历史', icon: 'Clock' },
]

const online = ref(false)
const loading = ref(false)
const viewRef = ref(null)

const title = computed(() => route.meta?.title || '控制台')
const subtitle = computed(() => route.meta?.subtitle || '')

const currentRun = computed(() => (route.name === 'run-analysis' ? route.params.id : null))
const currentBatch = computed(() => (route.name === 'batch-analysis' ? route.params.id : null))
const isBatchActive = computed(() => route.name === 'batch-analysis')

function isActive(item) {
  return route.path.startsWith(item.to)
}

function setViewRef(el) {
  viewRef.value = el
}

async function refresh() {
  const inst = viewRef.value
  if (inst && typeof inst.load === 'function') {
    loading.value = true
    try {
      await inst.load()
    } finally {
      loading.value = false
    }
  } else {
    router.go(0)
  }
}

async function ping() {
  try {
    await api.overview()
    online.value = true
  } catch {
    online.value = false
  }
}

onMounted(ping)
watch(() => route.fullPath, ping)
</script>

<style scoped>
.shell {
  display: flex;
  min-height: 100vh;
  background: var(--rs-bg);
}

.side {
  position: sticky;
  top: 0;
  display: flex;
  flex-direction: column;
  width: 236px;
  flex: 0 0 236px;
  height: 100vh;
  padding: 22px 16px 18px;
  background: linear-gradient(180deg, #16365f 0%, #12294a 100%);
  color: #dce6f4;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 8px 22px;
  color: #fff;
}

.brand-mark {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  border-radius: 11px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.16);
}

.brand-text {
  display: flex;
  flex-direction: column;
  line-height: 1.35;
}

.brand-text strong {
  font-size: 14px;
  letter-spacing: 0.02em;
}

.brand-text small {
  font-size: 11px;
  color: #93a9c6;
  letter-spacing: 0.04em;
}

.nav {
  flex: 1;
}

.nav-label {
  margin: 18px 8px 8px;
  font-size: 11px;
  letter-spacing: 0.14em;
  color: #7d93b2;
  text-transform: uppercase;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 42px;
  padding: 0 12px;
  margin-bottom: 4px;
  border-radius: 10px;
  color: #c6d4e6;
  font-size: 13.5px;
  transition: background 0.18s, color 0.18s;
}

.nav-item:hover {
  background: rgba(255, 255, 255, 0.07);
  color: #fff;
}

.nav-item.active {
  background: rgba(255, 255, 255, 0.13);
  color: #fff;
  box-shadow: inset 2px 0 0 #6fa8e8;
}

.nav-icon {
  font-size: 16px;
  opacity: 0.9;
}

.nav-empty {
  margin: 6px 10px;
  font-size: 11.5px;
  line-height: 1.7;
  color: #7389a7;
}

.side-foot {
  padding: 14px 10px 0;
  border-top: 1px solid rgba(255, 255, 255, 0.09);
  font-size: 11.5px;
  color: #8fa6c4;
}

.foot-line {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 6px;
  color: #c3d3e6;
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}

.dot.on {
  background: #4cc38a;
  box-shadow: 0 0 0 3px rgba(76, 195, 138, 0.16);
}

.dot.off {
  background: #d9534f;
  box-shadow: 0 0 0 3px rgba(217, 83, 79, 0.16);
}

.side-foot .mono {
  margin: 0;
  font-size: 10.5px;
  color: #7288a6;
}

.main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.topbar {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 18px 40px;
  background: rgba(255, 255, 255, 0.82);
  border-bottom: 1px solid var(--rs-line);
  backdrop-filter: blur(10px);
}

.top-title {
  font-size: 19px;
  line-height: 1.35;
}

.top-sub {
  margin: 3px 0 0;
  color: var(--rs-text-3);
  font-size: 12.5px;
}

.top-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.content {
  flex: 1;
  min-height: 0;
}

@media (max-width: 1080px) {
  .side {
    width: 200px;
    flex-basis: 200px;
  }

  .topbar {
    padding: 16px 22px;
  }
}
</style>
