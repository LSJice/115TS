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
