<template>
  <svg class="thumb" viewBox="0 0 400 300" preserveAspectRatio="xMidYMid meet" role="img">
    <defs>
      <pattern id="rs-grid" width="20" height="20" patternUnits="userSpaceOnUse">
        <path d="M20 0H0V20" fill="none" stroke="#eef2f8" stroke-width="1" />
      </pattern>
      <radialGradient id="rs-sphere" cx="35%" cy="30%" r="70%">
        <stop offset="0%" stop-color="#b9cfe8" stop-opacity="0.95" />
        <stop offset="100%" stop-color="#7fa1c8" stop-opacity="0.55" />
      </radialGradient>
    </defs>

    <rect x="0" y="0" width="400" height="300" fill="url(#rs-grid)" />

    <g v-if="view">
      <!-- 边界框 -->
      <line
        v-for="(e, i) in view.boxEdges"
        :key="'e' + i"
        :x1="e[0]"
        :y1="e[1]"
        :x2="e[2]"
        :y2="e[3]"
        stroke="#c9d6e7"
        stroke-width="1.2"
        stroke-dasharray="4 3"
      />

      <!-- 障碍：二维多边形 -->
      <polygon
        v-for="(poly, i) in view.polygons"
        :key="'p' + i"
        :points="poly"
        fill="#1f4e8c"
        fill-opacity="0.16"
        stroke="#1f4e8c"
        stroke-width="1.3"
        stroke-opacity="0.75"
      />

      <!-- 障碍：三维球体 -->
      <circle
        v-for="(s, i) in view.spheres"
        :key="'s' + i"
        :cx="s.cx"
        :cy="s.cy"
        :r="s.r"
        fill="url(#rs-sphere)"
        stroke="#5f86b3"
        stroke-width="1"
        stroke-opacity="0.6"
      />

      <!-- 起点编队 -->
      <circle
        v-for="(p, i) in view.starts"
        :key="'u' + i"
        :cx="p.cx"
        :cy="p.cy"
        r="3"
        fill="#ffffff"
        stroke="#2f6fbf"
        stroke-width="1.6"
      />

      <!-- 目标点 -->
      <g v-for="(t, i) in view.targets" :key="'t' + i">
        <circle :cx="t.cx" :cy="t.cy" r="5.5" fill="none" stroke="#2f9e73" stroke-width="1.6" />
        <circle :cx="t.cx" :cy="t.cy" r="1.8" fill="#2f9e73" />
      </g>

      <!-- 关键点 -->
      <g v-for="(m, i) in view.markers" :key="'m' + i">
        <circle :cx="m.cx" :cy="m.cy" r="7" :fill="m.color" fill-opacity="0.16" />
        <circle :cx="m.cx" :cy="m.cy" r="3.4" :fill="m.color" />
      </g>
    </g>

    <text v-else x="200" y="152" text-anchor="middle" fill="#9aa4b2" font-size="12">
      暂无场景几何
    </text>
  </svg>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  dim: { type: Number, default: 2 },
  bounds: { type: Object, default: () => ({}) },
  obstacles: { type: Array, default: () => [] },
  targets: { type: Array, default: () => [] },
  initPositions: { type: Array, default: () => [] },
  markers: { type: Array, default: () => [] },
})

const W = 400
const H = 300
const PAD = 30

function safeBounds() {
  const b = props.bounds || {}
  const axes = props.dim === 3 ? ['x', 'y', 'z'] : ['x', 'y']
  const ok = axes.every((a) => Array.isArray(b[a]) && b[a].length === 2 && b[a][1] > b[a][0])
  if (ok) return b

  // 兜底：用障碍/目标点撑出外接框
  const pts = []
  for (const ob of props.obstacles || []) {
    if (ob.kind === 'sphere' && ob.c) pts.push(ob.c)
    if (ob.kind === 'polygon') (ob.pts || []).forEach((p) => pts.push(p))
  }
  ;(props.targets || []).forEach((p) => pts.push(p))
  ;(props.initPositions || []).forEach((p) => pts.push(p))
  if (!pts.length) return null
  const out = {}
  axes.forEach((axis, i) => {
    const vals = pts.map((p) => p[i]).filter((v) => typeof v === 'number')
    if (!vals.length) return
    const lo = Math.min(...vals)
    const hi = Math.max(...vals)
    out[axis] = lo === hi ? [lo - 1, hi + 1] : [lo, hi]
  })
  return axes.every((a) => out[a]) ? out : null
}

const view = computed(() => {
  const b = safeBounds()
  if (!b) return null
  const markersIn = (props.markers || []).filter((m) => Array.isArray(m.p))

  let project
  let unit = 1 // 世界 1 单位对应多少像素，供球体半径换算

  if (props.dim === 3) {
    const bx = b.x
    const by = b.y
    const bz = b.z || [0, 1]
    const raw = (p) => [(p[0] - p[1]) * 0.866, (p[0] + p[1]) * 0.5 - p[2]]
    const corners = []
    for (const x of bx) for (const y of by) for (const z of bz) corners.push(raw([x, y, z]))
    const xs = corners.map((c) => c[0])
    const ys = corners.map((c) => c[1])
    const minX = Math.min(...xs)
    const maxX = Math.max(...xs)
    const minY = Math.min(...ys)
    const maxY = Math.max(...ys)
    const s = Math.min((W - PAD * 2) / (maxX - minX || 1), (H - PAD * 2) / (maxY - minY || 1))
    const ox = (W - (maxX - minX) * s) / 2 - minX * s
    const oy = (H - (maxY - minY) * s) / 2 - minY * s
    project = (p) => {
      const r = raw(p)
      return [ox + r[0] * s, oy + r[1] * s]
    }
    unit = s

    const c = []
    for (const x of bx) for (const y of by) for (const z of bz) c.push([x, y, z])
    // 顶点按 (x, y, z) 三重循环生成：0-3 为 x0 面，4-7 为 x1 面
    const edges = [
      [0, 4], [1, 5], [2, 6], [3, 7],
      [0, 2], [1, 3], [4, 6], [5, 7],
      [0, 1], [2, 3], [4, 5], [6, 7],
    ]
    const boxEdges = edges.map(([a, bb]) => {
      const p1 = project(c[a])
      const p2 = project(c[bb])
      return [p1[0], p1[1], p2[0], p2[1]]
    })
    const spheres = (props.obstacles || [])
      .filter((o) => o.kind === 'sphere')
      .map((o) => {
        const p = project(o.c)
        return { cx: p[0], cy: p[1], r: Math.max(4, (o.r || 1) * unit) }
      })
    return {
      boxEdges,
      polygons: [],
      spheres,
      starts: (props.initPositions || []).map((p) => {
        const q = project(p)
        return { cx: q[0], cy: q[1] }
      }),
      targets: (props.targets || []).map((p) => {
        const q = project(p)
        return { cx: q[0], cy: q[1] }
      }),
      markers: markersIn.map((m) => {
        const q = project(m.p)
        return { cx: q[0], cy: q[1], color: m.color || '#d9534f' }
      }),
    }
  }

  const dx = b.x[1] - b.x[0]
  const dy = b.y[1] - b.y[0]
  const s = Math.min((W - PAD * 2) / (dx || 1), (H - PAD * 2) / (dy || 1))
  const ox = (W - dx * s) / 2 - b.x[0] * s
  const oy = (H - dy * s) / 2 - b.y[0] * s
  project = (p) => [ox + p[0] * s, H - (oy + p[1] * s)]
  unit = s

  const polys = (props.obstacles || [])
    .filter((o) => o.kind === 'polygon')
    .map((o) => (o.pts || []).map((p) => project(p).join(',')).join(' '))

  const boxEdges = []
  const corners = [
    [b.x[0], b.y[0]],
    [b.x[1], b.y[0]],
    [b.x[1], b.y[1]],
    [b.x[0], b.y[1]],
  ].map(project)
  for (let i = 0; i < 4; i++) {
    const p1 = corners[i]
    const p2 = corners[(i + 1) % 4]
    boxEdges.push([p1[0], p1[1], p2[0], p2[1]])
  }

  return {
    boxEdges,
    polygons: polys,
    spheres: [],
    starts: (props.initPositions || []).map((p) => {
      const q = project(p)
      return { cx: q[0], cy: q[1] }
    }),
    targets: (props.targets || []).map((p) => {
      const q = project(p)
      return { cx: q[0], cy: q[1] }
    }),
    markers: markersIn.map((m) => {
      const q = project(m.p)
      return { cx: q[0], cy: q[1], color: m.color || '#d9534f' }
    }),
  }
})
</script>

<style scoped>
.thumb {
  display: block;
  width: 100%;
  height: 100%;
  background: #fff;
  border-radius: 10px;
}
</style>
