<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Promotion, Check } from '@element-plus/icons-vue'
import {
  getNotifyConfig,
  updateWecomConfig,
  updateDingtalkConfig,
  updateFeishuConfig,
  testWecomNotify,
  testDingtalkNotify,
  testFeishuNotify
} from '@/api/modules/notify'

interface WebhookConfig {
  enabled: boolean
  webhook_url: string | null
}

interface NotifyConfig {
  wecom: WebhookConfig
  dingtalk: WebhookConfig
  feishu: WebhookConfig
}

const loading = ref(false)
const config = ref<NotifyConfig>({
  wecom: { enabled: false, webhook_url: null },
  dingtalk: { enabled: false, webhook_url: null },
  feishu: { enabled: false, webhook_url: null }
})

const wecomUrl = ref('')
const dingtalkUrl = ref('')
const feishuUrl = ref('')

const wecomSaving = ref(false)
const dingtalkSaving = ref(false)
const feishuSaving = ref(false)

const wecomTesting = ref(false)
const dingtalkTesting = ref(false)
const feishuTesting = ref(false)

const activePanel = ref(['wecom', 'dingtalk', 'feishu'])

onMounted(async () => {
  await loadConfig()
})

async function loadConfig() {
  loading.value = true
  try {
    const res = await getNotifyConfig()
    if (res && res.data) {
      config.value = res.data
      wecomUrl.value = res.data.wecom.webhook_url || ''
      dingtalkUrl.value = res.data.dingtalk.webhook_url || ''
      feishuUrl.value = res.data.feishu.webhook_url || ''
    }
  } catch (err) {
    console.error('获取配置失败:', err)
  } finally {
    loading.value = false
  }
}

async function handleSaveWecom() {
  if (!wecomUrl.value.trim()) {
    ElMessage.warning('请输入Webhook地址')
    return
  }

  wecomSaving.value = true
  try {
    await updateWecomConfig({
      webhook_url: wecomUrl.value.trim(),
      enabled: true
    })
    ElMessage.success('企业微信配置保存成功')
    await loadConfig()
  } catch (err: any) {
    ElMessage.error(err.message || '保存失败')
  } finally {
    wecomSaving.value = false
  }
}

async function handleSaveDingtalk() {
  if (!dingtalkUrl.value.trim()) {
    ElMessage.warning('请输入Webhook地址')
    return
  }

  dingtalkSaving.value = true
  try {
    await updateDingtalkConfig({
      webhook_url: dingtalkUrl.value.trim(),
      enabled: true
    })
    ElMessage.success('钉钉配置保存成功')
    await loadConfig()
  } catch (err: any) {
    ElMessage.error(err.message || '保存失败')
  } finally {
    dingtalkSaving.value = false
  }
}

async function handleSaveFeishu() {
  if (!feishuUrl.value.trim()) {
    ElMessage.warning('请输入Webhook地址')
    return
  }

  feishuSaving.value = true
  try {
    await updateFeishuConfig({
      webhook_url: feishuUrl.value.trim(),
      enabled: true
    })
    ElMessage.success('飞书配置保存成功')
    await loadConfig()
  } catch (err: any) {
    ElMessage.error(err.message || '保存失败')
  } finally {
    feishuSaving.value = false
  }
}

async function handleTestWecom() {
  wecomTesting.value = true
  try {
    await testWecomNotify('这是一条来自 Qingcao_Tools 的测试消息')
    ElMessage.success('测试消息发送成功')
  } catch (err: any) {
    ElMessage.error(err.message || '发送失败')
  } finally {
    wecomTesting.value = false
  }
}

async function handleTestDingtalk() {
  dingtalkTesting.value = true
  try {
    await testDingtalkNotify('这是一条来自 Qingcao_Tools 的测试消息')
    ElMessage.success('测试消息发送成功')
  } catch (err: any) {
    ElMessage.error(err.message || '发送失败')
  } finally {
    dingtalkTesting.value = false
  }
}

async function handleTestFeishu() {
  feishuTesting.value = true
  try {
    await testFeishuNotify('这是一条来自 Qingcao_Tools 的测试消息')
    ElMessage.success('测试消息发送成功')
  } catch (err: any) {
    ElMessage.error(err.message || '发送失败')
  } finally {
    feishuTesting.value = false
  }
}
</script>

<template>
  <div class="notify-page">
    <div class="page-header">
      <h1 class="page-title">
        <div class="header-icon">
          <el-icon><Promotion /></el-icon>
        </div>
        消息推送
      </h1>
      <p class="page-desc">
        配置企业微信、钉钉、飞书Webhook实现消息推送
      </p>
    </div>

    <el-collapse v-model="activePanel" class="settings-collapse">
      <el-collapse-item name="wecom">
        <template #title>
          <div class="collapse-title">
            <div class="collapse-title__left">
              <div class="collapse-icon collapse-icon--green">
                <el-icon><Promotion /></el-icon>
              </div>
              <span class="collapse-label">企业微信</span>
            </div>
            <div class="collapse-title__right">
              <el-tag v-if="config.wecom.enabled" type="success" size="small">
                <el-icon class="mr-1"><Check /></el-icon>已启用
              </el-tag>
              <el-tag v-else type="info" size="small">未配置</el-tag>
            </div>
          </div>
        </template>
        <div class="settings-content">
          <div class="config-item">
            <div class="config-row">
              <label class="config-label">Webhook 地址</label>
              <el-tag :type="config.wecom.enabled ? 'success' : 'info'" size="small">
                {{ config.wecom.enabled ? '已配置' : '未配置' }}
              </el-tag>
            </div>
            <p class="config-hint">在企业微信群聊中添加机器人获取Webhook地址</p>
            <el-input v-model="wecomUrl" placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx" class="webhook-input" />
            <div class="config-actions">
              <el-button type="primary" size="small" :loading="wecomSaving" @click="handleSaveWecom">保存</el-button>
              <el-button size="small" :loading="wecomTesting" :disabled="!config.wecom.enabled" @click="handleTestWecom">测试发送</el-button>
            </div>
          </div>
        </div>
      </el-collapse-item>

      <el-collapse-item name="dingtalk">
        <template #title>
          <div class="collapse-title">
            <div class="collapse-title__left">
              <div class="collapse-icon collapse-icon--teal">
                <el-icon><Promotion /></el-icon>
              </div>
              <span class="collapse-label">钉钉</span>
            </div>
            <div class="collapse-title__right">
              <el-tag v-if="config.dingtalk.enabled" type="success" size="small">
                <el-icon class="mr-1"><Check /></el-icon>已启用
              </el-tag>
              <el-tag v-else type="info" size="small">未配置</el-tag>
            </div>
          </div>
        </template>
        <div class="settings-content">
          <div class="config-item">
            <div class="config-row">
              <label class="config-label">Webhook 地址</label>
              <el-tag :type="config.dingtalk.enabled ? 'success' : 'info'" size="small">
                {{ config.dingtalk.enabled ? '已配置' : '未配置' }}
              </el-tag>
            </div>
            <p class="config-hint">在钉钉群聊中添加自定义机器人获取Webhook地址</p>
            <el-input v-model="dingtalkUrl" placeholder="https://oapi.dingtalk.com/robot/send?access_token=xxx" class="webhook-input" />
            <div class="config-actions">
              <el-button type="primary" size="small" :loading="dingtalkSaving" @click="handleSaveDingtalk">保存</el-button>
              <el-button size="small" :loading="dingtalkTesting" :disabled="!config.dingtalk.enabled" @click="handleTestDingtalk">测试发送</el-button>
            </div>
          </div>
        </div>
      </el-collapse-item>

      <el-collapse-item name="feishu">
        <template #title>
          <div class="collapse-title">
            <div class="collapse-title__left">
              <div class="collapse-icon collapse-icon--cyan">
                <el-icon><Promotion /></el-icon>
              </div>
              <span class="collapse-label">飞书</span>
            </div>
            <div class="collapse-title__right">
              <el-tag v-if="config.feishu.enabled" type="success" size="small">
                <el-icon class="mr-1"><Check /></el-icon>已启用
              </el-tag>
              <el-tag v-else type="info" size="small">未配置</el-tag>
            </div>
          </div>
        </template>
        <div class="settings-content">
          <div class="config-item">
            <div class="config-row">
              <label class="config-label">Webhook 地址</label>
              <el-tag :type="config.feishu.enabled ? 'success' : 'info'" size="small">
                {{ config.feishu.enabled ? '已配置' : '未配置' }}
              </el-tag>
            </div>
            <p class="config-hint">在飞书群聊中添加自定义机器人获取Webhook地址</p>
            <el-input v-model="feishuUrl" placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/xxx" class="webhook-input" />
            <div class="config-actions">
              <el-button type="primary" size="small" :loading="feishuSaving" @click="handleSaveFeishu">保存</el-button>
              <el-button size="small" :loading="feishuTesting" :disabled="!config.feishu.enabled" @click="handleTestFeishu">测试发送</el-button>
            </div>
          </div>
        </div>
      </el-collapse-item>
    </el-collapse>

    <div class="guide-panel">
      <h3 class="guide-title">获取 Webhook 说明</h3>
      <div class="guide-grid">
        <div>
          <h4 class="guide-section-title guide-section-title--green">企业微信</h4>
          <ol class="guide-steps">
            <li class="guide-step"><span class="step-num">1</span>打开企业微信群聊</li>
            <li class="guide-step"><span class="step-num">2</span>点击群设置 → 群机器人</li>
            <li class="guide-step"><span class="step-num">3</span>添加机器人并获取Webhook</li>
          </ol>
        </div>
        <div>
          <h4 class="guide-section-title guide-section-title--teal">钉钉</h4>
          <ol class="guide-steps">
            <li class="guide-step"><span class="step-num">1</span>打开钉钉群聊</li>
            <li class="guide-step"><span class="step-num">2</span>点击群设置 → 智能群助手</li>
            <li class="guide-step"><span class="step-num">3</span>添加自定义机器人</li>
          </ol>
        </div>
        <div>
          <h4 class="guide-section-title guide-section-title--cyan">飞书</h4>
          <ol class="guide-steps">
            <li class="guide-step"><span class="step-num">1</span>打开飞书群聊</li>
            <li class="guide-step"><span class="step-num">2</span>点击群设置 → 群机器人</li>
            <li class="guide-step"><span class="step-num">3</span>添加自定义机器人</li>
          </ol>
        </div>
      </div>
      <div class="warning-box">
        <p class="warning-text">
          <strong>注意：</strong>Webhook 地址包含敏感信息，请勿泄露。建议设置IP白名单或签名验证。
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.notify-page {
  max-width: 56rem;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 24px;
}

.page-title {
  font-size: 22px;
  font-weight: 700;
  color: rgb(var(--app-text-strong-rgb));
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 0 0 8px;
}

.header-icon {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: linear-gradient(135deg, rgb(var(--primary-color-rgb)), rgb(var(--app-accent-soft-rgb)));
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgb(var(--utility-white-rgb));
}

.page-desc {
  color: rgb(var(--app-text-muted-rgb));
  margin: 0;
}

.settings-collapse {
  border: none;
  --el-collapse-header-bg-color: transparent;
}

.settings-collapse :deep(.el-collapse-item__header) {
  background-color: rgba(var(--app-surface-rgb) / 0.92);
  border: 1px solid rgba(var(--app-border-rgb) / 0.7);
  border-radius: 12px;
  padding: 16px 20px;
  margin-bottom: 12px;
  height: auto;
  line-height: 1.5;
}

.settings-collapse :deep(.el-collapse-item__header:hover) {
  border-color: rgba(var(--primary-color-rgb) / 0.3);
}

.settings-collapse :deep(.el-collapse-item__wrap) {
  background-color: transparent;
  border: none;
}

.settings-collapse :deep(.el-collapse-item__content) {
  padding: 0;
}

.settings-collapse :deep(.el-collapse-item__arrow) {
  display: none;
}

.collapse-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding-right: 16px;
}

.collapse-title__left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.collapse-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.collapse-icon--green {
  background: rgba(var(--primary-color-rgb) / 0.14);
  color: rgb(var(--primary-color-rgb));
}

.collapse-icon--teal {
  background: rgba(var(--app-accent-soft-rgb) / 0.14);
  color: rgb(var(--app-accent-soft-rgb));
}

.collapse-icon--cyan {
  background: rgba(var(--app-accent-alt-rgb) / 0.14);
  color: rgb(var(--app-accent-alt-rgb));
}

.collapse-label {
  color: rgb(var(--app-text-strong-rgb));
  font-weight: 500;
}

.settings-content {
  background: rgba(var(--app-surface-rgb) / 0.92);
  border: 1px solid rgba(var(--app-border-rgb) / 0.7);
  border-radius: 12px;
  margin-top: -8px;
  margin-bottom: 12px;
}

.config-item {
  padding: 16px;
  background: rgba(var(--app-surface-alt-rgb) / 0.92);
  border-radius: 8px;
}

.config-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.config-label {
  color: rgb(var(--app-text-rgb));
  font-size: 14px;
  font-weight: 500;
}

.config-hint {
  color: rgb(var(--app-text-subtle-rgb));
  font-size: 12px;
  margin: 0 0 8px;
}

.config-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.webhook-input :deep(.el-input__wrapper) {
  background: rgba(var(--app-bg-rgb) / 0.92) !important;
  box-shadow: 0 0 0 1px rgba(var(--app-border-rgb) / 0.8) inset !important;
}

.webhook-input :deep(.el-input__inner) {
  color: rgb(var(--app-text-strong-rgb)) !important;
}

.webhook-input :deep(.el-input__wrapper:focus-within) {
  box-shadow: 0 0 0 1px rgb(var(--primary-color-rgb)) inset !important;
}

.guide-panel {
  margin-top: 24px;
  padding: 20px;
  border-radius: 14px;
  background: rgba(var(--app-surface-rgb) / 0.92);
  border: 1px solid rgba(var(--app-border-rgb) / 0.7);
}

.guide-title {
  font-size: 15px;
  font-weight: 600;
  color: rgb(var(--app-text-strong-rgb));
  margin: 0 0 16px;
}

.guide-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
}

.guide-section-title {
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 12px;
}

.guide-section-title--green {
  color: rgb(var(--primary-color-rgb));
}

.guide-section-title--teal {
  color: rgb(var(--app-accent-soft-rgb));
}

.guide-section-title--cyan {
  color: rgb(var(--app-accent-alt-rgb));
}

.guide-steps {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.guide-step {
  display: flex;
  align-items: center;
  gap: 8px;
  color: rgb(var(--app-text-muted-rgb));
  font-size: 14px;
}

.step-num {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: rgba(var(--primary-color-rgb) / 0.14);
  color: rgb(var(--primary-color-rgb));
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.warning-box {
  margin-top: 16px;
  padding: 12px;
  border-radius: 10px;
  background: rgba(234 179 8, 0.08);
  border: 1px solid rgba(234 179 8, 0.2);
}

.warning-text {
  color: rgb(250 204 21);
  font-size: 14px;
  margin: 0;
}

@media (max-width: 768px) {
  .guide-grid {
    grid-template-columns: 1fr;
  }
}
</style>
