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
