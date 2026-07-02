<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { authApi } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const qrcodeUrl = ref<string>('')
type LoginState = 'idle' | 'waiting' | 'success' | 'error'
const state = ref<LoginState>('idle')
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
