<template>
  <div class="page page-wide console">
    <div class="layout">
      <div class="form-col" v-loading="metaLoading">
        <!-- 算法 -->
        <section class="card">
          <div class="card-head">
            <div>
              <p class="card-title">1. 算法选择</p>
              <p class="card-hint">选择被测集群算法，规模档位、判据默认值与场景类型会随之联动</p>
            </div>
          </div>
          <div class="algo-row">
            <button
              v-for="a in algorithms"
              :key="a.key"
              class="algo-pick"
              :class="{ active: form.algo === a.name }"
              @click="selectAlgo(a)"
            >
              <div class="pick-top">
                <AlgoTag :algo="a.name" />
                <span class="dim">{{ a.dim }}D</span>
              </div>
              <p class="pick-desc">{{ a.summary }}</p>
              <p class="pick-foot">论文规模：{{ a.paper_sizes.join(' / ') }} 机</p>
            </button>
          </div>
        </section>

        <!-- 规模与模式 -->
        <section class="card">
          <div class="card-head">
            <div>
              <p class="card-title">2. 集群规模与测试模式</p>
              <p class="card-hint">规模档位取自论文表格；自定义规模支持 2–50 机；模式可多选</p>
            </div>
          </div>
          <div class="card-pad">
            <div class="field">
              <label class="field-label">集群规模</label>
              <div class="row wrap">
                <el-radio-group v-model="form.sizeMode">
                  <el-radio-button value="paper">论文档位</el-radio-button>
                  <el-radio-button value="custom">自定义</el-radio-button>
                </el-radio-group>
                <template v-if="form.sizeMode === 'paper'">
                  <el-radio-group v-model="form.size">
                    <el-radio-button v-for="s in currentAlgo.paper_sizes" :key="s" :value="s">
                      {{ s }} 机
                    </el-radio-button>
                  </el-radio-group>
                </template>
                <template v-else>
                  <el-input-number v-model="form.customSize" :min="2" :max="50" :step="1" controls-position="right" />
                  <span class="muted">架无人机（2–50）</span>
                </template>
              </div>
            </div>

            <div class="field">
              <label class="field-label">测试模式</label>
              <el-checkbox-group v-model="form.modes">
                <el-checkbox value="na" label="NA · 无攻击基线" />
                <el-checkbox value="sa" label="SA · 单攻击者" />
                <el-checkbox value="ma" label="MA · 多攻击者" />
              </el-checkbox-group>
              <p class="hint">
                三种模式使用同一批种子，可直接做同种子配对比较；失败率对比更有意义。
              </p>
            </div>
          </div>
        </section>

        <!-- 判据 -->
        <section class="card">
          <div class="card-head">
            <div>
              <p class="card-title">3. 失败判据</p>
              <p class="card-hint">判据决定“什么算失败”，阈值可沿用算法默认值，也可按本次场景自定义</p>
            </div>
          </div>
          <div class="card-pad">
            <div class="crit-row">
              <div class="crit-head">
                <el-switch v-model="form.criteria.enable_timeout" />
                <div>
                  <p class="crit-title">判据 ① · 任务超时</p>
                  <p class="crit-desc">仿真时长超过 {{ form.criteria.timeout_multiplier }} × CTime 视为超时未收敛</p>
                </div>
              </div>
              <el-input-number
                v-model="form.criteria.timeout_multiplier"
                :min="1"
                :max="20"
                :step="0.5"
                :disabled="!form.criteria.enable_timeout"
                size="small"
                controls-position="right"
              />
              <span class="unit">× CTime</span>
            </div>

            <div class="crit-row">
              <div class="crit-head">
                <el-switch v-model="form.criteria.enable_obstacle" />
                <div>
                  <p class="crit-title">判据 ② · 撞障碍</p>
                  <p class="crit-desc">
                    {{ currentAlgo.dim === 3 ? '球形障碍由 Monitor 碰撞球体判定' : '多边形障碍按内点判定' }}
                  </p>
                </div>
              </div>
              <el-select v-model="form.criteria.obstacleMode" size="small" style="width: 150px" :disabled="!form.criteria.enable_obstacle">
                <el-option label="算法默认判定" value="default" />
                <el-option label="自定义距离阈值" value="custom" />
              </el-select>
              <el-input-number
                v-if="form.criteria.obstacleMode === 'custom'"
                v-model="form.criteria.obstacle_dist_thr"
                :min="0.01"
                :step="0.05"
                :precision="2"
                size="small"
                controls-position="right"
              />
              <span v-if="form.criteria.obstacleMode === 'custom'" class="unit">m</span>
            </div>

            <div class="crit-row">
              <div class="crit-head">
                <el-switch v-model="form.criteria.enable_collision" />
                <div>
                  <p class="crit-title">判据 ② · 机间碰撞</p>
                  <p class="crit-desc">
                    算法默认阈值 {{ currentAlgo.defaults.drone_dist_thr ?? '未设' }}
                    {{ currentAlgo.defaults.drone_dist_thr ? 'm' : '' }}，可改为自定义
                  </p>
                </div>
              </div>
              <el-select v-model="form.criteria.collisionMode" size="small" style="width: 170px" :disabled="!form.criteria.enable_collision">
                <el-option
                  :label="`算法默认（${currentAlgo.defaults.drone_dist_thr ?? '未设'} m）`"
                  value="default"
                />
                <el-option label="自定义阈值" value="custom" />
              </el-select>
              <el-input-number
                v-if="form.criteria.collisionMode === 'custom'"
                v-model="form.criteria.drone_dist_thr"
                :min="0.001"
                :step="0.01"
                :precision="3"
                size="small"
                controls-position="right"
              />
              <span v-if="form.criteria.collisionMode === 'custom'" class="unit">m</span>
            </div>

            <div class="crit-row disabled">
              <div class="crit-head">
                <el-switch :model-value="false" disabled />
                <div>
                  <p class="crit-title">判据 ③ · 轨迹偏离</p>
                  <p class="crit-desc">尚未接入采集链路，当前批次不可开启</p>
                </div>
              </div>
              <span class="chip chip-ghost">未接入</span>
            </div>
          </div>
        </section>

        <!-- 场景 -->
        <section class="card">
          <div class="card-head">
            <div>
              <p class="card-title">4. 场景设置</p>
              <p class="card-hint">内置论文地图 + 自定义场景；同一算法下可切换多个场景</p>
            </div>
            <el-button :icon="Plus" @click="openSceneDrawer">新建自定义场景</el-button>
          </div>
          <div class="scenario-grid">
            <button
              v-for="s in scenarios"
              :key="s.id"
              class="scenario-pick"
              :class="{ active: form.scenarioId === s.id }"
              @click="form.scenarioId = s.id"
            >
              <div class="scenario-pic">
                <SceneThumb
                  :dim="s.dim"
                  :bounds="s.bounds"
                  :obstacles="detailOf(s.id).obstacles"
                  :targets="detailOf(s.id).targets"
                  :init-positions="detailOf(s.id).init_positions"
                />
              </div>
              <div class="scenario-info">
                <p class="scenario-name">{{ s.name }}</p>
                <p class="scenario-sub">
                  {{ s.dim }}D · {{ s.obstacle_count }} 个障碍 · {{ s.source_type === 'builtin' ? '内置' : '自定义' }}
                </p>
                <p class="scenario-sub mono">{{ boundsText(s.bounds) }}</p>
              </div>
              <el-icon v-if="form.scenarioId === s.id" class="check"><CircleCheckFilled /></el-icon>
            </button>
            <p v-if="!scenarios.length" class="muted pad">该算法下还没有可用场景，请新建自定义场景。</p>
          </div>
        </section>

        <!-- 种子 -->
        <section class="card">
          <div class="card-head">
            <div>
              <p class="card-title">5. 种子选择</p>
              <p class="card-hint">种子决定攻击者初始位置与采样序列；固定种子才能复现失败</p>
            </div>
          </div>
          <div class="card-pad">
            <div class="field">
              <el-radio-group v-model="form.seedMode">
                <el-radio-button value="range">指定区间</el-radio-button>
                <el-radio-button value="random">随机抽取</el-radio-button>
              </el-radio-group>
            </div>
            <div class="field row wrap">
              <span class="field-label inline">种子区间</span>
              <el-input-number v-model="form.seedFrom" :min="1" :max="1000000" :controls="false" style="width: 120px" />
              <span class="muted">至</span>
              <el-input-number v-model="form.seedTo" :min="1" :max="1000000" :controls="false" style="width: 120px" />
              <template v-if="form.seedMode === 'random'">
                <span class="field-label inline">抽取数量</span>
                <el-input-number v-model="form.seedCount" :min="1" :max="seedCapacity" style="width: 130px" />
              </template>
              <span class="muted">共 {{ seedList.length }} 个种子</span>
            </div>
            <div class="seed-preview">
              <template v-if="form.seedMode === 'random'">
                <span class="chip chip-ghost">
                  提交时从 {{ Math.min(form.seedFrom, form.seedTo) }}–{{ Math.max(form.seedFrom, form.seedTo) }}
                  中随机抽取 {{ seedList.length }} 个种子
                </span>
              </template>
              <template v-else>
                <span v-for="s in seedPreview" :key="s" class="chip chip-ghost mono">{{ s }}</span>
                <span v-if="seedList.length > seedPreview.length" class="muted more">
                  … 另有 {{ seedList.length - seedPreview.length }} 个
                </span>
              </template>
            </div>
            <p class="hint">预计任务数 = 种子数 {{ seedList.length }} × 模式数 {{ form.modes.length }} = <b>{{ plannedTasks }}</b></p>
          </div>
        </section>

        <!-- 高级参数 -->
        <section class="card">
          <div class="card-head">
            <div>
              <p class="card-title">6. 高级参数</p>
              <p class="card-hint">默认值来自论文与算法实现，通常无需修改</p>
            </div>
          </div>
          <div class="card-pad adv-grid">
            <div class="adv">
              <span>候选采样点数</span>
              <el-input-number v-model="form.criteria.candidate_count" :min="1" :max="1000" size="small" controls-position="right" />
            </div>
            <div class="adv">
              <span>最大迭代轮数</span>
              <el-input-number
                v-model="form.criteria.max_iterations"
                :min="1"
                :max="100000"
                size="small"
                controls-position="right"
                :placeholder="`默认 ${currentAlgo.defaults.max_iterations ?? '不限'}`"
              />
            </div>
            <div class="adv">
              <span>单任务仿真时长上限</span>
              <el-input-number v-model="form.criteria.max_sim_time" :min="1" :max="100000" size="small" controls-position="right" placeholder="不限" />
            </div>
            <div class="adv">
              <span>采样高斯 σ</span>
              <el-input-number v-model="form.criteria.sample_sigma" :min="0.01" :step="0.1" :precision="2" size="small" controls-position="right" placeholder="算法默认" />
            </div>
            <div class="adv">
              <span>并发任务数</span>
              <el-input-number v-model="form.workers" :min="1" :max="64" size="small" controls-position="right" />
            </div>
            <div class="adv">
              <span>单任务硬超时（秒）</span>
              <el-input-number v-model="form.taskTimeout" :min="60" :max="86400" size="small" controls-position="right" placeholder="调度器默认" />
            </div>
            <div v-if="currentAlgo.defaults.support_attack_chain" class="adv">
              <span>A3 攻击链</span>
              <el-switch v-model="form.a3Link" size="small" active-text="进入集群势场" />
            </div>
            <div v-if="currentAlgo.defaults.support_waypoints_mode" class="adv">
              <span>Howard 航点模式</span>
              <el-select v-model="form.waypointsMode" size="small" style="width: 130px">
                <el-option label="shared" value="shared" />
                <el-option label="independent" value="indep" />
              </el-select>
            </div>
            <div class="adv">
              <span>采集逐帧轨迹</span>
              <el-switch v-model="form.trace" size="small" active-text="开启回放" />
            </div>
            <div class="adv wide">
              <span>批次备注</span>
              <el-input v-model="form.note" size="small" placeholder="例如：Howard 6 机，球形障碍回归" />
            </div>
          </div>
        </section>
      </div>

      <!-- 右侧摘要 -->
      <aside class="summary">
        <section class="card card-pad">
          <p class="card-title">本次提交</p>
          <p class="card-hint">提交后批次进入队列，调度器执行完成后自动导入结果</p>
          <div class="divider" />
          <dl class="kv small">
            <dt>算法</dt><dd>{{ form.algo }}</dd>
            <dt>集群规模</dt><dd>{{ effectiveSize }} 机</dd>
            <dt>模式</dt><dd>{{ modeText }}</dd>
            <dt>场景</dt><dd>{{ selectedScenario?.name || '未选择' }}</dd>
            <dt>种子</dt><dd class="mono">{{ seedLabel }}</dd>
            <dt>判据</dt><dd>{{ criteriaText }}</dd>
            <dt>预计任务</dt><dd><b>{{ plannedTasks }}</b> 个</dd>
          </dl>
          <div class="divider" />
          <p class="side-label">调度命令预览</p>
          <pre class="cmd">{{ commandPreview }}</pre>
          <el-button type="primary" class="submit" :loading="submitting" :disabled="!canSubmit" @click="submit">
            提交测试批次
          </el-button>
          <p v-if="!canSubmit" class="hint center">请至少选择一种模式、一个场景</p>
        </section>

        <section class="card card-pad tips">
          <p class="side-label">提示</p>
          <ul>
            <li>同一批次内所有模式共享种子，便于做配对统计。</li>
            <li>判据阈值改动会生成新的判据快照，历史批次不受影响。</li>
            <li>自定义场景按几何哈希去重，重复提交不会产生重复记录。</li>
          </ul>
        </section>
      </aside>
    </div>

    <!-- 自定义场景 -->
    <el-drawer v-model="drawer" title="新建自定义场景" size="920px" :close-on-click-modal="false">
      <div class="drawer-body">
        <div class="drawer-form">
          <div class="field">
            <label class="field-label">场景名称</label>
            <el-input v-model="sceneForm.name" placeholder="例如：交叉通道 / 6 机" />
          </div>

          <div class="field">
            <label class="field-label">地图边界</label>
            <div class="row wrap">
              <template v-for="ax in axes" :key="ax">
                <span class="axis">{{ ax }}</span>
                <el-input-number v-model="sceneForm.bounds[ax][0]" :step="1" size="small" controls-position="right" style="width: 110px" />
                <span class="muted">–</span>
                <el-input-number v-model="sceneForm.bounds[ax][1]" :step="1" size="small" controls-position="right" style="width: 110px" />
              </template>
            </div>
          </div>

          <div class="field">
            <div class="row between">
              <label class="field-label">
                {{ currentAlgo.dim === 3 ? '球形障碍（球心 + 半径）' : '多边形障碍（顶点）' }}
              </label>
              <el-button size="small" :icon="Plus" @click="addObstacle">添加障碍</el-button>
            </div>

            <!-- 2D 多边形 -->
            <div v-if="currentAlgo.dim === 2" class="ob-list">
              <div v-for="(ob, oi) in sceneForm.polygons" :key="'ob' + oi" class="ob-card">
                <div class="ob-head">
                  <span>多边形 {{ oi + 1 }} · {{ ob.pts.length }} 个顶点</span>
                  <div class="row">
                    <el-button size="small" text :icon="Plus" @click="addPoint(ob)">顶点</el-button>
                    <el-button size="small" text type="danger" :icon="Delete" @click="sceneForm.polygons.splice(oi, 1)">删除</el-button>
                  </div>
                </div>
                <div class="pt-grid">
                  <div v-for="(pt, pi) in ob.pts" :key="'p' + pi" class="pt">
                    <span class="mono pt-no">{{ pi + 1 }}</span>
                    <el-input-number v-model="pt[0]" :step="1" size="small" controls-position="right" style="width: 92px" />
                    <el-input-number v-model="pt[1]" :step="1" size="small" controls-position="right" style="width: 92px" />
                    <el-button size="small" text :icon="Close" :disabled="ob.pts.length <= 3" @click="ob.pts.splice(pi, 1)" />
                  </div>
                </div>
              </div>
            </div>

            <!-- 3D 球体 -->
            <div v-else class="ob-list">
              <div v-for="(ob, oi) in sceneForm.spheres" :key="'sp' + oi" class="ob-card">
                <div class="ob-head">
                  <span>球体 {{ oi + 1 }}</span>
                  <el-button size="small" text type="danger" :icon="Delete" @click="sceneForm.spheres.splice(oi, 1)">删除</el-button>
                </div>
                <div class="row wrap">
                  <span class="axis">c</span>
                  <el-input-number v-model="ob.c[0]" :step="1" size="small" controls-position="right" style="width: 100px" />
                  <el-input-number v-model="ob.c[1]" :step="1" size="small" controls-position="right" style="width: 100px" />
                  <el-input-number v-model="ob.c[2]" :step="1" size="small" controls-position="right" style="width: 100px" />
                  <span class="axis">r</span>
                  <el-input-number v-model="ob.r" :min="0.1" :step="0.5" size="small" controls-position="right" style="width: 100px" />
                </div>
              </div>
            </div>
          </div>

          <div class="field">
            <div class="row between">
              <label class="field-label">目标点</label>
              <el-button size="small" :icon="Plus" @click="addTarget">添加目标点</el-button>
            </div>
            <div class="row wrap">
              <div v-for="(t, ti) in sceneForm.targets" :key="'t' + ti" class="target-row">
                <template v-for="(_, ai) in axes" :key="ai">
                  <el-input-number v-model="t[ai]" :step="1" size="small" controls-position="right" style="width: 92px" />
                </template>
                <el-button size="small" text :icon="Close" @click="sceneForm.targets.splice(ti, 1)" />
              </div>
            </div>
          </div>
        </div>

        <div class="drawer-preview">
          <p class="side-label">实时预览</p>
          <div class="preview-box">
            <SceneThumb
              :dim="currentAlgo.dim"
              :bounds="sceneBounds"
              :obstacles="sceneObstacles"
              :targets="sceneForm.targets"
              :init-positions="[]"
            />
          </div>
          <dl class="kv small preview-kv">
            <dt>维度</dt><dd>{{ currentAlgo.dim }}D</dd>
            <dt>障碍</dt><dd>{{ sceneObstacles.length }} 个</dd>
            <dt>目标点</dt><dd>{{ sceneForm.targets.length }} 个</dd>
            <dt>初始编队</dt><dd>提交时按边界自动生成</dd>
          </dl>
          <p class="hint">
            预览按几何坐标实时绘制；提交后端会做边界与退化校验，并按几何哈希去重。
          </p>
          <el-button type="primary" class="create-btn" :loading="creating" @click="createScenario">
            保存场景并选中
          </el-button>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  CircleCheckFilled,
  Close,
  Delete,
  Plus,
} from '@element-plus/icons-vue'
import { api } from '@/api'
import AlgoTag from '@/components/AlgoTag.vue'
import SceneThumb from '@/components/SceneThumb.vue'

const router = useRouter()

const metaLoading = ref(false)
const submitting = ref(false)
const creating = ref(false)
const drawer = ref(false)
const meta = ref(null)
const scenarios = ref([])
const scenarioDetails = reactive({})

const ALGO_ORDER = ['Adaptive Swarm', 'Pietro', 'Howard']

const form = reactive({
  algo: 'Adaptive Swarm',
  sizeMode: 'paper',
  size: 4,
  customSize: 8,
  modes: ['sa'],
  criteria: {
    enable_timeout: true,
    timeout_multiplier: 2,
    enable_obstacle: true,
    enable_collision: true,
    obstacleMode: 'default',
    collisionMode: 'default',
    obstacle_dist_thr: 0.5,
    drone_dist_thr: 0.07,
    candidate_count: 20,
    max_iterations: null,
    max_sim_time: null,
    sample_sigma: null,
  },
  scenarioId: null,
  seedMode: 'range',
  seedFrom: 1,
  seedTo: 10,
  seedCount: 10,
  workers: 8,
  taskTimeout: null,
  trace: true,
  a3Link: true,
  waypointsMode: 'shared',
  note: '',
})

const sceneForm = reactive({
  name: '',
  bounds: { x: [0, 25], y: [0, 25], z: [0, 25] },
  polygons: [{ pts: [[5, 5], [12, 5], [12, 12], [5, 12]] }],
  spheres: [{ c: [12, 12, 12], r: 3 }],
  targets: [[20, 20]],
})

const algorithms = computed(() => {
  const list = meta.value?.algorithms || []
  return [...list].sort((a, b) => ALGO_ORDER.indexOf(a.name) - ALGO_ORDER.indexOf(b.name))
})

const currentAlgo = computed(
  () =>
    algorithms.value.find((a) => a.name === form.algo) || {
      name: form.algo,
      dim: 2,
      paper_sizes: [4],
      defaults: {},
      summary: '',
    },
)

const axes = computed(() => (currentAlgo.value.dim === 3 ? ['x', 'y', 'z'] : ['x', 'y']))

const effectiveSize = computed(() =>
  form.sizeMode === 'paper' ? form.size : Math.min(50, Math.max(2, form.customSize || 2)),
)

const modeText = computed(() => form.modes.map((m) => ({ na: 'NA', sa: 'SA', ma: 'MA' })[m]).join(' / ') || '未选择')

const seedCapacity = computed(() => Math.max(1, form.seedTo - form.seedFrom + 1))

const seedList = computed(() => {
  const from = Math.min(form.seedFrom, form.seedTo)
  const to = Math.max(form.seedFrom, form.seedTo)
  if (form.seedMode === 'random') {
    const n = Math.min(Math.max(1, form.seedCount || 1), to - from + 1)
    return Array.from({ length: n }, (_, i) => from + i) // 后端会真正随机抽取，这里只做数量预览
  }
  return Array.from({ length: to - from + 1 }, (_, i) => from + i)
})

const seedPreview = computed(() => seedList.value.slice(0, 12))
const seedLabel = computed(() =>
  form.seedMode === 'random'
    ? `随机 ${seedList.value.length} 个（${form.seedFrom}–${form.seedTo}）`
    : `${form.seedFrom}–${form.seedTo}（${seedList.value.length} 个）`,
)

const plannedTasks = computed(() => seedList.value.length * (form.modes.length || 0))

const selectedScenario = computed(() => scenarios.value.find((s) => s.id === form.scenarioId) || null)

const criteriaText = computed(() => {
  const c = form.criteria
  const parts = []
  if (c.enable_timeout) parts.push(`① ${c.timeout_multiplier}×CTime`)
  if (c.enable_obstacle) parts.push('② 撞障碍')
  if (c.enable_collision) parts.push('② 机间')
  return parts.join(' · ') || '未启用判据'
})

const canSubmit = computed(() => !!form.scenarioId && form.modes.length > 0)

const commandPreview = computed(() => {
  const key = { 'Adaptive Swarm': 'a1', Pietro: 'a2', Howard: 'a3' }[form.algo]
  const strat = form.modes.map((m) => ({ na: 0, sa: 2, ma: 3 })[m]).sort().join(',') || '2'
  const seeds =
    form.seedMode === 'random'
      ? `${form.seedFrom}-${form.seedTo}`
      : form.seedFrom === form.seedTo
        ? String(form.seedFrom)
        : `${form.seedFrom}-${form.seedTo}`
  return `python sched.py --algo ${key} --size ${effectiveSize.value} --seeds ${seeds} --strategies ${strat} --workers ${form.workers}`
})

const sceneBounds = computed(() => {
  const b = {}
  axes.value.forEach((ax) => {
    const v = sceneForm.bounds[ax] || [0, 25]
    b[ax] = [Number(v[0] ?? 0), Number(v[1] ?? 25)]
  })
  return b
})

const sceneObstacles = computed(() => {
  if (currentAlgo.value.dim === 3) {
    return sceneForm.spheres
      .filter((s) => s.c.every((v) => typeof v === 'number'))
      .map((s) => ({ kind: 'sphere', c: s.c.map(Number), r: Number(s.r) }))
  }
  return sceneForm.polygons
    .filter((p) => p.pts.length >= 3)
    .map((p) => ({ kind: 'polygon', pts: p.pts.map((pt) => [Number(pt[0]), Number(pt[1])]) }))
})

function detailOf(id) {
  return scenarioDetails[id] || { obstacles: [], targets: [], init_positions: [] }
}

function boundsText(b) {
  if (!b) return ''
  return ['x', 'y', 'z']
    .filter((a) => Array.isArray(b[a]))
    .map((a) => `${a} ${b[a][0]}–${b[a][1]}`)
    .join('  ')
}

function applyAlgoDefaults() {
  const d = currentAlgo.value.defaults || {}
  form.sizeMode = 'paper'
  form.size = currentAlgo.value.paper_sizes[0] || 4
  form.criteria.timeout_multiplier = d.timeout_multiplier ?? 2
  form.criteria.candidate_count = d.candidate_count ?? 20
  form.criteria.max_iterations = d.max_iterations ?? null
  form.criteria.max_sim_time = d.max_sim_time ?? null
  form.criteria.sample_sigma = d.sample_sigma ?? null
  form.criteria.drone_dist_thr = d.drone_dist_thr ?? 0.1
  form.criteria.obstacle_dist_thr = d.obstacle_dist_thr ?? 0.5
  form.criteria.obstacleMode = 'default'
  form.criteria.collisionMode = 'default'
  form.criteria.enable_obstacle = true
  form.criteria.enable_collision = true
  form.criteria.enable_timeout = true
}

function selectAlgo(a) {
  if (form.algo === a.name) return
  form.algo = a.name
  applyAlgoDefaults()
  loadScenarios()
}

async function loadScenarios() {
  try {
    const data = await api.scenarios({ algo: form.algo })
    scenarios.value = data.items
    if (!scenarios.value.some((s) => s.id === form.scenarioId)) {
      form.scenarioId = scenarios.value[0]?.id ?? null
    }
    await Promise.all(
      scenarios.value.map(async (s) => {
        if (scenarioDetails[s.id]) return
        const d = await api.scenario(s.id)
        scenarioDetails[s.id] = {
          obstacles: d.obstacles || [],
          targets: d.targets || [],
          init_positions: d.init_positions || [],
        }
      }),
    )
  } catch (e) {
    ElMessage.error(e.message || '场景加载失败')
  }
}

function openSceneDrawer() {
  sceneForm.name = ''
  const b = sceneBounds.value
  const x0 = b.x?.[0] ?? 0
  const x1 = b.x?.[1] ?? 25
  const y0 = b.y?.[0] ?? 0
  const y1 = b.y?.[1] ?? 25
  sceneForm.bounds = { x: [x0, x1], y: [y0, y1], z: [0, Math.max(25, x1 - x0)] }
  const w = (x1 - x0) * 0.2
  const h = (y1 - y0) * 0.2
  sceneForm.polygons =
    currentAlgo.value.dim === 2
      ? [{ pts: [[x0 + w, y0 + h], [x0 + 2 * w, y0 + h], [x0 + 2 * w, y0 + 2 * h], [x0 + w, y0 + 2 * h]] }]
      : []
  sceneForm.spheres =
    currentAlgo.value.dim === 3
      ? [{ c: [(x0 + x1) / 2, (y0 + y1) / 2, Math.max(25, x1 - x0) * 0.3], r: Math.max(1, Math.min(x1 - x0, y1 - y0) * 0.08) }]
      : []
  sceneForm.targets = [[x1 - w, y1 - h]]
  drawer.value = true
}

function addObstacle() {
  if (currentAlgo.value.dim === 2) {
    sceneForm.polygons.push({ pts: [[1, 1], [3, 1], [3, 3], [1, 3]] })
  } else {
    sceneForm.spheres.push({ c: [0, 0, 0], r: 2 })
  }
}

function addPoint(ob) {
  ob.pts.push([0, 0])
}

function addTarget() {
  sceneForm.targets.push(axes.value.map(() => 0))
}

async function createScenario() {
  creating.value = true
  try {
    const payload = {
      algo: form.algo,
      swarm_size: effectiveSize.value,
      name: sceneForm.name || undefined,
      dim: currentAlgo.value.dim,
      bounds: Object.fromEntries(
        axes.value.map((ax) => {
          const v = sceneForm.bounds[ax]
          return [ax, [Number(v[0]), Number(v[1])]]
        }),
      ),
      obstacles: sceneObstacles.value,
      targets: sceneForm.targets.map((t) => t.map(Number)),
    }
    const res = await api.createScenario(payload)
    ElMessage.success(res.created ? '场景已创建' : '该几何已存在，直接复用')
    drawer.value = false
    await loadScenarios()
    form.scenarioId = res.id
  } catch (e) {
    ElMessage.error(e.message || '场景创建失败')
  } finally {
    creating.value = false
  }
}

async function submit() {
  const c = form.criteria
  submitting.value = true
  try {
    const payload = {
      algo: form.algo,
      swarm_size: effectiveSize.value,
      modes: form.modes,
      scenario_ids: [form.scenarioId],
      criteria: {
        enable_timeout: c.enable_timeout,
        timeout_multiplier: c.timeout_multiplier,
        enable_obstacle: c.enable_obstacle,
        enable_collision: c.enable_collision,
        obstacle_dist_thr: c.enable_obstacle && c.obstacleMode === 'custom' ? c.obstacle_dist_thr : null,
        drone_dist_thr: c.enable_collision && c.collisionMode === 'custom' ? c.drone_dist_thr : null,
        candidate_count: c.candidate_count,
        max_iterations: c.max_iterations,
        max_sim_time: c.max_sim_time,
        sample_sigma: c.sample_sigma,
        extra: {
          a3_link: currentAlgo.value.defaults.support_attack_chain ? (form.a3Link ? 1 : 0) : undefined,
          waypoints_mode: currentAlgo.value.defaults.support_waypoints_mode ? form.waypointsMode : undefined,
        },
      },
      seeds: {
        mode: form.seedMode,
        seed_from: Math.min(form.seedFrom, form.seedTo),
        seed_to: Math.max(form.seedFrom, form.seedTo),
        count: form.seedMode === 'random' ? form.seedCount : undefined,
      },
      workers: form.workers,
      task_timeout: form.taskTimeout,
      trace: form.trace,
      note: form.note || undefined,
    }
    const res = await api.createBatch(payload)
    const seedsText = res.seeds.slice(0, 8).join(', ') + (res.seeds.length > 8 ? ' …' : '')
    ElMessageBox.alert(
      `<div style="font-size:13px;line-height:1.9">
        <p>批次 <b>#${res.batch_id}</b> ${res.created ? '已登记' : '已存在（配置相同）'}</p>
        <p>预计任务数：<b>${res.planned_tasks}</b>；种子：${seedsText}</p>
        <p style="background:#f6f8fc;padding:8px;border-radius:6px;word-break:break-all;font-family:monospace;font-size:11px">${res.command}</p>
      </div>`,
      res.created ? '批次已提交' : '批次已存在',
      { dangerouslyUseHTMLString: true, confirmButtonText: '查看批次分析' },
    )
      .then(() => router.push(`/console/batch/${res.batch_id}`))
      .catch(() => {})
  } catch (e) {
    ElMessage.error(e.message || '提交失败')
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  metaLoading.value = true
  try {
    meta.value = await api.meta()
    applyAlgoDefaults()
    await loadScenarios()
  } catch (e) {
    ElMessage.error(e.message || '元数据加载失败')
  } finally {
    metaLoading.value = false
  }
})
</script>

<style scoped>
.console {
  padding: 26px 32px 56px;
}

.layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 20px;
  align-items: start;
}

.form-col {
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-width: 0;
}

.summary {
  position: sticky;
  top: 86px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.algo-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
  padding: 20px 22px;
}

.algo-pick {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
  border: 1px solid var(--rs-line);
  border-radius: 12px;
  background: var(--rs-surface-2);
  text-align: left;
  cursor: pointer;
  transition: border-color 0.18s, background 0.18s, box-shadow 0.18s;
}

.algo-pick:hover {
  border-color: #c3d5ea;
}

.algo-pick.active {
  border-color: var(--rs-primary);
  background: #f6faff;
  box-shadow: 0 0 0 3px rgba(31, 78, 140, 0.08);
}

.pick-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.dim {
  color: var(--rs-text-3);
  font-size: 11px;
}

.pick-desc {
  margin: 0;
  color: var(--rs-text-2);
  font-size: 12px;
  line-height: 1.7;
}

.pick-foot {
  margin: 0;
  color: var(--rs-text-3);
  font-size: 11.5px;
}

.field {
  margin-bottom: 18px;
}

.field:last-child {
  margin-bottom: 0;
}

.field-label {
  display: block;
  margin-bottom: 8px;
  color: var(--rs-text-2);
  font-size: 12.5px;
}

.field-label.inline {
  display: inline;
  margin: 0 4px 0 0;
}

.row.wrap {
  flex-wrap: wrap;
  row-gap: 10px;
}

.row.between {
  justify-content: space-between;
}

.hint {
  margin: 8px 0 0;
  color: var(--rs-text-3);
  font-size: 11.5px;
  line-height: 1.75;
}

.hint.center {
  text-align: center;
}

.crit-row {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 0;
  border-bottom: 1px dashed var(--rs-line);
}

.crit-row:first-child {
  padding-top: 0;
}

.crit-row:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.crit-row.disabled {
  opacity: 0.72;
}

.crit-head {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  flex: 1;
  min-width: 0;
}

.crit-title {
  margin: 0 0 2px;
  font-size: 13px;
  font-weight: 600;
}

.crit-desc {
  margin: 0;
  color: var(--rs-text-3);
  font-size: 11.5px;
}

.unit {
  color: var(--rs-text-3);
  font-size: 12px;
}

.scenario-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 14px;
  padding: 20px 22px;
}

.scenario-pick {
  position: relative;
  padding: 10px;
  border: 1px solid var(--rs-line);
  border-radius: 12px;
  background: var(--rs-surface-2);
  cursor: pointer;
  text-align: left;
  transition: border-color 0.18s, background 0.18s;
}

.scenario-pick:hover {
  border-color: #c3d5ea;
}

.scenario-pick.active {
  border-color: var(--rs-primary);
  background: #f6faff;
}

.scenario-pic {
  height: 130px;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
}

.scenario-info {
  padding: 8px 4px 2px;
}

.scenario-name {
  margin: 0 0 3px;
  font-size: 12.5px;
  font-weight: 600;
}

.scenario-sub {
  margin: 0;
  color: var(--rs-text-3);
  font-size: 11px;
  line-height: 1.6;
}

.check {
  position: absolute;
  top: 14px;
  right: 14px;
  color: var(--rs-primary);
  font-size: 18px;
  background: #fff;
  border-radius: 50%;
}

.seed-preview {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 12px;
  padding: 10px;
  border-radius: 8px;
  background: var(--rs-surface-2);
}

.more {
  font-size: 11.5px;
  align-self: center;
}

.adv-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px 20px;
}

.adv {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.adv span {
  color: var(--rs-text-2);
  font-size: 12px;
}

.adv.wide {
  grid-column: span 3;
}

.side-label {
  margin: 0 0 8px;
  color: var(--rs-text-3);
  font-size: 11.5px;
  letter-spacing: 0.03em;
}

.cmd {
  margin: 0 0 16px;
  padding: 10px;
  border-radius: 8px;
  background: #f6f8fc;
  color: #33475f;
  font-size: 11px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: 'JetBrains Mono', Consolas, monospace;
}

.kv.small {
  grid-template-columns: 70px 1fr;
  font-size: 12.5px;
}

.submit {
  width: 100%;
}

.tips ul {
  margin: 0;
  padding-left: 16px;
  color: var(--rs-text-3);
  font-size: 11.5px;
  line-height: 1.9;
}

.pad {
  padding: 8px 4px;
}

.drawer-body {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 24px;
}

.drawer-form {
  min-width: 0;
}

.axis {
  display: inline-block;
  min-width: 14px;
  color: var(--rs-text-3);
  font-family: monospace;
  font-size: 12px;
}

.ob-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ob-card {
  padding: 12px;
  border: 1px solid var(--rs-line);
  border-radius: 10px;
  background: var(--rs-surface-2);
}

.ob-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  font-size: 12px;
  color: var(--rs-text-2);
}

.pt-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.pt {
  display: flex;
  align-items: center;
  gap: 4px;
}

.pt-no {
  width: 16px;
  color: var(--rs-text-3);
}

.target-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.drawer-preview {
  position: sticky;
  top: 0;
  align-self: start;
}

.preview-box {
  height: 260px;
  border: 1px solid var(--rs-line);
  border-radius: 10px;
  overflow: hidden;
  background: #fff;
}

.preview-kv {
  margin: 12px 0;
  grid-template-columns: 66px 1fr;
  font-size: 12px;
}

.create-btn {
  width: 100%;
  margin-top: 10px;
}

@media (max-width: 1280px) {
  .layout {
    grid-template-columns: 1fr;
  }

  .summary {
    position: static;
    display: grid;
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 980px) {
  .algo-row,
  .adv-grid {
    grid-template-columns: 1fr 1fr;
  }

  .drawer-body {
    grid-template-columns: 1fr;
  }
}
</style>
