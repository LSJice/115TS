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
