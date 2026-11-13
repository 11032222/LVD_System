<template>
  <span class="algo" :style="{ color: theme.color, background: theme.bg }">
    <i class="dot" :style="{ background: theme.color }" />
    {{ name }}
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ algo: { type: String, default: '' } })

const THEME = {
  'Adaptive Swarm': { color: '#1f4e8c', bg: '#eaf1fb' },
  Pietro: { color: '#2f7d6b', bg: '#e8f4f0' },
  Howard: { color: '#7a4fa8', bg: '#f2ecfa' },
}

const name = computed(() => props.algo || '未知算法')
const theme = computed(() => THEME[props.algo] || { color: '#55637a', bg: '#f1f4f9' })
</script>

<style scoped>
.algo {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 24px;
  padding: 0 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}
</style>
