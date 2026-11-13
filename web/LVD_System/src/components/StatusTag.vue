<template>
  <span class="status" :class="tone">{{ text }}</span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  failed: { type: [Number, Boolean], default: 0 },
  failureType: { type: String, default: null },
  text: { type: String, default: '' },
})

const tone = computed(() => {
  if (props.failed) return props.failureType === 'timeout' ? 'warn' : 'danger'
  return 'ok'
})

const label = computed(() => {
  if (props.text) return props.text
  if (!props.failed) return '未复现失败'
  return '失败已复现'
})
</script>

<style scoped>
.status {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: 5px;
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
}

.ok {
  background: #eaf6f0;
  color: #2f9e73;
}

.warn {
  background: #fdf3e8;
  color: #c96f28;
}

.danger {
  background: #fdeeee;
  color: #c0453f;
}
</style>
