import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'home',
    component: () => import('@/views/HomeView.vue'),
    meta: { title: '首页' },
  },
  {
    path: '/console',
    component: () => import('@/layouts/ConsoleLayout.vue'),
    redirect: '/console/test',
    children: [
      {
        path: 'test',
        name: 'console-test',
        component: () => import('@/views/console/TestConsoleView.vue'),
        meta: { title: '测试控制台', subtitle: '配置测试参数并提交集群测试批次' },
      },
      {
        path: 'history',
        name: 'console-history',
        component: () => import('@/views/console/HistoryView.vue'),
        meta: { title: '测试历史', subtitle: '按批次检索历史测试记录，进入批次分析或测试详情' },
      },
      {
        path: 'batch/:id',
        name: 'batch-analysis',
        component: () => import('@/views/BatchAnalysisView.vue'),
        meta: { title: '批次分析', subtitle: '批次参数快照与结果统计' },
      },
      {
        path: 'run/:id',
        name: 'run-analysis',
        component: () => import('@/views/RunAnalysisView.vue'),
        meta: { title: '测试分析', subtitle: '轨迹复现、场景复现与任务时间轴' },
      },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

router.afterEach((to) => {
  const title = to.meta?.title
  document.title = title ? `${title} · 无人机集群算法逻辑漏洞发现系统` : '无人机集群算法逻辑漏洞发现系统'
})

export default router
