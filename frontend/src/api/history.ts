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
