import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  getXianyuAuthStatus,
  logoutXianyu,
  type XianyuAuthStatusResponse,
} from '@/api/modules/xianyu'

export const useXianyuUserStore = defineStore('xianyu-user', () => {
  const isLoggedIn = ref(false)
  const userInfo = ref<Record<string, unknown> | null>(null)
  const loading = ref(false)
  const initialized = ref(false)

  const loadFromStorage = () => {
    try {
      const stored = localStorage.getItem('xianyu_auth')
      if (stored) {
        const data = JSON.parse(stored)
        isLoggedIn.value = Boolean(data.isLoggedIn)
        userInfo.value = data.userInfo || null
      }
    } catch (error) {
      console.error('加载闲鱼认证状态失败:', error)
    }
  }

  const saveToStorage = () => {
    try {
      localStorage.setItem(
        'xianyu_auth',
        JSON.stringify({
          isLoggedIn: isLoggedIn.value,
          userInfo: userInfo.value,
        }),
      )
    } catch (error) {
      console.error('保存闲鱼认证状态失败:', error)
    }
  }

  const loginSuccess = (info?: Record<string, unknown> | null) => {
    isLoggedIn.value = true
    if (info) {
      userInfo.value = info
    }
    saveToStorage()
  }

  const setLoggedOut = () => {
    isLoggedIn.value = false
    userInfo.value = null
    localStorage.removeItem('xianyu_auth')
  }

  const checkAuthStatus = async () => {
    loading.value = true
    try {
      const response: XianyuAuthStatusResponse = await getXianyuAuthStatus()
      isLoggedIn.value = Boolean(response.is_logged_in)
      userInfo.value = (response.user_info as Record<string, unknown> | null) || null
      saveToStorage()
      return isLoggedIn.value
    } catch (error) {
      console.error('检查闲鱼登录状态失败:', error)
      setLoggedOut()
      return false
    } finally {
      loading.value = false
      initialized.value = true
    }
  }

  const logout = async () => {
    try {
      await logoutXianyu()
    } catch (error) {
      console.error('闲鱼退出登录失败:', error)
    }
    setLoggedOut()
  }

  const init = async () => {
    loadFromStorage()
    await checkAuthStatus()
    initialized.value = true
  }

  return {
    isLoggedIn,
    userInfo,
    loading,
    initialized,
    loginSuccess,
    logout,
    checkAuthStatus,
    init,
  }
})
