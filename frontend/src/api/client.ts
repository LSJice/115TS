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
      if (!url.endsWith('/api/auth/check') && !url.endsWith('/api/auth/qrcode')) {
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
