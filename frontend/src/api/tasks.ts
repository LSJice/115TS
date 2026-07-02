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
