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
              type="primary"
              :loading="cookieSubmitting"
              @click="loginByCookie"
            >
              登录
            </el-button>
            <el-button
              text
              :disabled="cookieSubmitting"
              @click="fillSavedCookie"
            >
              从本地已保存 Cookie 填充
            </el-button>
          </el-form-item>
        </el-form>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import {
  getXianyuAuthStatus,
  loginXianyu,
} from '@/api/modules/xianyu'
import { getFullXianyuCookie } from '@/api/modules/settings'
import { useXianyuUserStore } from '@/stores'

const router = useRouter()
const route = useRoute()
const userStore = useXianyuUserStore()

const cookieSubmitting = ref(false)

// 自动登录状态：idle=未开始，pending=进行中，failed=失败，success=成功
const autoLoginStatus = ref<'idle' | 'pending' | 'failed' | 'success'>('idle')
const autoLoginMessage = ref('')

const cookieForm = reactive({
  cookie: '',
})

const getRedirectTarget = () => (route.query.redirect as string) || '/xianyu'

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
  try {
    const response = await getFullXianyuCookie()
    const savedCookie = response.data?.cookie?.trim() || ''
    if (!savedCookie) {
      ElMessage.warning('本地未保存闲鱼 Cookie')
      return
    }
    cookieForm.cookie = savedCookie
    ElMessage.success('已填充本地保存的 Cookie')
  } catch (err: unknown) {
    ElMessage.error(err instanceof Error ? err.message : '读取本地 Cookie 失败')
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
</style>
