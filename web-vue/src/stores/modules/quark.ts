import { defineStore } from 'pinia'
import { ref } from 'vue'
import { authAPI } from '@/api/modules/quark'

const QUARK_SKIP_AUTO_LOGIN_KEY = 'quark_skip_auto_login'

export const useQuarkUserStore = defineStore('quark-user', () => {
  const isLoggedIn = ref(false)
  const userInfo = ref<any>(null)
  const loading = ref(false)
  const initialized = ref(false)

  const loadFromStorage = () => {
    try {
      const stored = localStorage.getItem('quark_auth')
      if (stored) {
        const data = JSON.parse(stored)
        isLoggedIn.value = data.isLoggedIn || false
        userInfo.value = data.userInfo || null
      }
    } catch (error) {
      console.error('加载认证状态失败:', error)
    }
  }

  const saveToStorage = () => {
    try {
      localStorage.setItem('quark_auth', JSON.stringify({
        isLoggedIn: isLoggedIn.value,
        userInfo: userInfo.value
      }))
    } catch (error) {
      console.error('保存认证状态失败:', error)
    }
  }

  const setLoginStatus = (status: boolean) => {
    isLoggedIn.value = status
    saveToStorage()
  }

  const setUserInfo = (info: any) => {
    userInfo.value = info
    saveToStorage()
  }

  const loginSuccess = (info?: any) => {
    isLoggedIn.value = true
    if (info) {
      userInfo.value = info
    }
    localStorage.removeItem(QUARK_SKIP_AUTO_LOGIN_KEY)
    saveToStorage()
  }

  const shouldSkipAutoLogin = () => {
    return localStorage.getItem(QUARK_SKIP_AUTO_LOGIN_KEY) === '1'
  }

  const markSkipAutoLogin = () => {
    localStorage.setItem(QUARK_SKIP_AUTO_LOGIN_KEY, '1')
  }

  const logout = async () => {
    try {
      await authAPI.logout()
    } catch (error) {
      console.error('退出登录失败:', error)
    }
    markSkipAutoLogin()
    isLoggedIn.value = false
    userInfo.value = null
    localStorage.removeItem('quark_auth')
    localStorage.removeItem('quark_cookies')
    localStorage.removeItem('quark_cookies_expiry')
  }

  const checkAuthStatus = async () => {
    loading.value = true
    try {
      const response = await authAPI.getStatus()
      if (response.is_logged_in) {
        isLoggedIn.value = true
        userInfo.value = response.user_info || null
        saveToStorage()
        return true
      }

      if (shouldSkipAutoLogin()) {
        isLoggedIn.value = false
        userInfo.value = null
        saveToStorage()
        return false
      }

      try {
        const autoLoginResponse = await authAPI.autoLogin()
        if (autoLoginResponse.success) {
          isLoggedIn.value = true
          try {
            const refreshed = await authAPI.getStatus()
            userInfo.value = refreshed.user_info || null
          } catch {
            userInfo.value = null
          }
          saveToStorage()
          return true
        }
      } catch {
        // 自动登录失败时保持未登录状态
      }

      isLoggedIn.value = false
      userInfo.value = null
      saveToStorage()
      return false
    } catch (error) {
      console.error('检查登录状态失败:', error)
      return false
    } finally {
      loading.value = false
      initialized.value = true
    }
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
    setLoginStatus,
    setUserInfo,
    loginSuccess,
    logout,
    checkAuthStatus,
    init,
    shouldSkipAutoLogin
  }
})
