import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/tasks',
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { layout: 'blank' },
  },
  {
    path: '/tasks',
    name: 'tasks',
    component: () => import('@/views/TasksView.vue'),
  },
  {
    path: '/history',
    name: 'history',
    component: () => import('@/views/HistoryView.vue'),
  },
  {
    path: '/config',
    name: 'config',
    component: () => import('@/views/ConfigView.vue'),
  },
  {
    path: '/browser',
    name: 'browser',
    component: () => import('@/views/BrowserView.vue'),
  },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由守卫：未登录访问受保护页面 → 跳 /login；已登录访问 /login → 跳 /tasks
router.beforeEach(async (to) => {
  const auth = useAuthStore()
  // /login 是公开页面
  if (to.name === 'login') {
    if (auth.loggedIn) {
      return { name: 'tasks' }
    }
    return true
  }
  // 其他页面需要登录态
  if (!auth.loggedIn) {
    // 启动后第一次访问时主动 check 一次（避免每次路由切换都调 API）
    const ok = await auth.check()
    if (!ok) {
      return { name: 'login' }
    }
  }
  return true
})
