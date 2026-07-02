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
