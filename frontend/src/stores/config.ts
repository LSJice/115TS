import { defineStore } from 'pinia'
import { ref } from 'vue'
import { configApi } from '@/api/config'
import type { ConfigOut, ConfigUpdate } from '@/types'

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

  async function save(patch: ConfigUpdate): Promise<ConfigOut> {
    const resp = await configApi.update(patch)
    data.value = resp
    return resp
  }

  return { data, loading, fetch, save }
})
