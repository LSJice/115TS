# Plan B1: Vue3 Web UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建 Vue3 + TypeScript + Element Plus 前端，覆盖扫码登录、任务管理（含 SSE 实时推送）、历史检索、配置管理、115 目录浏览 5 大视图，与 Plan A 后端 API 完整对接。

**Architecture:** 经典 SPA——Vite 开发服务器（5173）通过 proxy 转发 `/api` 到 FastAPI（8000）；生产构建后输出 `frontend/dist/` 由 FastAPI 静态托管（main.py 已支持）。状态管理用 Pinia，路由用 Vue Router 4，HTTP 用 axios + 拦截器自动注入 Bearer Token。SSE 用原生 EventSource API。

**Tech Stack:**
- 构建：Vite 5 + TypeScript 5
- 框架：Vue 3.4+（Composition API + `<script setup>`）
- UI：Element Plus 2.x（中文文档完善、表单/表格组件成熟）
- 路由：vue-router 4
- 状态：pinia 2
- HTTP：axios 1
- SSE：原生 EventSource（无第三方依赖）
- 测试：本计划不要求前端单元测试（spec §7.3 明确"前端组件初期手动验证"）

---

## File Structure

```
frontend/
├── package.json              # 依赖声明
├── vite.config.ts            # dev proxy + build 输出配置
├── tsconfig.json             # TS 配置（含 vue-tsc）
├── tsconfig.node.json        # Node 端 TS 配置（vite.config.ts 用）
├── index.html                # 入口 HTML
├── env.d.ts                  # Vite env 类型声明
├── .gitignore                # node_modules、dist 等
└── src/
    ├── main.ts               # 应用入口（挂载 Pinia + Router + Element Plus）
    ├── App.vue               # 根组件（仅 <router-view/>）
    ├── router/
    │   └── index.ts          # 5 个路由定义
    ├── stores/
    │   ├── auth.ts           # 登录态 + 启动时检查
    │   └── config.ts         # 配置缓存
    ├── api/
    │   ├── client.ts         # axios 实例 + Bearer Token 拦截器 + 错误处理
    │   ├── auth.ts           # /api/auth/* 接口
    │   ├── tasks.ts          # /api/tasks/* 接口
    │   ├── history.ts        # /api/history/* 接口
    │   ├── dirs.ts           # /api/dirs/* 接口
    │   └── config.ts         # /api/config/* 接口
    ├── types/
    │   └── index.ts          # TaskOut / ConfigOut / HistoryOut 等类型（与后端 schemas 对齐）
    ├── components/
    │   └── AppLayout.vue     # 主布局（Element Plus container + 侧边栏菜单）
    ├── views/
    │   ├── LoginView.vue     # /login 扫码登录
    │   ├── TasksView.vue     # /tasks 任务列表 + 提交 + SSE
    │   ├── HistoryView.vue   # /history 历史搜索 + 删除
    │   ├── ConfigView.vue    # /config 配置查看/编辑
    │   └── BrowserView.vue   # /browser 115 目录浏览
    └── styles/
        └── main.css          # 全局样式
```

每个文件单一职责：API 层按业务域拆分（5 个模块），store 按数据域拆分（auth + config），view 按用户场景拆分（5 个页面）。

---

## Conventions

**前端不强制 TDD**（spec §7.3），但每个任务必须有可执行的验证步骤：
- "运行 dev server" / "访问 URL" / "打开浏览器控制台检查无错误"
- 每个 task 完成后端到端可点击验证

**提交规范：**
- 每个 task 一个 commit
- commit message 格式：`feat(fe): <短描述>` / `chore(fe): <短描述>` / `fix(fe): <短描述>`
- 分支：当前默认分支（用户已授权 git 操作）

**安全相关：**
- Token 存 localStorage（key: `115_token`）—— 单用户本地场景，足够
- axios 拦截器自动注入 `Authorization: Bearer <token>`
- 401 响应自动清空 token 并跳转 /login

**中文 UI 文案：** 所有界面文字、按钮、提示一律中文

---

### Task 1: 项目脚手架与依赖

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/.gitignore`
- Create: `frontend/index.html`
- Create: `frontend/env.d.ts`
- Create: `frontend/src/main.ts`
- Create: `frontend/src/App.vue`

- [ ] **Step 1.1: 创建 frontend 目录**

```bash
mkdir -p frontend/src
```

- [ ] **Step 1.2: 创建 `frontend/package.json`**

```json
{
  "name": "115-auto-save-fe",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc --noEmit && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "axios": "^1.7.7",
    "element-plus": "^2.8.5",
    "pinia": "^2.2.4",
    "vue": "^3.5.12",
    "vue-router": "^4.4.5"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.1.4",
    "@vue/tsconfig": "^0.5.1",
    "typescript": "~5.6.3",
    "vite": "^5.4.10",
    "vue-tsc": "^2.1.10"
  }
}
```

- [ ] **Step 1.3: 创建 `frontend/.gitignore`**

```
node_modules
dist
*.local
.vite
```

- [ ] **Step 1.4: 创建 `frontend/index.html`**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>115 自动转存</title>
</head>
<body>
  <div id="app"></div>
  <script type="module" src="/src/main.ts"></script>
</body>
</html>
```

- [ ] **Step 1.5: 创建 `frontend/env.d.ts`**

```typescript
/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}
```

- [ ] **Step 1.6: 创建 `frontend/src/App.vue`**

```vue
<script setup lang="ts">
</script>

<template>
  <router-view />
</template>
```

- [ ] **Step 1.7: 创建最小 `frontend/src/main.ts`（仅挂载 Vue，不含 router/store，本 task 不引入避免缺依赖报错）**

```typescript
import { createApp } from 'vue'
import App from './App.vue'

createApp(App).mount('#app')
```

- [ ] **Step 1.8: 安装依赖**

```bash
cd frontend
npm install --registry=https://registry.npmmirror.com
```

预期：生成 `node_modules/` 和 `package-lock.json`，无错误。

- [ ] **Step 1.9: 验证 dev server 启动（暂无 router 会显示空白页但无报错）**

```bash
npm run dev
```

预期：输出 `Local: http://localhost:5173/`，浏览器访问看到空白页（只有 `<div id="app"></div>`），控制台无报错。按 `Ctrl+C` 退出。

- [ ] **Step 1.10: 提交**

```bash
cd ..
git add frontend/package.json frontend/package-lock.json frontend/.gitignore frontend/index.html frontend/env.d.ts frontend/src/main.ts frontend/src/App.vue
git commit -m "chore(fe): scaffold Vite + Vue3 + TypeScript project"
```

---

### Task 2: TypeScript 与 Vite 配置

**Files:**
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/vite.config.ts`

- [ ] **Step 2.1: 创建 `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "module": "ESNext",
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "preserve",
    "strict": true,
    "noUnusedLocals": false,
    "noUnusedParameters": false,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    }
  },
  "include": ["src/**/*.ts", "src/**/*.d.ts", "src/**/*.vue", "env.d.ts"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

- [ ] **Step 2.2: 创建 `frontend/tsconfig.node.json`**

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 2.3: 创建 `frontend/vite.config.ts`**

```typescript
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/healthz': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
```

- [ ] **Step 2.4: 验证 TypeScript 编译通过**

```bash
cd frontend
npx vue-tsc --noEmit
```

预期：无输出（无类型错误），exit code 0。

- [ ] **Step 2.5: 验证 dev server 仍能启动**

```bash
npm run dev
```

预期：`Local: http://localhost:5173/`，浏览器访问无报错。`Ctrl+C` 退出。

- [ ] **Step 2.6: 提交**

```bash
cd ..
git add frontend/tsconfig.json frontend/tsconfig.node.json frontend/vite.config.ts
git commit -m "chore(fe): add TypeScript and Vite configuration"
```

---

### Task 3: API 类型定义与 axios client

**Files:**
- Create: `frontend/src/types/index.ts`
- Create: `frontend/src/api/client.ts`

- [ ] **Step 3.1: 创建 `frontend/src/types/index.ts`（与后端 `backend/app/schemas.py` 字段对齐）**

```typescript
// 与后端 app/schemas.py 对齐的接口类型

export interface TaskOut {
  id: number
  source: string
  raw_input: string
  share_url: string
  share_code: string | null
  status: 'pending' | 'running' | 'done' | 'failed' | 'skipped'
  category: string | null
  target_path: string | null
  error_msg: string | null
  retry_count: number
  created_at: number
  started_at: number | null
  finished_at: number | null
}

export interface TaskCreate {
  raw_input: string
}

export interface TaskCategoryUpdate {
  category: string
  target_path_override: string | null
}

export type HistoryOut = TaskOut

export interface QRStartResp {
  qrcode_url: string
  state: string
}

export interface QRStatusResp {
  state: string
  message: string
}

export interface AuthCheckResp {
  logged_in: boolean
}

export interface ConfigOut {
  tmdb_api_key: string
  tmdb_language: string
  feishu_app_id: string
  feishu_app_token: string
  feishu_table_id: string
  feishu_link_column: string
  feishu_code_column: string
  feishu_remark_column: string
  feishu_poll_interval_minutes: number
  telegram_allowed_chat_ids: number[]
  telegram_allowed_user_ids: number[]
}

export interface ConfigUpdate {
  tmdb_api_key?: string
  tmdb_language?: string
  feishu_app_id?: string
  feishu_app_secret?: string
  feishu_app_token?: string
  feishu_table_id?: string
  feishu_link_column?: string
  feishu_code_column?: string
  feishu_remark_column?: string
  feishu_poll_interval_minutes?: number
  telegram_allowed_chat_ids?: number[]
  telegram_allowed_user_ids?: number[]
}

export interface FeishuTestResp {
  ok: boolean
  message: string
}

export interface DirRoot {
  name: string
  cid: number
}

export interface DirNode {
  name: string
  cid: number
  is_dir: boolean
}

export interface TaskStreamEvent {
  task_id: number
  status: string
  target_path?: string
  error?: string
}
```

- [ ] **Step 3.2: 创建 `frontend/src/api/client.ts`**

```typescript
import axios, { AxiosError, type AxiosInstance } from 'axios'
import { ElMessage } from 'element-plus'

const TOKEN_KEY = '115_token'

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) || ''
}

export function setToken(token: string): void {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token)
  } else {
    localStorage.removeItem(TOKEN_KEY)
  }
}

const client: AxiosInstance = axios.create({
  baseURL: '/',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// 请求拦截器：自动注入 Bearer Token
client.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器：401 清空 token 并跳转登录页
client.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    const status = error.response?.status
    if (status === 401) {
      // 排除 /api/auth/check 本身（用于启动时检查登录态）
      const url = error.config?.url || ''
      if (!url.includes('/api/auth/check') && !url.includes('/api/auth/qrcode')) {
        setToken('')
        ElMessage.error('登录已失效或未授权，请重新登录')
        // 避免在登录页本身循环跳转
        if (window.location.pathname !== '/login') {
          window.location.href = '/login'
        }
      }
    }
    return Promise.reject(error)
  },
)

export default client
```

- [ ] **Step 3.3: 验证 TS 编译**

```bash
cd frontend
npx vue-tsc --noEmit
```

预期：无输出，exit code 0。

- [ ] **Step 3.4: 提交**

```bash
cd ..
git add frontend/src/types/index.ts frontend/src/api/client.ts
git commit -m "feat(fe): add shared types and axios client with token interceptor"
```

---

### Task 4: API 接口模块（5 个业务域）

**Files:**
- Create: `frontend/src/api/auth.ts`
- Create: `frontend/src/api/tasks.ts`
- Create: `frontend/src/api/history.ts`
- Create: `frontend/src/api/dirs.ts`
- Create: `frontend/src/api/config.ts`

- [ ] **Step 4.1: 创建 `frontend/src/api/auth.ts`**

```typescript
import client from './client'
import type { AuthCheckResp, QRStartResp, QRStatusResp } from '@/types'

export const authApi = {
  check(): Promise<AuthCheckResp> {
    return client.get('/api/auth/check').then((r) => r.data)
  },
  startQrcode(): Promise<QRStartResp> {
    return client.post('/api/auth/qrcode').then((r) => r.data)
  },
  pollQrcodeStatus(): Promise<QRStatusResp> {
    return client.get('/api/auth/qrcode/status').then((r) => r.data)
  },
  logout(): Promise<{ ok: boolean }> {
    return client.post('/api/auth/logout').then((r) => r.data)
  },
}
```

- [ ] **Step 4.2: 创建 `frontend/src/api/tasks.ts`**

```typescript
import client from './client'
import type { TaskCreate, TaskCategoryUpdate, TaskOut } from '@/types'

export const tasksApi = {
  create(body: TaskCreate): Promise<TaskOut> {
    return client.post('/api/tasks', body).then((r) => r.data)
  },
  list(params?: {
    status?: string[]
    limit?: number
    offset?: number
  }): Promise<TaskOut[]> {
    return client.get('/api/tasks', { params }).then((r) => r.data)
  },
  get(taskId: number): Promise<TaskOut> {
    return client.get(`/api/tasks/${taskId}`).then((r) => r.data)
  },
  retry(taskId: number): Promise<TaskOut> {
    return client.post(`/api/tasks/${taskId}/retry`).then((r) => r.data)
  },
  updateCategory(
    taskId: number,
    body: TaskCategoryUpdate,
  ): Promise<TaskOut> {
    return client
      .put(`/api/tasks/${taskId}/category`, body)
      .then((r) => r.data)
  },
}
```

- [ ] **Step 4.3: 创建 `frontend/src/api/history.ts`**

```typescript
import client from './client'
import type { HistoryOut } from '@/types'

export const historyApi = {
  list(params?: {
    q?: string
    category?: string
    limit?: number
    offset?: number
  }): Promise<HistoryOut[]> {
    return client.get('/api/history', { params }).then((r) => r.data)
  },
  delete(taskId: number): Promise<{ ok: boolean }> {
    return client.delete(`/api/history/${taskId}`).then((r) => r.data)
  },
}
```

- [ ] **Step 4.4: 创建 `frontend/src/api/dirs.ts`**

```typescript
import client from './client'
import type { DirRoot, DirNode } from '@/types'

export const dirsApi = {
  roots(): Promise<{ roots: DirRoot[] }> {
    return client.get('/api/dirs/roots').then((r) => r.data)
  },
  browse(cid: number): Promise<{ items: DirNode[] }> {
    return client
      .get('/api/dirs/browse', { params: { cid } })
      .then((r) => r.data)
  },
}
```

- [ ] **Step 4.5: 创建 `frontend/src/api/config.ts`**

```typescript
import client from './client'
import type { ConfigOut, ConfigUpdate, FeishuTestResp } from '@/types'

export const configApi = {
  get(): Promise<ConfigOut> {
    return client.get('/api/config').then((r) => r.data)
  },
  update(body: ConfigUpdate): Promise<ConfigOut> {
    return client.put('/api/config', body).then((r) => r.data)
  },
  testFeishu(): Promise<FeishuTestResp> {
    return client.post('/api/config/feishu/test').then((r) => r.data)
  },
}
```

- [ ] **Step 4.6: 验证 TS 编译**

```bash
cd frontend
npx vue-tsc --noEmit
```

预期：无输出，exit code 0。

- [ ] **Step 4.7: 提交**

```bash
cd ..
git add frontend/src/api/auth.ts frontend/src/api/tasks.ts frontend/src/api/history.ts frontend/src/api/dirs.ts frontend/src/api/config.ts
git commit -m "feat(fe): add API modules for auth/tasks/history/dirs/config"
```

---

### Task 5: Pinia stores

**Files:**
- Create: `frontend/src/stores/auth.ts`
- Create: `frontend/src/stores/config.ts`

- [ ] **Step 5.1: 创建 `frontend/src/stores/auth.ts`**

```typescript
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { authApi } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const loggedIn = ref<boolean>(false)
  const checking = ref<boolean>(false)

  async function check(): Promise<boolean> {
    checking.value = true
    try {
      const resp = await authApi.check()
      loggedIn.value = resp.logged_in
      return resp.logged_in
    } catch {
      loggedIn.value = false
      return false
    } finally {
      checking.value = false
    }
  }

  function setLoggedIn(v: boolean) {
    loggedIn.value = v
  }

  async function logout(): Promise<void> {
    try {
      await authApi.logout()
    } finally {
      loggedIn.value = false
    }
  }

  return { loggedIn, checking, check, setLoggedIn, logout }
})
```

- [ ] **Step 5.2: 创建 `frontend/src/stores/config.ts`**

```typescript
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { configApi } from '@/api/config'
import type { ConfigOut } from '@/types'

export const useConfigStore = defineStore('config', () => {
  const data = ref<ConfigOut | null>(null)
  const loading = ref<boolean>(false)

  async function fetch(): Promise<ConfigOut> {
    loading.value = true
    try {
      const resp = await configApi.get()
      data.value = resp
      return resp
    } finally {
      loading.value = false
    }
  }

  async function save(patch: Partial<ConfigOut>): Promise<ConfigOut> {
    const resp = await configApi.update(patch)
    data.value = resp
    return resp
  }

  return { data, loading, fetch, save }
})
```

- [ ] **Step 5.3: 验证 TS 编译**

```bash
cd frontend
npx vue-tsc --noEmit
```

预期：无输出，exit code 0。

- [ ] **Step 5.4: 提交**

```bash
cd ..
git add frontend/src/stores/auth.ts frontend/src/stores/config.ts
git commit -m "feat(fe): add Pinia stores for auth and config"
```

---

### Task 6: 路由 + 主布局 + 应用入口装配

**Files:**
- Create: `frontend/src/router/index.ts`
- Create: `frontend/src/components/AppLayout.vue`
- Create: `frontend/src/styles/main.css`
- Create: `frontend/src/views/PlaceholderView.vue`（占位，后续 task 替换）
- Modify: `frontend/src/main.ts`（挂载 router + pinia + element-plus）

- [ ] **Step 6.1: 创建 `frontend/src/router/index.ts`**

```typescript
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

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
```

- [ ] **Step 6.2: 创建 5 个 view 的占位文件**

`frontend/src/views/LoginView.vue`:
```vue
<script setup lang="ts"></script>
<template>
  <div>LoginView placeholder</div>
</template>
```

`frontend/src/views/TasksView.vue`:
```vue
<script setup lang="ts"></script>
<template>
  <div>TasksView placeholder</div>
</template>
```

`frontend/src/views/HistoryView.vue`:
```vue
<script setup lang="ts"></script>
<template>
  <div>HistoryView placeholder</div>
</template>
```

`frontend/src/views/ConfigView.vue`:
```vue
<script setup lang="ts"></script>
<template>
  <div>ConfigView placeholder</div>
</template>
```

`frontend/src/views/BrowserView.vue`:
```vue
<script setup lang="ts"></script>
<template>
  <div>BrowserView placeholder</div>
</template>
```

- [ ] **Step 6.3: 创建 `frontend/src/styles/main.css`**

```css
html,
body,
#app {
  margin: 0;
  padding: 0;
  height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
    'Helvetica Neue', Arial, 'PingFang SC', 'Hiragino Sans GB',
    'Microsoft YaHei', sans-serif;
}

.app-container {
  height: 100vh;
}

.app-aside {
  background-color: #304156;
  color: #bfcbd9;
}

.app-aside .el-menu {
  background-color: transparent;
  border-right: none;
}

.app-main {
  padding: 20px;
  background-color: #f0f2f5;
  overflow-y: auto;
}

.app-header {
  background-color: #fff;
  border-bottom: 1px solid #e6e6e6;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  height: 60px;
}
```

- [ ] **Step 6.4: 创建 `frontend/src/components/AppLayout.vue`**

```vue
<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const activeMenu = computed(() => route.name as string)

async function handleLogout() {
  await auth.logout()
  router.push('/login')
}

function go(name: string) {
  router.push({ name })
}
</script>

<template>
  <el-container class="app-container">
    <el-aside width="200px" class="app-aside">
      <div
        style="
          height: 60px;
          line-height: 60px;
          text-align: center;
          color: #fff;
          font-size: 18px;
          font-weight: bold;
        "
      >
        115 自动转存
      </div>
      <el-menu
        :default-active="activeMenu"
        background-color="transparent"
        text-color="#bfcbd9"
        active-text-color="#409eff"
        @select="go"
      >
        <el-menu-item index="tasks">
          <el-icon><Document /></el-icon>
          <span>任务</span>
        </el-menu-item>
        <el-menu-item index="history">
          <el-icon><Clock /></el-icon>
          <span>历史</span>
        </el-menu-item>
        <el-menu-item index="browser">
          <el-icon><FolderOpened /></el-icon>
          <span>网盘浏览</span>
        </el-menu-item>
        <el-menu-item index="config">
          <el-icon><Setting /></el-icon>
          <span>配置</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="app-header">
        <div></div>
        <div>
          <el-tag v-if="auth.loggedIn" type="success" size="small">已登录</el-tag>
          <el-tag v-else type="warning" size="small">未登录</el-tag>
          <el-button
            type="text"
            style="margin-left: 16px; color: #f56c6c"
            @click="handleLogout"
          >
            退出
          </el-button>
        </div>
      </el-header>
      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script lang="ts">
import { Document, Clock, FolderOpened, Setting } from '@element-plus/icons-vue'
export default { components: { Document, Clock, FolderOpened, Setting } }
</script>
```

- [ ] **Step 6.5: 修改 `frontend/src/App.vue`（根据路由 meta 决定是否套布局）**

```vue
<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppLayout from '@/components/AppLayout.vue'

const route = useRoute()
const isBlank = computed(() => route.meta.layout === 'blank')
</script>

<template>
  <AppLayout v-if="!isBlank" />
  <router-view v-else />
</template>
```

- [ ] **Step 6.6: 修改 `frontend/src/main.ts`（挂载 router + pinia + element-plus + 图标 + 样式）**

```typescript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import App from './App.vue'
import { router } from './router'
import './styles/main.css'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(ElementPlus)

// 注册所有 Element Plus 图标为全局组件
for (const [name, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(name, component)
}

app.mount('#app')
```

- [ ] **Step 6.7: 安装 Element Plus 图标包**

修改 `frontend/package.json`，在 `dependencies` 中添加：
```json
"@element-plus/icons-vue": "^2.3.1"
```

完整更新后的 `frontend/package.json` `dependencies` 部分：
```json
"dependencies": {
  "@element-plus/icons-vue": "^2.3.1",
  "axios": "^1.7.7",
  "element-plus": "^2.8.5",
  "pinia": "^2.2.4",
  "vue": "^3.5.12",
  "vue-router": "^4.4.5"
}
```

执行：
```bash
cd frontend
npm install @element-plus/icons-vue@^2.3.1 --registry=https://registry.npmmirror.com
```

- [ ] **Step 6.8: 验证 TS 编译**

```bash
npx vue-tsc --noEmit
```

预期：无输出，exit code 0。

- [ ] **Step 6.9: 启动 dev server 端到端验证**

```bash
npm run dev
```

预期：
- 浏览器访问 `http://localhost:5173/` 自动跳转到 `/tasks`
- 显示左侧菜单（任务/历史/网盘浏览/配置）和右侧 placeholder 内容
- 切换菜单（点"历史"/"配置"/"网盘浏览"）显示对应 placeholder
- 浏览器控制台无报错（含 axios 请求会失败，因为后端未启动，但应被静默吞掉或显示网络错误，不阻塞页面渲染）

`Ctrl+C` 退出。

- [ ] **Step 6.10: 提交**

```bash
cd ..
git add frontend/src/router/ frontend/src/components/ frontend/src/styles/ frontend/src/views/ frontend/src/App.vue frontend/src/main.ts frontend/package.json frontend/package-lock.json
git commit -m "feat(fe): wire up router, layout, element-plus, and 5 view placeholders"
```

---

### Task 7: LoginView（扫码登录）

**Files:**
- Modify: `frontend/src/views/LoginView.vue`

- [ ] **Step 7.1: 实现 LoginView**

替换 `frontend/src/views/LoginView.vue` 全部内容：

```vue
<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { authApi } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const qrcodeUrl = ref<string>('')
const state = ref<string>('idle') // idle | waiting | success | error
const message = ref<string>('正在获取二维码…')
let pollTimer: number | null = null

async function fetchQrcode() {
  state.value = 'idle'
  message.value = '正在获取二维码…'
  qrcodeUrl.value = ''
  try {
    const resp = await authApi.startQrcode()
    if (resp.state !== 'waiting' || !resp.qrcode_url) {
      state.value = 'error'
      message.value = '获取二维码失败，请重试'
      return
    }
    qrcodeUrl.value = resp.qrcode_url
    state.value = 'waiting'
    message.value = '请使用 115 手机 App 扫描二维码'
    startPolling()
  } catch (e: any) {
    state.value = 'error'
    message.value = `获取二维码失败：${e.response?.data?.detail || e.message}`
  }
}

function startPolling() {
  stopPolling()
  pollTimer = window.setInterval(pollOnce, 1500)
}

function stopPolling() {
  if (pollTimer !== null) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function pollOnce() {
  try {
    const resp = await authApi.pollQrcodeStatus()
    if (resp.state === 'success' || resp.state === 'logged_in') {
      stopPolling()
      state.value = 'success'
      message.value = '登录成功，正在跳转…'
      auth.setLoggedIn(true)
      setTimeout(() => router.push('/tasks'), 800)
    } else if (resp.state === 'expired' || resp.state === 'cancel') {
      stopPolling()
      state.value = 'error'
      message.value = resp.message || '二维码已失效，请重新获取'
    } else if (resp.state === 'scaned') {
      message.value = '已扫描，请在手机上确认'
    } else {
      message.value = resp.message || '等待扫描…'
    }
  } catch (e: any) {
    // 单次轮询失败不终止循环
    console.warn('poll status failed', e)
  }
}

onMounted(() => {
  // 启动前先检查是否已登录
  auth.check().then((ok) => {
    if (ok) {
      router.push('/tasks')
    } else {
      fetchQrcode()
    }
  })
})

onUnmounted(() => {
  stopPolling()
})
</script>

<template>
  <div
    style="
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      background: #f0f2f5;
    "
  >
    <el-card style="width: 400px; text-align: center">
      <h2 style="margin-top: 0">115 扫码登录</h2>
      <div
        style="
          height: 280px;
          display: flex;
          align-items: center;
          justify-content: center;
          background: #fafafa;
          margin: 16px 0;
        "
      >
        <el-image
          v-if="qrcodeUrl"
          :src="qrcodeUrl"
          style="width: 240px; height: 240px"
          fit="contain"
        />
        <el-icon v-else :size="60" color="#909399"><Loading /></el-icon>
      </div>
      <div
        :style="{
          color:
            state === 'success'
              ? '#67c23a'
              : state === 'error'
                ? '#f56c6c'
                : '#606266',
          marginBottom: '16px',
        }"
      >
        {{ message }}
      </div>
      <el-button
        v-if="state === 'error' || state === 'waiting'"
        type="primary"
        @click="fetchQrcode"
      >
        重新获取二维码
      </el-button>
    </el-card>
  </div>
</template>
```

- [ ] **Step 7.2: 验证 TS 编译**

```bash
cd frontend
npx vue-tsc --noEmit
```

预期：无输出。

- [ ] **Step 7.3: 端到端验证（需要后端运行）**

启动后端（在另一个终端）：
```bash
cd backend
ENCRYPTION_KEY=$(python -c "import secrets,base64;print(base64.b64encode(secrets.token_bytes(32)).decode())") uvicorn app.main:app --port 8000
```

启动前端：
```bash
cd frontend
npm run dev
```

浏览器访问 `http://localhost:5173/login`：
- 看到"115 扫码登录"卡片
- 看到"获取二维码失败"或显示二维码（取决于 115 接口可用性）
- 控制台无未捕获错误

`Ctrl+C` 退出前后端。

- [ ] **Step 7.4: 提交**

```bash
cd ..
git add frontend/src/views/LoginView.vue
git commit -m "feat(fe): implement LoginView with QR code polling"
```

---

### Task 8: TasksView（任务列表 + 提交 + SSE）

**Files:**
- Modify: `frontend/src/views/TasksView.vue`

- [ ] **Step 8.1: 实现 TasksView**

替换 `frontend/src/views/TasksView.vue` 全部内容：

```vue
<script setup lang="ts">
import { onMounted, onUnmounted, ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { tasksApi } from '@/api/tasks'
import type { TaskOut } from '@/types'

const tasks = ref<TaskOut[]>([])
const loading = ref<boolean>(false)
const submitInput = ref<string>('')
const submitting = ref<boolean>(false)
const filterStatus = ref<string[]>([])
const pollTimer = ref<number | null>(null)
let evtSource: EventSource | null = null

const statusOptions = [
  { label: '全部', value: '' },
  { label: '待处理', value: 'pending' },
  { label: '处理中', value: 'running' },
  { label: '已完成', value: 'done' },
  { label: '已失败', value: 'failed' },
  { label: '已跳过', value: 'skipped' },
]

const filteredTasks = computed(() => {
  if (filterStatus.value.length === 0) return tasks.value
  return tasks.value.filter((t) => filterStatus.value.includes(t.status))
})

async function fetchTasks() {
  loading.value = true
  try {
    tasks.value = await tasksApi.list({ limit: 100 })
  } catch (e: any) {
    ElMessage.error(`加载任务列表失败：${e.message}`)
  } finally {
    loading.value = false
  }
}

async function submit() {
  const raw = submitInput.value.trim()
  if (!raw) {
    ElMessage.warning('请粘贴 115 分享链接')
    return
  }
  submitting.value = true
  try {
    const t = await tasksApi.create({ raw_input: raw })
    ElMessage.success(`任务 #${t.id} 已创建`)
    submitInput.value = ''
    await fetchTasks()
  } catch (e: any) {
    const detail = e.response?.data?.detail || e.message
    ElMessage.error(`创建失败：${detail}`)
  } finally {
    submitting.value = false
  }
}

async function retry(taskId: number) {
  try {
    await tasksApi.retry(taskId)
    ElMessage.success(`任务 #${taskId} 已重新入队`)
    await fetchTasks()
  } catch (e: any) {
    ElMessage.error(`重试失败：${e.message}`)
  }
}

async function editCategory(t: TaskOut) {
  try {
    const { value: category } = await ElMessageBox.prompt(
      '请输入新分类（电影/电视剧/动漫/综艺/学习/_未分类）',
      `修正任务 #${t.id} 分类`,
      {
        inputValue: t.category || '',
        inputPattern: /.+/,
        inputErrorMessage: '分类不能为空',
      },
    )
    const { value: path } = await ElMessageBox.prompt(
      '目标路径覆盖（可留空使用默认）',
      '目标路径',
      { inputValue: t.target_path || '', inputErrorMessage: '' },
    ).catch(() => ({ value: '' }))
    await tasksApi.updateCategory(t.id, {
      category,
      target_path_override: path || null,
    })
    ElMessage.success('已修正分类并重新入队')
    await fetchTasks()
  } catch (e: any) {
    if (e === 'cancel') return
    ElMessage.error(`修正失败：${e.message}`)
  }
}

function statusTagType(s: TaskOut['status']) {
  return {
    pending: 'info',
    running: 'warning',
    done: 'success',
    failed: 'danger',
    skipped: 'info',
  }[s]
}

function formatTime(ts: number | null): string {
  if (!ts) return '-'
  return new Date(ts * 1000).toLocaleString('zh-CN')
}

function startSSE() {
  if (evtSource) evtSource.close()
  evtSource = new EventSource('/api/tasks/stream')
  evtSource.addEventListener('task', (e: MessageEvent) => {
    try {
      const evt = JSON.parse(e.data)
      // 收到事件后刷新列表（简单策略）
      fetchTasks()
      if (evt.status === 'done') {
        ElMessage.success(`任务 #${evt.task_id} 已完成`)
      } else if (evt.status === 'failed') {
        ElMessage.error(`任务 #${evt.task_id} 失败：${evt.error || ''}`)
      } else if (evt.status === 'auth_expired') {
        ElMessage.warning('115 登录已失效，请重新扫码')
      }
    } catch (err) {
      console.warn('parse SSE event failed', err)
    }
  })
  evtSource.onerror = () => {
    // SSE 断开后自动重连由浏览器处理；这里仅记录
    console.warn('SSE connection error')
  }
}

function stopSSE() {
  if (evtSource) {
    evtSource.close()
    evtSource = null
  }
}

function startPollingFallback() {
  // 兜底：每 10s 拉一次列表，避免 SSE 偶发断开导致页面不更新
  pollTimer.value = window.setInterval(fetchTasks, 10000)
}

function stopPollingFallback() {
  if (pollTimer.value !== null) {
    clearInterval(pollTimer.value)
    pollTimer.value = null
  }
}

onMounted(() => {
  fetchTasks()
  startSSE()
  startPollingFallback()
})

onUnmounted(() => {
  stopSSE()
  stopPollingFallback()
})
</script>

<template>
  <div>
    <el-card style="margin-bottom: 16px">
      <h3 style="margin-top: 0">提交任务</h3>
      <el-input
        v-model="submitInput"
        type="textarea"
        :rows="3"
        placeholder="粘贴 115 分享链接，例如：https://115.com/s/abc123?password=xyz"
      />
      <div style="margin-top: 12px; text-align: right">
        <el-button type="primary" :loading="submitting" @click="submit">
          提交
        </el-button>
      </div>
    </el-card>

    <el-card>
      <div
        style="
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 12px;
        "
      >
        <h3 style="margin: 0">任务列表</h3>
        <el-select
          v-model="filterStatus"
          multiple
          collapse-tags
          placeholder="筛选状态"
          style="width: 240px"
          @change="fetchTasks"
        >
          <el-option
            v-for="opt in statusOptions.filter((o) => o.value)"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
      </div>
      <el-table
        :data="filteredTasks"
        v-loading="loading"
        style="width: 100%"
        empty-text="暂无任务"
      >
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="category" label="分类" width="100" />
        <el-table-column
          prop="share_url"
          label="分享链接"
          show-overflow-tooltip
        />
        <el-table-column
          prop="target_path"
          label="目标路径"
          show-overflow-tooltip
        />
        <el-table-column label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column
          prop="error_msg"
          label="错误信息"
          show-overflow-tooltip
        />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'failed'"
              type="text"
              size="small"
              @click="retry(row.id)"
            >
              重试
            </el-button>
            <el-button
              v-if="row.status === 'failed' || row.status === 'done'"
              type="text"
              size="small"
              @click="editCategory(row)"
            >
              修正分类
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>
```

- [ ] **Step 8.2: 验证 TS 编译**

```bash
cd frontend
npx vue-tsc --noEmit
```

预期：无输出。

- [ ] **Step 8.3: 端到端验证**

启动后端（一个终端）：
```bash
cd backend
ENCRYPTION_KEY=$(python -c "import secrets,base64;print(base64.b64encode(secrets.token_bytes(32)).decode())") uvicorn app.main:app --port 8000
```

启动前端（另一个终端）：
```bash
cd frontend
npm run dev
```

浏览器访问 `http://localhost:5173/tasks`：
- 看到提交表单和空的任务列表
- 提交无效链接（如 "no link"）→ 看到 400 错误提示
- 提交有效链接（如 `https://115.com/s/abc?password=x`）→ 看到"任务 #N 已创建"成功提示
- 任务列表自动刷新显示新任务
- 点击"修正分类"按钮能看到对话框

`Ctrl+C` 退出前后端。

- [ ] **Step 8.4: 提交**

```bash
cd ..
git add frontend/src/views/TasksView.vue
git commit -m "feat(fe): implement TasksView with submit, list, SSE, retry, category edit"
```

---

### Task 9: HistoryView（历史搜索 + 删除）

**Files:**
- Modify: `frontend/src/views/HistoryView.vue`

- [ ] **Step 9.1: 实现 HistoryView**

替换 `frontend/src/views/HistoryView.vue` 全部内容：

```vue
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { historyApi } from '@/api/history'
import type { HistoryOut } from '@/types'

const items = ref<HistoryOut[]>([])
const loading = ref<boolean>(false)
const query = ref<string>('')
const category = ref<string>('')

async function fetchHistory() {
  loading.value = true
  try {
    items.value = await historyApi.list({
      q: query.value || undefined,
      category: category.value || undefined,
      limit: 100,
    })
  } catch (e: any) {
    ElMessage.error(`加载历史失败：${e.message}`)
  } finally {
    loading.value = false
  }
}

async function deleteItem(id: number) {
  try {
    await ElMessageBox.confirm(
      `确定删除历史记录 #${id}？此操作不可恢复。`,
      '确认删除',
      { type: 'warning' },
    )
    await historyApi.delete(id)
    ElMessage.success('已删除')
    await fetchHistory()
  } catch (e: any) {
    if (e === 'cancel') return
    ElMessage.error(`删除失败：${e.message}`)
  }
}

function statusTagType(s: HistoryOut['status']) {
  return {
    done: 'success',
    failed: 'danger',
    skipped: 'info',
    pending: 'info',
    running: 'warning',
  }[s]
}

function formatTime(ts: number | null): string {
  if (!ts) return '-'
  return new Date(ts * 1000).toLocaleString('zh-CN')
}

onMounted(() => {
  fetchHistory()
})
</script>

<template>
  <el-card>
    <div
      style="
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;
      "
    >
      <h3 style="margin: 0">转存历史</h3>
      <div style="display: flex; gap: 8px">
        <el-input
          v-model="query"
          placeholder="搜索链接/路径"
          clearable
          style="width: 240px"
          @keyup.enter="fetchHistory"
          @clear="fetchHistory"
        />
        <el-input
          v-model="category"
          placeholder="分类"
          clearable
          style="width: 120px"
          @keyup.enter="fetchHistory"
          @clear="fetchHistory"
        />
        <el-button type="primary" @click="fetchHistory">搜索</el-button>
      </div>
    </div>
    <el-table
      :data="items"
      v-loading="loading"
      style="width: 100%"
      empty-text="暂无历史记录"
    >
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.status)" size="small">
            {{ row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="category" label="分类" width="100" />
      <el-table-column
        prop="share_url"
        label="分享链接"
        show-overflow-tooltip
      />
      <el-table-column
        prop="target_path"
        label="目标路径"
        show-overflow-tooltip
      />
      <el-table-column label="完成时间" width="180">
        <template #default="{ row }">
          {{ formatTime(row.finished_at) }}
        </template>
      </el-table-column>
      <el-table-column
        prop="error_msg"
        label="错误信息"
        show-overflow-tooltip
      />
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button
            type="text"
            size="small"
            style="color: #f56c6c"
            @click="deleteItem(row.id)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>
```

- [ ] **Step 9.2: 验证 TS 编译**

```bash
cd frontend
npx vue-tsc --noEmit
```

预期：无输出。

- [ ] **Step 9.3: 端到端验证**

启动后端 + 前端（同 Task 8 步骤），浏览器访问 `http://localhost:5173/history`：
- 看到"暂无历史记录"（如果之前没完成过任务）
- 或看到已完成/失败的任务列表
- 搜索框输入关键词后回车能过滤
- 删除按钮弹出确认对话框，确认后看到"已删除"

`Ctrl+C` 退出。

- [ ] **Step 9.4: 提交**

```bash
cd ..
git add frontend/src/views/HistoryView.vue
git commit -m "feat(fe): implement HistoryView with search and delete"
```

---

### Task 10: ConfigView（配置查看 + 编辑 + 飞书测试）

**Files:**
- Modify: `frontend/src/views/ConfigView.vue`

- [ ] **Step 10.1: 实现 ConfigView**

替换 `frontend/src/views/ConfigView.vue` 全部内容：

```vue
<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useConfigStore } from '@/stores/config'
import { configApi } from '@/api/config'

const store = useConfigStore()
const saving = ref<boolean>(false)
const testing = ref<boolean>(false)

const form = reactive({
  tmdb_api_key: '',
  tmdb_language: 'zh-CN',
  feishu_app_id: '',
  feishu_app_secret: '',
  feishu_app_token: '',
  feishu_table_id: '',
  feishu_link_column: '链接',
  feishu_code_column: '提取码',
  feishu_remark_column: '备注',
  feishu_poll_interval_minutes: 5,
  telegram_allowed_chat_ids: '' as string | number[],
  telegram_allowed_user_ids: '' as string | number[],
})

function parseIds(v: string | number[]): number[] {
  if (Array.isArray(v)) return v
  if (!v) return []
  return v
    .split(/[,，\s]+/)
    .map((s) => Number(s.trim()))
    .filter((n) => !Number.isNaN(n))
}

function idsToString(v: number[]): string {
  return v.join(', ')
}

async function load() {
  try {
    const c = await store.fetch()
    form.tmdb_api_key = ''
    form.tmdb_language = c.tmdb_language || 'zh-CN'
    form.feishu_app_id = ''
    form.feishu_app_secret = ''
    form.feishu_app_token = ''
    form.feishu_table_id = c.feishu_table_id || ''
    form.feishu_link_column = c.feishu_link_column || '链接'
    form.feishu_code_column = c.feishu_code_column || '提取码'
    form.feishu_remark_column = c.feishu_remark_column || '备注'
    form.feishu_poll_interval_minutes = c.feishu_poll_interval_minutes || 5
    form.telegram_allowed_chat_ids = idsToString(
      c.telegram_allowed_chat_ids || [],
    )
    form.telegram_allowed_user_ids = idsToString(
      c.telegram_allowed_user_ids || [],
    )
  } catch (e: any) {
    ElMessage.error(`加载配置失败：${e.message}`)
  }
}

async function save() {
  saving.value = true
  try {
    const patch: Record<string, any> = {}
    if (form.tmdb_api_key) patch.tmdb_api_key = form.tmdb_api_key
    if (form.tmdb_language) patch.tmdb_language = form.tmdb_language
    if (form.feishu_app_id) patch.feishu_app_id = form.feishu_app_id
    if (form.feishu_app_secret) patch.feishu_app_secret = form.feishu_app_secret
    if (form.feishu_app_token) patch.feishu_app_token = form.feishu_app_token
    if (form.feishu_table_id) patch.feishu_table_id = form.feishu_table_id
    if (form.feishu_link_column) patch.feishu_link_column = form.feishu_link_column
    if (form.feishu_code_column) patch.feishu_code_column = form.feishu_code_column
    if (form.feishu_remark_column) patch.feishu_remark_column = form.feishu_remark_column
    patch.feishu_poll_interval_minutes = Number(form.feishu_poll_interval_minutes)
    patch.telegram_allowed_chat_ids = parseIds(form.telegram_allowed_chat_ids)
    patch.telegram_allowed_user_ids = parseIds(form.telegram_allowed_user_ids)
    await store.save(patch)
    ElMessage.success('已保存到 .env.override，需重启服务生效')
    // 清空敏感字段，避免下次保存重复写入
    form.tmdb_api_key = ''
    form.feishu_app_id = ''
    form.feishu_app_secret = ''
    form.feishu_app_token = ''
  } catch (e: any) {
    ElMessage.error(`保存失败：${e.message}`)
  } finally {
    saving.value = false
  }
}

async function testFeishu() {
  testing.value = true
  try {
    const resp = await configApi.testFeishu()
    if (resp.ok) {
      ElMessage.success(resp.message || '飞书连通正常')
    } else {
      ElMessage.warning(resp.message || '飞书测试失败')
    }
  } catch (e: any) {
    ElMessage.error(`测试失败：${e.message}`)
  } finally {
    testing.value = false
  }
}

onMounted(() => {
  load()
})
</script>

<template>
  <div>
    <el-card style="margin-bottom: 16px">
      <div
        style="
          display: flex;
          justify-content: space-between;
          align-items: center;
        "
      >
        <h3 style="margin: 0">当前配置（脱敏显示）</h3>
        <el-button @click="load">刷新</el-button>
      </div>
      <el-descriptions
        v-if="store.data"
        :column="2"
        border
        style="margin-top: 12px"
      >
        <el-descriptions-item label="TMDB API Key">
          {{ store.data.tmdb_api_key || '（未配置）' }}
        </el-descriptions-item>
        <el-descriptions-item label="TMDB Language">
          {{ store.data.tmdb_language }}
        </el-descriptions-item>
        <el-descriptions-item label="飞书 App ID">
          {{ store.data.feishu_app_id || '（未配置）' }}
        </el-descriptions-item>
        <el-descriptions-item label="飞书 App Token">
          {{ store.data.feishu_app_token || '（未配置）' }}
        </el-descriptions-item>
        <el-descriptions-item label="飞书表格 ID">
          {{ store.data.feishu_table_id || '（未配置）' }}
        </el-descriptions-item>
        <el-descriptions-item label="飞书轮询间隔（分钟）">
          {{ store.data.feishu_poll_interval_minutes }}
        </el-descriptions-item>
        <el-descriptions-item label="TG 允许的 chat_id">
          {{ (store.data.telegram_allowed_chat_ids || []).join(', ') || '（未配置）' }}
        </el-descriptions-item>
        <el-descriptions-item label="TG 允许的 user_id">
          {{ (store.data.telegram_allowed_user_ids || []).join(', ') || '（未配置）' }}
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card>
      <h3 style="margin-top: 0">更新配置</h3>
      <el-form :model="form" label-width="200px">
        <el-divider content-position="left">TMDB</el-divider>
        <el-form-item label="TMDB API Key">
          <el-input
            v-model="form.tmdb_api_key"
            placeholder="留空表示不修改"
            show-password
          />
        </el-form-item>
        <el-form-item label="TMDB Language">
          <el-input v-model="form.tmdb_language" />
        </el-form-item>

        <el-divider content-position="left">飞书</el-divider>
        <el-form-item label="App ID">
          <el-input v-model="form.feishu_app_id" placeholder="留空表示不修改" />
        </el-form-item>
        <el-form-item label="App Secret">
          <el-input
            v-model="form.feishu_app_secret"
            placeholder="留空表示不修改"
            show-password
          />
        </el-form-item>
        <el-form-item label="App Token（表格 token）">
          <el-input v-model="form.feishu_app_token" placeholder="留空表示不修改" />
        </el-form-item>
        <el-form-item label="表格 ID">
          <el-input v-model="form.feishu_table_id" />
        </el-form-item>
        <el-form-item label="链接列名">
          <el-input v-model="form.feishu_link_column" />
        </el-form-item>
        <el-form-item label="提取码列名">
          <el-input v-model="form.feishu_code_column" />
        </el-form-item>
        <el-form-item label="备注列名">
          <el-input v-model="form.feishu_remark_column" />
        </el-form-item>
        <el-form-item label="轮询间隔（分钟）">
          <el-input-number
            v-model="form.feishu_poll_interval_minutes"
            :min="1"
            :max="60"
          />
        </el-form-item>

        <el-divider content-position="left">Telegram</el-divider>
        <el-form-item label="允许的 chat_id">
          <el-input
            v-model="form.telegram_allowed_chat_ids"
            placeholder="逗号分隔，例如：123456, -100987654"
          />
        </el-form-item>
        <el-form-item label="允许的 user_id">
          <el-input
            v-model="form.telegram_allowed_user_ids"
            placeholder="逗号分隔"
          />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="saving" @click="save">
            保存（写入 .env.override）
          </el-button>
          <el-button :loading="testing" @click="testFeishu">
            测试飞书连通
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>
```

- [ ] **Step 10.2: 验证 TS 编译**

```bash
cd frontend
npx vue-tsc --noEmit
```

预期：无输出。

- [ ] **Step 10.3: 端到端验证**

启动后端 + 前端，浏览器访问 `http://localhost:5173/config`：
- 上半部分显示当前配置（脱敏）
- 下半部分显示编辑表单
- 编辑某个字段（如 tmdb_language）后点"保存"→ 看到"已保存到 .env.override"提示
- 点"测试飞书连通"→ 看到 Plan B 提示信息

`Ctrl+C` 退出。

- [ ] **Step 10.4: 提交**

```bash
cd ..
git add frontend/src/views/ConfigView.vue
git commit -m "feat(fe): implement ConfigView with masked display and edit form"
```

---

### Task 11: BrowserView（115 目录浏览）

**Files:**
- Modify: `frontend/src/views/BrowserView.vue`

- [ ] **Step 11.1: 实现 BrowserView**

替换 `frontend/src/views/BrowserView.vue` 全部内容：

```vue
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { dirsApi } from '@/api/dirs'
import type { DirRoot, DirNode } from '@/types'

const roots = ref<DirRoot[]>([])
const currentItems = ref<DirNode[]>([])
const breadcrumb = ref<{ name: string; cid: number }[]>([])
const loading = ref<boolean>(false)
const error = ref<string>('')

async function fetchRoots() {
  loading.value = true
  error.value = ''
  try {
    const resp = await dirsApi.roots()
    roots.value = resp.roots || []
    if (roots.value.length > 0) {
      await browse(roots.value[0].cid, roots.value[0].name)
    }
  } catch (e: any) {
    const status = e.response?.status
    if (status === 401) {
      error.value = '未登录 115，请先到登录页扫码'
    } else {
      error.value = `加载根目录失败：${e.message}`
    }
  } finally {
    loading.value = false
  }
}

async function browse(cid: number, name?: string) {
  loading.value = true
  error.value = ''
  try {
    const resp = await dirsApi.browse(cid)
    currentItems.value = resp.items || []
    // 更新面包屑
    if (name !== undefined) {
      // 从根重新进入时重置
      const existingIdx = breadcrumb.value.findIndex((b) => b.cid === cid)
      if (existingIdx >= 0) {
        breadcrumb.value = breadcrumb.value.slice(0, existingIdx + 1)
      } else {
        // 检查是否是 roots 中的根
        const root = roots.value.find((r) => r.cid === cid)
        if (root) {
          breadcrumb.value = [{ name: root.name, cid: root.cid }]
        } else {
          breadcrumb.value.push({ name, cid })
        }
      }
    }
  } catch (e: any) {
    error.value = `浏览失败：${e.message}`
    currentItems.value = []
  } finally {
    loading.value = false
  }
}

function enterNode(node: DirNode) {
  if (!node.is_dir) return
  browse(node.cid, node.name)
}

function jumpTo(index: number) {
  const target = breadcrumb.value[index]
  if (target) browse(target.cid)
}

onMounted(() => {
  fetchRoots()
})
</script>

<template>
  <el-card>
    <h3 style="margin-top: 0">网盘浏览</h3>

    <div style="margin-bottom: 12px">
      <el-tag
        v-for="r in roots"
        :key="r.cid"
        style="margin-right: 8px; cursor: pointer"
        :type="
          breadcrumb[0]?.cid === r.cid ? 'primary' : 'info'
        "
        @click="browse(r.cid, r.name)"
      >
        {{ r.name }}
      </el-tag>
    </div>

    <el-breadcrumb separator="/" style="margin-bottom: 12px">
      <el-breadcrumb-item
        v-for="(b, idx) in breadcrumb"
        :key="b.cid"
        @click="jumpTo(idx)"
      >
        <a href="javascript:void(0)">{{ b.name }}</a>
      </el-breadcrumb-item>
    </el-breadcrumb>

    <el-alert
      v-if="error"
      :title="error"
      type="warning"
      :closable="false"
      style="margin-bottom: 12px"
    />

    <el-table
      :data="currentItems"
      v-loading="loading"
      style="width: 100%"
      empty-text="目录为空或未登录"
      @row-dblclick="(row: DirNode) => enterNode(row)"
    >
      <el-table-column label="名称">
        <template #default="{ row }">
          <el-icon v-if="row.is_dir" color="#409eff"><Folder /></el-icon>
          <el-icon v-else color="#909399"><Document /></el-icon>
          <span
            style="margin-left: 8px; cursor: pointer"
            @click="enterNode(row)"
          >
            {{ row.name }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="类型" width="100">
        <template #default="{ row }">
          {{ row.is_dir ? '文件夹' : '文件' }}
        </template>
      </el-table-column>
      <el-table-column prop="cid" label="CID" width="120" />
    </el-table>
  </el-card>
</template>
```

- [ ] **Step 11.2: 验证 TS 编译**

```bash
cd frontend
npx vue-tsc --noEmit
```

预期：无输出。

- [ ] **Step 11.3: 端到端验证**

启动后端 + 前端，浏览器访问 `http://localhost:5173/browser`：
- 如果未登录 115 → 看到"未登录 115，请先到登录页扫码"警告
- 如果已登录 → 看到根目录标签 + 内容表格
- 点击文件夹名称能进入子目录
- 面包屑能跳转

`Ctrl+C` 退出。

- [ ] **Step 11.4: 提交**

```bash
cd ..
git add frontend/src/views/BrowserView.vue
git commit -m "feat(fe): implement BrowserView with directory navigation"
```

---

### Task 12: 构建集成 + 后端 dist 挂载验证

**Files:**
- 无新建文件，运行构建并验证 FastAPI 静态托管

- [ ] **Step 12.1: 构建前端**

```bash
cd frontend
npm run build
```

预期：
- 输出 `dist/` 目录
- 终端显示 `dist/assets/index-*.js` 和 `dist/assets/index-*.css`
- 无 TS 错误
- exit code 0

- [ ] **Step 12.2: 验证 dist 内容**

```bash
ls dist/
```

预期看到：`index.html`、`assets/`、`favicon.ico`（可选）。

- [ ] **Step 12.3: 验证后端挂载（main.py 中 `dist.exists()` 检查路径是相对 cwd）**

后端 `app/main.py:108` 中 `Path("frontend/dist")`——相对于 `backend/` cwd 不存在该目录。需要在 `backend/` 下创建符号链接或修改路径。

**采用方案：修改 main.py 使用绝对路径解析到项目根目录的 `frontend/dist`。**

修改 `backend/app/main.py` 第 108 行：
```python
    # 静态文件（Plan B 构建 dist 后挂载）
    dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
    if dist.exists():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="static")
```

完整修改上下文（替换 `def create_app()` 末尾的静态文件挂载块）：
```python
def create_app() -> FastAPI:
    app = FastAPI(title="115 Auto Save", lifespan=lifespan)
    if settings.web_api_token:
        app.add_middleware(BearerTokenMiddleware, expected_token=settings.web_api_token)
    app.include_router(auth.router)
    app.include_router(tasks.router)
    app.include_router(history.router)
    app.include_router(dirs.router)
    app.include_router(config.router)

    @app.get("/healthz")
    def health():
        return {"ok": True, "logged_in": _is_logged_in()}

    # 静态文件：从 backend/app/main.py 解析到项目根目录的 frontend/dist
    # 这样无论从 backend/ 还是项目根启动都能正确挂载
    dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
    if dist.exists():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="static")

    return app
```

- [ ] **Step 12.4: 端到端冒烟（后端服务化运行，前端不再单独 dev）**

在 backend/ 目录启动后端：
```bash
cd backend
ENCRYPTION_KEY=$(python -c "import secrets,base64;print(base64.b64encode(secrets.token_bytes(32)).decode())") uvicorn app.main:app --port 8000
```

浏览器访问 `http://localhost:8000/`：
- 自动跳转到 `/tasks`（router 配置 redirect）
- 看到 Element Plus 主布局，左侧菜单
- 提交任务能成功
- 访问 `http://localhost:8000/healthz` → `{"ok": true, "logged_in": false}`
- 访问 `http://localhost:8000/docs` → Swagger UI
- 访问 `http://localhost:8000/login` → 二维码登录页

`Ctrl+C` 退出。

- [ ] **Step 12.5: 运行后端全回归测试（确保 main.py 修改未破坏）**

```bash
cd backend
.venv/Scripts/python.exe -m pytest tests/ -v
```

预期：67 passed（与 Plan A 完成时相同）。

- [ ] **Step 12.6: 添加 .gitignore 排除 dist**

修改 `frontend/.gitignore`，确认包含 `dist`：
```
node_modules
dist
*.local
.vite
```

- [ ] **Step 12.7: 提交**

```bash
cd ..
git add backend/app/main.py frontend/.gitignore
git commit -m "feat(app): mount frontend/dist via project-relative path for production"
```

---

## Plan B1 完成验收

执行完上述 12 个任务后，应满足：

- [ ] `cd frontend && npm run build` 成功，无 TS 错误
- [ ] `cd backend && uvicorn app.main:app` 启动后，浏览器访问 `http://localhost:8000/` 看到登录页
- [ ] 5 个 view 全部可访问：`/login`、`/tasks`、`/history`、`/config`、`/browser`
- [ ] 提交任务 → 任务列表显示 + SSE 实时推送生效
- [ ] 历史搜索/删除可用
- [ ] 配置查看（脱敏）+ 编辑保存可用
- [ ] 网盘浏览（已登录时）能进入子目录
- [ ] 后端 67 个测试无回归

**未完成项（B2/B3 处理）**：
- Telegram / 飞书适配器
- `_resolve_cid` 还在用占位 0（路径转存到 115 根目录，需要手动移动；B2 完善）
- Telegram 白名单等配置写入后还需要后端实际生效（B2 接入）
- Vitest 单元测试（如复杂度上升再补）

---

## Self-Review

**1. 规格覆盖：**
- spec §4.5 前端模块 → T1-T11 全部覆盖（5 view + stores + api + router）
- spec §4.3 API 路由对接 → T4 5 个 API 模块与后端 T18/T19 路由一一对应
- spec §6.3 SSE 推送 → T8 TasksView 中 EventSource 实现
- spec §6.3 Bearer Token → T3 client.ts 拦截器实现
- spec §8 部署与运行 → T12 dist 挂载 + 端到端冒烟

**2. 占位符扫描：**
- 无 "TBD" / "TODO" / "implement later"
- 所有 Vue SFC、配置文件、TS 模块均为完整可运行代码
- T6 中的 5 个占位 view 是临时占位（明确说明后续 task 替换），T7-T11 分别替换为完整实现

**3. 类型一致性：**
- `TaskOut` 字段与后端 `backend/app/schemas.py:TaskOut` 完全一致
- `ConfigOut`/`ConfigUpdate`/`HistoryOut`/`QRStartResp`/`QRStatusResp` 同上
- API 函数签名（如 `tasksApi.create(body: TaskCreate): Promise<TaskOut>`）与 view 调用一致
- 路由 name（'tasks'/'history'/'config'/'browser'/'login'）在 router、AppLayout 菜单、view 之间一致

**4. 实施执行顺序：** T1 脚手架 → T2 配置 → T3-T4 数据层 → T5 store → T6 路由布局 → T7-T11 各 view → T12 集成。每个 task 完成后可独立端到端验证（dev server 或 build）。
