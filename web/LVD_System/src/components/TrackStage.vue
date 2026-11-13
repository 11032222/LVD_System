<template>
  <div ref="host" class="stage">
    <div class="legend">
      <span><i class="uav" />无人机</span>
      <span><i class="attacker" />攻击者</span>
      <span><i class="target" />目标</span>
      <span><i class="failure" />失败点</span>
    </div>
    <div v-if="!hasFrames" class="stage-empty">该任务没有采集到逐帧轨迹，无法回放</div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'

const props = defineProps({
  scene: { type: Object, default: null },
  frames: { type: Array, default: () => [] },
  progress: { type: Number, default: 0 },
  viewMode: { type: String, default: '3d' },
  showObstacles: { type: Boolean, default: true },
  showTrail: { type: Boolean, default: true },
  markers: { type: Array, default: () => [] },
})

const host = ref(null)
const hasFrames = computed(() => props.frames.length > 0)

let renderer = null
let scene = null
let camera = null
let controls = null
let world = null
let staticGroup = null
let obstacleGroup = null
let trailGroup = null
let agentGroup = null
let markerGroup = null
let raf = null
let observer = null
let geometryInfo = null
const agents = new Map()     // key -> mesh
const trails = new Map()     // key -> {full, traveled}
let initialPositions = []

function keyOf(a) {
  return `${a.k}:${a.id}`
}

function centerAndScale() {
  const b = props.scene?.bounds || {}
  const dim = props.scene?.dim || 3
  const axes = dim === 3 ? ['x', 'y', 'z'] : ['x', 'y']
  const lo = axes.map((ax) => (Array.isArray(b[ax]) ? b[ax][0] : 0))
  const hi = axes.map((ax) => (Array.isArray(b[ax]) ? b[ax][1] : 1))
  const center = lo.map((v, i) => (v + hi[i]) / 2)
  const size = hi.map((v, i) => Math.max(1, v - lo[i]))
  const diag = Math.hypot(...size)
  return { axes, lo, hi, center, size, diag, dim }
}

function toVec(p) {
  const c = geometryInfo.center
  const v = [0, 0, 0]
  for (let i = 0; i < 3; i++) v[i] = (p[i] ?? c[i] ?? 0) - (c[i] ?? 0)
  return new THREE.Vector3(v[0], v[1], v[2])
}

function disposeGroup(g) {
  if (!g) return
  g.traverse((o) => {
    if (o.geometry) o.geometry.dispose()
    if (o.material) {
      if (Array.isArray(o.material)) o.material.forEach((m) => m.dispose())
      else o.material.dispose()
    }
  })
  g.clear()
}

function buildObstacles() {
  const sc = props.scene
  if (!sc) return
  const dim = sc.dim || 2
  const geo = geometryInfo
  for (const ob of sc.obstacles || []) {
    if (ob.kind === 'polygon' && Array.isArray(ob.pts)) {
      const shape = new THREE.Shape()
      ob.pts.forEach((p, i) => {
        const v = toVec([p[0], p[1], geo.lo[2] || 0])
        if (i === 0) shape.moveTo(v.x, v.y)
        else shape.lineTo(v.x, v.y)
      })
      const mesh = new THREE.Mesh(
        new THREE.ShapeGeometry(shape),
        new THREE.MeshBasicMaterial({
          color: 0x1f4e8c,
          transparent: true,
          opacity: 0.16,
          side: THREE.DoubleSide,
          depthWrite: false,
        }),
      )
      mesh.position.z = 0.02
      obstacleGroup.add(mesh)

      const lineGeo = new THREE.BufferGeometry().setFromPoints(
        ob.pts.map((p) => toVec([p[0], p[1], geo.lo[2] || 0])).concat([toVec([ob.pts[0][0], ob.pts[0][1], geo.lo[2] || 0])]),
      )
      obstacleGroup.add(new THREE.Line(lineGeo, new THREE.LineBasicMaterial({ color: 0x1f4e8c, transparent: true, opacity: 0.55 })))
    }
    if (ob.kind === 'sphere') {
      const mesh = new THREE.Mesh(
        new THREE.SphereGeometry(ob.r || 1, 24, 18),
        new THREE.MeshStandardMaterial({
          color: 0x8fb0d4,
          transparent: true,
          opacity: 0.32,
          roughness: 0.8,
          metalness: 0,
          depthWrite: false,
        }),
      )
      mesh.position.copy(toVec(ob.c))
      obstacleGroup.add(mesh)
      const wire = new THREE.Mesh(
        new THREE.SphereGeometry((ob.r || 1) * 1.001, 16, 10),
        new THREE.MeshBasicMaterial({ color: 0x5f86b3, wireframe: true, transparent: true, opacity: 0.18 }),
      )
      wire.position.copy(mesh.position)
      obstacleGroup.add(wire)
    }
  }
  obstacleGroup.visible = props.showObstacles

  // 目标点
  for (const t of sc.targets || []) {
    const v = toVec(t)
    const cone = new THREE.Mesh(
      new THREE.ConeGeometry(geo.diag * 0.012, geo.diag * 0.03, 16),
      new THREE.MeshStandardMaterial({ color: 0x2f9e73, transparent: true, opacity: 0.85 }),
    )
    cone.position.set(v.x, v.y, (geo.dim === 2 ? 0 : v.z) + geo.diag * 0.02)
    cone.rotation.x = Math.PI / 2
    obstacleGroup.add(cone)
  }
}

function buildBounds() {
  const { size, dim } = geometryInfo
  const box = new THREE.BoxGeometry(size[0], size[1], dim === 3 ? size[2] : 0.001)
  const edges = new THREE.LineSegments(
    new THREE.EdgesGeometry(box),
    new THREE.LineBasicMaterial({ color: 0xc9d6e7, transparent: true, opacity: 0.9 }),
  )
  staticGroup.add(edges)

  const gridSize = Math.max(size[0], size[1])
  const grid = new THREE.GridHelper(gridSize, 20, 0xdfe7f2, 0xeef3f9)
  grid.rotation.x = Math.PI / 2
  grid.position.z = -(size[2] || 0) / 2 - 0.001
  staticGroup.add(grid)
}

function buildTrails() {
  const list = new Map()
  for (const f of props.frames) {
    for (const a of f.agents || []) {
      if (a.k !== 'uav' && a.k !== 'attacker') continue
      const k = keyOf(a)
      if (!list.has(k)) list.set(k, { kind: a.k, pts: [] })
      list.get(k).pts.push(toVec(a.p))
    }
  }
  for (const [k, item] of list) {
    const positions = item.pts
    if (positions.length < 2) continue
    const color = item.kind === 'attacker' ? 0xd9534f : 0x2f6fbf
    const full = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(positions),
      new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.16 }),
    )
    const traveled = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(positions),
      new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.85 }),
    )
    trailGroup.add(full)
    trailGroup.add(traveled)
    trails.set(k, { full, traveled, count: positions.length })
  }
  trailGroup.visible = props.showTrail
}

function ensureAgent(kind, id) {
  const k = `${kind}:${id}`
  if (agents.has(k)) return agents.get(k)
  const geo = geometryInfo
  const radius = kind === 'attacker' ? geo.diag * 0.012 : geo.diag * 0.007
  const mesh = new THREE.Mesh(
    kind === 'attacker'
      ? new THREE.OctahedronGeometry(radius * 1.5)
      : new THREE.SphereGeometry(radius, 18, 14),
    new THREE.MeshStandardMaterial({
      color: kind === 'attacker' ? 0xd9534f : 0x2f6fbf,
      roughness: 0.35,
      metalness: 0.1,
      emissive: kind === 'attacker' ? 0x5a1512 : 0x0b2347,
      emissiveIntensity: 0.35,
    }),
  )
  agentGroup.add(mesh)
  agents.set(k, mesh)
  return mesh
}

function buildMarkers() {
  const geo = geometryInfo
  let idx = 0
  for (const m of props.markers) {
    if (!m.position) continue
    const v = toVec(m.position)
    const color = new THREE.Color(m.color || '#d9534f')
    const ring = new THREE.Mesh(
      new THREE.RingGeometry(geo.diag * 0.016, geo.diag * 0.026, 32),
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.85, side: THREE.DoubleSide }),
    )
    ring.position.set(v.x, v.y, v.z)
    ring.rotation.x = 0
    markerGroup.add(ring)
    const dot = new THREE.Mesh(
      new THREE.SphereGeometry(geo.diag * 0.009, 12, 10),
      new THREE.MeshBasicMaterial({ color }),
    )
    dot.position.copy(v)
    markerGroup.add(dot)
    idx += 1
  }
  // 起飞点：首帧编队位置
  for (const p of initialPositions) {
    const v = toVec(p)
    const ring = new THREE.Mesh(
      new THREE.RingGeometry(geo.diag * 0.008, geo.diag * 0.012, 18),
      new THREE.MeshBasicMaterial({ color: 0x4cc38a, transparent: true, opacity: 0.7, side: THREE.DoubleSide }),
    )
    ring.position.set(v.x, v.y, v.z)
    markerGroup.add(ring)
  }
  return idx
}

function buildScene() {
  if (!scene || !props.scene) return
  geometryInfo = centerAndScale()
  for (const g of [staticGroup, obstacleGroup, trailGroup, agentGroup, markerGroup]) disposeGroup(g)
  agents.clear()
  trails.clear()

  buildBounds()
  buildObstacles()

  if (props.frames.length) {
    const first = props.frames[0].agents || []
    initialPositions = first.filter((a) => a.k === 'uav').map((a) => a.p)
    const seen = new Set()
    for (const f of props.frames) {
      for (const a of f.agents || []) {
        const k = keyOf(a)
        if (seen.has(k)) continue
        seen.add(k)
        ensureAgent(a.k, a.id)
      }
    }
    buildTrails()
  }
  buildMarkers()
  updateCamera()
  applyProgress()
}

function applyProgress() {
  if (!props.frames.length) return
  const total = props.frames.length - 1
  const p = Math.max(0, Math.min(total, props.progress))
  const i0 = Math.floor(p)
  const i1 = Math.min(total, i0 + 1)
  const t = p - i0
  const f0 = props.frames[i0]
  const f1 = props.frames[i1]

  const prev = new Map()
  for (const a of f0.agents || []) prev.set(keyOf(a), a.p)
  for (const a of f1.agents || []) {
    const k = keyOf(a)
    const mesh = agents.get(k)
    if (!mesh) continue
    const p0 = prev.get(k) || a.p
    const p1 = a.p
    const mix = [0, 1, 2].map((i) => (p0[i] ?? 0) + ((p1[i] ?? 0) - (p0[i] ?? 0)) * t)
    mesh.position.copy(toVec(mix))
  }

  const steps = i0 + 1
  for (const [, item] of trails) {
    item.traveled.geometry.setDrawRange(0, Math.max(2, steps))
  }
}

function updateCamera() {
  if (!renderer || !geometryInfo) return
  const { size, diag, dim } = geometryInfo
  const aspect = renderer.domElement.clientWidth / Math.max(1, renderer.domElement.clientHeight)
  const dist = diag * 2.1

  if (props.viewMode === 'top') {
    const cam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.001, dist * 4)
    const span = Math.max(size[0], size[1]) * 0.62
    cam.left = -span * aspect
    cam.right = span * aspect
    cam.top = span
    cam.bottom = -span
    cam.position.set(0, 0, dist)
    cam.up.set(0, 1, 0)
    cam.lookAt(0, 0, 0)
    cam.updateProjectionMatrix()
    camera = cam
  } else {
    const cam = new THREE.PerspectiveCamera(42, aspect, diag * 0.01, diag * 40)
    cam.position.set(dist * 0.55, -dist * 0.62, dist * 0.55)
    cam.up.set(0, 0, dim === 3 ? 1 : 1)
    cam.lookAt(0, 0, 0)
    camera = cam
  }

  if (controls) controls.dispose()
  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.dampingFactor = 0.08
  controls.target.set(0, 0, 0)
  controls.update()
}

function initThree() {
  scene = new THREE.Scene()
  scene.background = new THREE.Color('#f8fafd')
  world = new THREE.Group()
  scene.add(world)

  staticGroup = new THREE.Group()
  obstacleGroup = new THREE.Group()
  trailGroup = new THREE.Group()
  agentGroup = new THREE.Group()
  markerGroup = new THREE.Group()
  world.add(staticGroup, obstacleGroup, trailGroup, agentGroup, markerGroup)

  scene.add(new THREE.AmbientLight(0xffffff, 1.5))
  const dir = new THREE.DirectionalLight(0xffffff, 1.6)
  dir.position.set(1, -1, 2)
  scene.add(dir)

  renderer = new THREE.WebGLRenderer({ antialias: true })
  renderer.setPixelRatio(Math.min(2, window.devicePixelRatio))
  host.value.appendChild(renderer.domElement)
  renderer.domElement.style.width = '100%'
  renderer.domElement.style.height = '100%'
  renderer.domElement.style.display = 'block'

  const resize = () => {
    if (!renderer) return
    const w = host.value.clientWidth
    const h = host.value.clientHeight
    if (!w || !h) return
    renderer.setSize(w, h, false)
    if (camera) {
      if (camera.isPerspectiveCamera) {
        camera.aspect = w / h
      } else {
        const span = Math.max(geometryInfo.size[0], geometryInfo.size[1]) * 0.62
        camera.left = -span * (w / h)
        camera.right = span * (w / h)
        camera.top = span
        camera.bottom = -span
      }
      camera.updateProjectionMatrix()
    }
  }
  observer = new ResizeObserver(resize)
  observer.observe(host.value)
  resize()

  const loop = () => {
    raf = requestAnimationFrame(loop)
    controls && controls.update()
    // 相机要等场景几何就绪后才创建，这里必须判空，否则首帧会以 null 相机渲染而抛错
    if (renderer && camera) renderer.render(scene, camera)
  }
  loop()
}

onMounted(() => {
  initThree()
  buildScene()
})

watch(
  () => [props.scene, props.frames],
  () => buildScene(),
  { deep: false },
)

watch(() => props.progress, applyProgress)
watch(() => props.viewMode, updateCamera)
watch(
  () => [props.showObstacles, props.showTrail],
  () => {
    if (obstacleGroup) obstacleGroup.visible = props.showObstacles
    if (trailGroup) trailGroup.visible = props.showTrail
  },
)

onBeforeUnmount(() => {
  cancelAnimationFrame(raf)
  observer && observer.disconnect()
  controls && controls.dispose()
  if (renderer) {
    renderer.dispose()
    renderer.domElement.remove()
    renderer = null
  }
  scene = null
  camera = null
})
</script>

<style scoped>
.stage {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 420px;
  border-radius: 12px;
  overflow: hidden;
  background: #f8fafd;
}

.legend {
  position: absolute;
  top: 12px;
  left: 14px;
  display: flex;
  gap: 14px;
  padding: 6px 10px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid var(--rs-line);
  font-size: 11.5px;
  color: var(--rs-text-2);
  z-index: 2;
}

.legend span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.legend i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}

.legend .uav {
  background: #2f6fbf;
}

.legend .attacker {
  background: #d9534f;
}

.legend .target {
  background: #2f9e73;
}

.legend .failure {
  background: #d9534f;
  box-shadow: 0 0 0 2px rgba(217, 83, 79, 0.2);
}

.stage-empty {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: var(--rs-text-3);
  font-size: 13px;
  background: #f8fafd;
}
</style>
