<template>
  <div class="quark-login-page login-container">
    <el-card class="login-card">
      <template #header>
        <div class="card-header">
          <h2>登录夸克网盘</h2>
        </div>
      </template>
      <el-tabs v-model="activeTab">
        <el-tab-pane label="二维码登录" name="qrcode">
          <div class="qrcode-login">
            <div class="qrcode-area">
              <div v-if="loading" class="qrcode-loading">
                <el-icon class="is-loading" :size="40">
                  <Loading />
                </el-icon>
                <p>正在生成二维码...</p>
              </div>
              <div v-else-if="error" class="qrcode-error">
                <el-icon :size="40" color="#f56c6c">
                  <Warning />
                </el-icon>
                <p>{{ error }}</p>
                <el-button type="primary" @click="generateQrcode">重新获取</el-button>
              </div>
              <div v-else class="qrcode-box">
                <img v-if="qrcodeImage" :src="qrcodeImage" alt="登录二维码" class="qrcode-image" />
                <div v-else class="qrcode-fallback">二维码加载中...</div>
              </div>
            </div>
            <div class="qrcode-tips">
              <p v-if="qrcodeToken">请使用夸克 APP 扫码登录</p>
              <p v-if="checkingLogin" class="checking-status">
                <el-icon class="is-loading"><Loading /></el-icon>
                等待扫码中...
              </p>
              <el-link type="primary" @click="generateQrcode" :disabled="loading">刷新二维码</el-link>
            </div>
          </div>
        </el-tab-pane>
        <el-tab-pane label="Cookie 登录" name="cookie">
          <div class="cookie-login">
            <el-form :model="cookieForm" label-width="80px">
              <el-form-item label="Cookie">
                <el-input
                  v-model="cookieForm.cookie"
                  type="textarea"
                  :rows="6"
                  placeholder="请输入 Cookie"
                />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="loginByCookie">登录</el-button>
              </el-form-item>
            </el-form>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Loading, Warning } from '@element-plus/icons-vue'
import { authAPI } from '@/api/modules/quark'
import { useQuarkUserStore } from '@/stores'

const router = useRouter()
const route = useRoute()
const userStore = useQuarkUserStore()
const activeTab = ref('qrcode')
const loading = ref(false)
const error = ref('')
const qrcodeToken = ref('')
const qrcodeImage = ref('')
const checkingLogin = ref(false)

let pollTimer: number | null = null

const cookieForm = reactive({
  cookie: ''
})

const getRedirectTarget = () => (route.query.redirect as string) || '/quark/files'

const generateQrcode = async () => {
  loading.value = true
  error.value = ''
  qrcodeImage.value = ''

  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }

  try {
    const response = await authAPI.getQRCode()

    if (response.success && response.qrcode_url) {
      loading.value = false
      qrcodeToken.value = response.qrcode_token || ''
      qrcodeImage.value = response.qrcode_image || ''
      ElMessage.success('二维码已生成，请使用夸克 APP 扫码')

      if (!qrcodeImage.value) {
        error.value = '二维码图片生成失败，请刷新重试'
        return
      }

      if (qrcodeToken.value) {
        startPolling(qrcodeToken.value)
      }
    } else {
      loading.value = false
      error.value = response.message || '获取二维码失败'
      ElMessage.error(error.value)
    }
  } catch (err: any) {
    loading.value = false
    error.value = err.response?.data?.detail || '获取二维码失败，请检查后端服务是否正常'
    ElMessage.error(error.value)
  }
}

const startPolling = (token: string) => {
  checkingLogin.value = true

  pollTimer = window.setInterval(async () => {
    try {
      const result = await authAPI.checkLogin({ qrcode_token: token })
      if (result.is_logged_in) {
        stopPolling()
        userStore.loginSuccess()
        ElMessage.success('登录成功！')
        router.push(getRedirectTarget())
      }
    } catch (err: any) {
      if (err.response?.status === 400) {
        stopPolling()
        error.value = '二维码已过期，请重新获取'
        ElMessage.warning(error.value)
      }
    }
  }, 2000)

  setTimeout(() => {
    if (pollTimer) {
      stopPolling()
      error.value = '二维码已过期，请重新获取'
      ElMessage.warning(error.value)
    }
  }, 5 * 60 * 1000)
}

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  checkingLogin.value = false
}

const loginByCookie = async () => {
  if (!cookieForm.cookie.trim()) {
    ElMessage.warning('请输入 Cookie')
    return
  }

  try {
    const response = await authAPI.login({
      method: 'simple',
      cookies: cookieForm.cookie
    })

    if (response.success) {
      userStore.loginSuccess()
      ElMessage.success('登录成功')
      router.push(getRedirectTarget())
    } else {
      ElMessage.error(response.message || '登录失败')
    }
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || '登录失败')
  }
}

const tryAutoLogin = async () => {
  try {
    const response = await authAPI.autoLogin()
    if (response.success) {
      userStore.loginSuccess()
      ElMessage.success('已自动登录')
      router.push(getRedirectTarget())
      return true
    }
  } catch (err: any) {
    console.log('自动登录失败:', err.response?.data?.detail || err.message)
  }
  return false
}

onMounted(async () => {
  if (userStore.isLoggedIn) {
    router.push(getRedirectTarget())
    return
  }

  if (userStore.shouldSkipAutoLogin()) {
    generateQrcode()
    return
  }

  const loggedIn = await tryAutoLogin()
  if (!loggedIn) {
    generateQrcode()
  }
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.login-container {
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 24px;
  background:
    radial-gradient(circle at top left, rgba(var(--quark-primary-rgb) / 0.08), transparent 26%),
    radial-gradient(circle at 85% 12%, rgba(var(--quark-accent-rgb) / 0.08), transparent 22%),
    linear-gradient(180deg, rgb(var(--quark-bg-rgb)) 0%, rgb(var(--quark-bg-soft-rgb)) 100%);
}

.login-card {
  width: min(500px, 100%);
  border: 1px solid rgba(var(--quark-border-rgb) / 0.52);
  border-radius: 24px;
  overflow: hidden;
  box-shadow: 0 14px 36px rgba(var(--app-shadow-rgb) / 0.09), inset 0 1px 0 rgba(var(--utility-white-rgb) / 0.5);
}

.login-card :deep(.el-card__header) {
  padding: 24px 24px 18px;
  background: rgba(var(--quark-surface-soft-rgb) / 0.52);
}

.login-card :deep(.el-card__body) {
  padding: 22px 24px 24px;
}

.card-header {
  text-align: center;
}

.card-header h2 {
  margin: 0;
  color: rgb(var(--quark-text-rgb));
}

.qrcode-login {
  text-align: center;
}

.qrcode-area {
  margin: 20px 0;
  min-height: 240px;
  display: flex;
  justify-content: center;
  align-items: center;
  border-radius: 20px;
  background: rgba(var(--quark-surface-soft-rgb) / 0.52);
  border: 1px dashed rgba(var(--quark-primary-rgb) / 0.28);
}

.qrcode-loading,
.qrcode-error {
  text-align: center;
}

.qrcode-loading p,
.qrcode-error p {
  margin-top: 10px;
  color: rgb(var(--quark-text-muted-rgb));
}

.qrcode-box {
  width: 220px;
  height: 220px;
  border: 1px solid rgba(var(--quark-border-rgb) / 0.36);
  border-radius: 18px;
  overflow: hidden;
  background: rgb(var(--quark-surface-rgb));
  display: flex;
  justify-content: center;
  align-items: center;
  box-shadow: 0 10px 24px rgba(var(--app-shadow-rgb) / 0.07);
}

.qrcode-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
  padding: 10px;
}

.qrcode-fallback {
  color: rgb(var(--quark-text-subtle-rgb));
  font-size: 13px;
}

.qrcode-tips {
  margin-top: 20px;
}

.qrcode-tips p {
  color: rgb(var(--quark-text-muted-rgb));
  margin-bottom: 10px;
}

.checking-status {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: rgb(var(--quark-primary-rgb)) !important;
}

.cookie-login {
  padding: 10px 0;
}
</style>
