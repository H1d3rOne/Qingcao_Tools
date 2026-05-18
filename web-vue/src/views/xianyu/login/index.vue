<template>
  <div class="xianyu-login-page login-container">
    <el-card class="login-card">
      <template #header>
        <div class="card-header">
          <h2>登录闲鱼</h2>
          <p>优先使用设置中保存的 Cookie 自动登录，失败后请粘贴 Cookie 手动登录。</p>
        </div>
      </template>

      <!-- 自动登录中 -->
      <div
        v-if="autoLoginStatus === 'pending'"
        class="auto-login-status"
      >
        <el-icon
          class="is-loading"
          :size="32"
        >
          <Loading />
        </el-icon>
        <p>正在使用已保存的 Cookie 自动登录...</p>
      </div>

      <!-- 自动登录失败提示 -->
      <el-alert
        v-if="autoLoginStatus === 'failed' && autoLoginMessage"
        :title="autoLoginMessage"
        type="warning"
        :closable="false"
        show-icon
        class="auto-login-alert"
      />

      <div
        v-if="autoLoginStatus !== 'pending'"
        class="cookie-login"
      >
        <div class="login-section-title">
          <h3>Cookie 登录</h3>
          <p>支持直接粘贴 Cookie 字符串或浏览器导出的 JSON 内容。</p>
        </div>
        <el-form
          :model="cookieForm"
          label-width="80px"
        >
          <el-form-item label="Cookie">
            <el-input
              v-model="cookieForm.cookie"
              type="textarea"
              :rows="8"
              placeholder="请输入闲鱼 Cookie"
            />
          </el-form-item>
          <el-form-item>
            <el-button
              :loading="fillCookieLoading"
              @click="fillSavedCookie"
            >
              从本地已保存 Cookie 填充
            </el-button>
            <el-button
              type="primary"
              :loading="cookieSubmitting"
              @click="loginByCookie"
            >
              登录
            </el-button>
          </el-form-item>
        </el-form>
      </div>

      <el-collapse
        v-if="autoLoginStatus !== 'pending'"
        v-model="expandedPanels"
        class="login-secondary-collapse"
      >
        <el-collapse-item
          name="qrcode"
          title="扫码登录（可选）"
        >
          <div class="qrcode-login">
            <div class="qrcode-area">
              <div
                v-if="loading"
                class="qrcode-loading"
              >
                <el-icon
                  class="is-loading"
                  :size="40"
                >
                  <Loading />
                </el-icon>
                <p>正在生成二维码...</p>
              </div>
              <div
                v-else-if="error"
                class="qrcode-error"
              >
                <el-icon
                  :size="40"
                  color="#f56c6c"
                >
                  <Warning />
                </el-icon>
                <p>{{ error }}</p>
                <el-button
                  type="primary"
                  @click="generateQrcode"
                >
                  重新获取
                </el-button>
              </div>
              <div
                v-else
                class="qrcode-box"
              >
                <img
                  v-if="qrcodeImage"
                  :src="qrcodeImage"
                  alt="闲鱼登录二维码"
                  class="qrcode-image"
                >
                <div
                  v-else
                  class="qrcode-fallback"
                >
                  请点击下方“刷新二维码”获取登录二维码
                </div>
              </div>
            </div>

            <div class="qrcode-tips">
              <p v-if="browserLoginSessionId">
                请使用闲鱼 APP 扫码登录
              </p>
              <p
                v-if="checkingLogin"
                class="checking-status"
              >
                <el-icon class="is-loading">
                  <Loading />
                </el-icon>
                <span>{{ checkingText }}</span>
              </p>
              <el-link
                type="primary"
                :disabled="loading"
                @click="generateQrcode"
              >
                刷新二维码
              </el-link>
            </div>
          </div>
        </el-collapse-item>
      </el-collapse>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Loading, Warning } from '@element-plus/icons-vue'
import {
  cancelXianyuBrowserLogin,
  getXianyuBrowserLoginStatus,
  getXianyuAuthStatus,
  loginXianyu,
  startXianyuBrowserLogin,
} from '@/api/modules/xianyu'
import { getFullXianyuCookie } from '@/api/modules/settings'
import { useXianyuUserStore } from '@/stores'

const router = useRouter()
const route = useRoute()
const userStore = useXianyuUserStore()

const expandedPanels = ref<string[]>([])
const loading = ref(false)
const error = ref('')
const browserLoginSessionId = ref('')
const qrcodeImage = ref('')
const checkingLogin = ref(false)
const checkingText = ref('等待扫码中...')
const cookieSubmitting = ref(false)
const fillCookieLoading = ref(false)

// 自动登录状态：idle=未开始，pending=进行中，failed=失败，success=成功
const autoLoginStatus = ref<'idle' | 'pending' | 'failed' | 'success'>('idle')
const autoLoginMessage = ref('')

let pollTimer: number | null = null
let expireTimer: number | null = null

const cookieForm = reactive({
  cookie: '',
})

const getRedirectTarget = () => (route.query.redirect as string) || '/xianyu'

const clearPollingTimers = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  if (expireTimer) {
    clearTimeout(expireTimer)
    expireTimer = null
  }
  checkingLogin.value = false
}

const cancelBrowserSession = async () => {
  const sessionId = browserLoginSessionId.value
  browserLoginSessionId.value = ''
  if (!sessionId) {
    return
  }
  try {
    await cancelXianyuBrowserLogin(sessionId)
  } catch {
    // ignore cancel errors
  }
}

const generateQrcode = async () => {
  loading.value = true
  error.value = ''
  qrcodeImage.value = ''
  clearPollingTimers()
  await cancelBrowserSession()

  try {
    const response = await startXianyuBrowserLogin()
    if (!response.success) {
      throw new Error(response.message || '获取二维码失败')
    }

    browserLoginSessionId.value = response.session_id || ''
    qrcodeImage.value = response.qrcode_image || ''
    loading.value = false

    if (!qrcodeImage.value || !browserLoginSessionId.value) {
      throw new Error('二维码生成失败，请重试')
    }

    ElMessage.success(response.message || '二维码已生成，请使用闲鱼 APP 扫码')
    startPolling(browserLoginSessionId.value)
  } catch (err: unknown) {
    loading.value = false
    error.value = err instanceof Error ? err.message : '获取二维码失败'
    ElMessage.error(error.value)
  }
}

const startPolling = (sessionId: string) => {
  checkingLogin.value = true
  checkingText.value = '等待扫码中...'

  pollTimer = window.setInterval(async () => {
    try {
      const result = await getXianyuBrowserLoginStatus(sessionId)
      checkingText.value = result.message || '等待扫码中...'
      if (['expired', 'failed', 'cancelled'].includes(result.status)) {
        clearPollingTimers()
        browserLoginSessionId.value = ''
        error.value = result.message || '二维码已失效，请重新获取'
        ElMessage.error(error.value)
        return
      }
      if (result.is_logged_in) {
        clearPollingTimers()
        browserLoginSessionId.value = ''
        await userStore.checkAuthStatus()
        userStore.loginSuccess((await getXianyuAuthStatus()).user_info as Record<string, unknown> | null)
        ElMessage.success('登录成功！')
        router.push(getRedirectTarget())
      }
    } catch (err: unknown) {
      clearPollingTimers()
      error.value = err instanceof Error ? err.message : '登录状态检查失败'
      ElMessage.error(error.value)
    }
  }, 2000)

  expireTimer = window.setTimeout(() => {
    clearPollingTimers()
    browserLoginSessionId.value = ''
    error.value = '二维码已过期，请重新获取'
    ElMessage.warning(error.value)
  }, 5 * 60 * 1000)
}

const loginByCookie = async () => {
  if (!cookieForm.cookie.trim()) {
    ElMessage.warning('请输入 Cookie')
    return
  }

  cookieSubmitting.value = true
  try {
    const response = await loginXianyu({
      method: 'cookie',
      cookies: cookieForm.cookie.trim(),
    })
    if (!response.success) {
      throw new Error(response.message || '登录失败')
    }
    await userStore.checkAuthStatus()
    userStore.loginSuccess((await getXianyuAuthStatus()).user_info as Record<string, unknown> | null)
    ElMessage.success('登录成功')
    router.push(getRedirectTarget())
  } catch (err: unknown) {
    ElMessage.error(err instanceof Error ? err.message : '登录失败')
  } finally {
    cookieSubmitting.value = false
  }
}

const fillSavedCookie = async () => {
  fillCookieLoading.value = true
  try {
    const response = await getFullXianyuCookie()
    const cookie = response.data?.cookie?.trim() || ''
    if (!cookie) {
      ElMessage.warning('本地未找到已保存的闲鱼 Cookie')
      return
    }
    cookieForm.cookie = cookie
    ElMessage.success('已从本地填充闲鱼 Cookie')
  } catch (err: unknown) {
    ElMessage.error(err instanceof Error ? err.message : '读取本地 Cookie 失败')
  } finally {
    fillCookieLoading.value = false
  }
}

onMounted(async () => {
  if (!userStore.initialized) {
    await userStore.init()
  }
  if (userStore.isLoggedIn) {
    router.push(getRedirectTarget())
    return
  }
  // 尝试用设置中保存的 Cookie 自动登录
  await tryAutoLogin()
})

const tryAutoLogin = async () => {
  autoLoginStatus.value = 'pending'
  autoLoginMessage.value = ''
  try {
    const response = await getFullXianyuCookie()
    const savedCookie = response.data?.cookie?.trim() || ''
    if (!savedCookie) {
      autoLoginStatus.value = 'failed'
      autoLoginMessage.value = '设置中未配置闲鱼 Cookie，请粘贴 Cookie 手动登录'
      return
    }
    const loginRes = await loginXianyu({
      method: 'cookie',
      cookies: savedCookie,
    })
    if (!loginRes.success) {
      autoLoginStatus.value = 'failed'
      autoLoginMessage.value = `已保存的 Cookie 登录失败：${loginRes.message || 'Cookie 可能已失效'}，请重新粘贴 Cookie 登录`
      cookieForm.cookie = savedCookie
      return
    }
    await userStore.checkAuthStatus()
    userStore.loginSuccess((await getXianyuAuthStatus()).user_info as Record<string, unknown> | null)
    autoLoginStatus.value = 'success'
    ElMessage.success('已使用保存的 Cookie 自动登录')
    router.push(getRedirectTarget())
  } catch (err: unknown) {
    autoLoginStatus.value = 'failed'
    autoLoginMessage.value = err instanceof Error
      ? `自动登录失败：${err.message}，请重新粘贴 Cookie 登录`
      : '自动登录失败，请重新粘贴 Cookie 登录'
  }
}

onUnmounted(() => {
  clearPollingTimers()
  void cancelBrowserSession()
})
</script>

<style scoped>
.xianyu-login-page {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100%;
  padding: 48px 16px;
}

.login-card {
  width: min(100%, 720px);
}

.card-header {
  display: grid;
  gap: 6px;
}

.card-header h2 {
  margin: 0;
}

.card-header p {
  margin: 0;
  color: #6b7280;
}

.login-section-title {
  display: grid;
  gap: 4px;
  margin-bottom: 12px;
}

.login-section-title h3 {
  margin: 0;
  font-size: 16px;
  color: #111827;
}

.login-section-title p {
  margin: 0;
  color: #6b7280;
  font-size: 13px;
}

.qrcode-login {
  display: grid;
  gap: 18px;
  justify-items: center;
  padding: 12px 0 8px;
}

.qrcode-area {
  width: 240px;
  min-height: 240px;
  display: grid;
  place-items: center;
  border: 1px dashed #d1d5db;
  border-radius: 18px;
  background: #fff;
}

.qrcode-box,
.qrcode-loading,
.qrcode-error {
  width: 100%;
  min-height: 240px;
  display: grid;
  place-items: center;
  text-align: center;
  gap: 12px;
}

.qrcode-image {
  width: 220px;
  height: 220px;
  object-fit: contain;
}

.qrcode-fallback {
  color: #6b7280;
}

.qrcode-tips {
  display: grid;
  gap: 8px;
  justify-items: center;
  color: #6b7280;
}

.checking-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.cookie-login {
  padding-top: 8px;
}

.auto-login-status {
  display: grid;
  gap: 12px;
  justify-items: center;
  padding: 32px 0;
  color: #6b7280;
}

.auto-login-status p {
  margin: 0;
  font-size: 14px;
}

.auto-login-alert {
  margin-bottom: 16px;
}

.login-secondary-collapse {
  margin-top: 12px;
}
</style>
