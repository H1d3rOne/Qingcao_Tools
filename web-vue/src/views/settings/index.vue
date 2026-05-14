<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Check, Delete, Edit, View, Hide } from '@element-plus/icons-vue'
import {
  getCookieSettings,
  updateDyCookie,
  updateLiveCookie,
  updateXianyuCookie,
  updateQuarkCookie,
} from '@/api/modules/settings'
import {
  getXianyuChatAiConfig,
  setXianyuChatAiEnabled,
  setXianyuChatKeepaliveInterval,
  createXianyuChatAiProvider,
  updateXianyuChatAiProvider,
  deleteXianyuChatAiProvider,
  setActiveXianyuChatAiProvider,
  testXianyuChatAi,
  testXianyuChatAiProvider,
  getXianyuChatAiProviderApiKey,
  setXianyuChatAiProviderActiveModel,
  type XianyuChatAiConfig,
  type XianyuChatAiProvider,
} from '@/api/modules/xianyu'

const activeTab = ref('cookies')

const dyCookieInput = ref('')
const liveCookieInput = ref('')
const xianyuCookieInput = ref('')
const quarkCookieInput = ref('')
const loading = ref(false)
const dySaving = ref(false)
const liveSaving = ref(false)
const xianyuSaving = ref(false)
const quarkSaving = ref(false)
const dyConfigured = ref(false)
const liveConfigured = ref(false)
const xianyuConfigured = ref(false)
const quarkFallbackConfigured = ref(false)

const aiConfig = ref<XianyuChatAiConfig | null>(null)
const aiConfigLoading = ref(false)
const aiTesting = ref(false)
const aiKeepaliveSaving = ref(false)
const keepaliveIntervalSeconds = ref(180)

const showProviderDialog = ref(false)
const editingProvider = ref<XianyuChatAiProvider | null>(null)
const providerTesting = ref(false)
const apiKeyConfigured = ref(false)
const newModelInput = ref('')
const providerForm = ref({
  name: '',
  base_url: '',
  api_key: '',
  models: [] as string[],
  active_model: '',
  system_prompt: '',
})

onMounted(async () => {
  await Promise.all([loadCookieSettings(), loadAiConfig()])
})

async function loadCookieSettings() {
  loading.value = true
  try {
    const res = await getCookieSettings()
    if (res && res.data) {
      dyConfigured.value = res.data.dy_configured || false
      liveConfigured.value = res.data.live_configured || false
      quarkFallbackConfigured.value = res.data.quark_configured || false
      xianyuConfigured.value = res.data.xianyu_configured || false
    }
  } catch (err) {
    console.error('获取Cookie配置失败:', err)
  } finally {
    loading.value = false
  }
}

async function loadAiConfig() {
  aiConfigLoading.value = true
  try {
    const res = await getXianyuChatAiConfig()
    const data = res.data || null
    if (data?.providers) {
      data.providers = data.providers.map((p: any) => {
        if (!p.models?.length && p.model) {
          p.models = [p.model]
        }
        if (!p.active_model) {
          p.active_model = p.models?.[0] || p.model || ''
        }
        return p
      })
    }
    aiConfig.value = data
    keepaliveIntervalSeconds.value = data?.chat_keepalive_interval_seconds || 180
  } catch (err) {
    console.error('获取AI配置失败:', err)
  } finally {
    aiConfigLoading.value = false
  }
}

async function handleSaveDyCookie() {
  if (!dyCookieInput.value.trim()) {
    ElMessage.warning('请输入Cookie')
    return
  }

  dySaving.value = true
  try {
    await updateDyCookie(dyCookieInput.value.trim())
    ElMessage.success('抖音Cookie更新成功')
    dyCookieInput.value = ''
    await loadCookieSettings()
  } catch (err: any) {
    ElMessage.error(err.message || '更新失败')
  } finally {
    dySaving.value = false
  }
}

async function handleSaveLiveCookie() {
  if (!liveCookieInput.value.trim()) {
    ElMessage.warning('请输入Cookie')
    return
  }

  liveSaving.value = true
  try {
    await updateLiveCookie(liveCookieInput.value.trim())
    ElMessage.success('直播Cookie更新成功')
    liveCookieInput.value = ''
    await loadCookieSettings()
  } catch (err: any) {
    ElMessage.error(err.message || '更新失败')
  } finally {
    liveSaving.value = false
  }
}

async function handleSaveXianyuCookie() {
  if (!xianyuCookieInput.value.trim()) {
    ElMessage.warning('请输入Cookie')
    return
  }

  xianyuSaving.value = true
  try {
    await updateXianyuCookie(xianyuCookieInput.value.trim())
    ElMessage.success('闲鱼Cookie更新成功')
    xianyuCookieInput.value = ''
    await loadCookieSettings()
  } catch (err: any) {
    ElMessage.error(err.message || '更新失败')
  } finally {
    xianyuSaving.value = false
  }
}

async function handleSaveQuarkCookie() {
  if (!quarkCookieInput.value.trim()) {
    ElMessage.warning('请输入Cookie')
    return
  }

  quarkSaving.value = true
  try {
    await updateQuarkCookie(quarkCookieInput.value.trim())
    ElMessage.success('夸克Cookie更新成功')
    quarkCookieInput.value = ''
    await loadCookieSettings()
  } catch (err: any) {
    ElMessage.error(err.message || '更新失败')
  } finally {
    quarkSaving.value = false
  }
}

async function handleToggleAiEnabled(enabled: boolean) {
  try {
    const res = await setXianyuChatAiEnabled(enabled)
    aiConfig.value = res.data
    keepaliveIntervalSeconds.value = res.data?.chat_keepalive_interval_seconds || keepaliveIntervalSeconds.value
    ElMessage.success(enabled ? 'AI 已启用' : 'AI 已关闭')
  } catch (err: any) {
    ElMessage.error(err.message || '操作失败')
  }
}

async function handleSaveKeepaliveInterval() {
  aiKeepaliveSaving.value = true
  try {
    const res = await setXianyuChatKeepaliveInterval(keepaliveIntervalSeconds.value)
    aiConfig.value = res.data
    keepaliveIntervalSeconds.value = res.data?.chat_keepalive_interval_seconds || keepaliveIntervalSeconds.value
    ElMessage.success('聊天保活间隔已更新')
  } catch (err: any) {
    ElMessage.error(err.message || '保存失败')
  } finally {
    aiKeepaliveSaving.value = false
  }
}

async function handleSetActiveProvider(providerId: string) {
  try {
    await setActiveXianyuChatAiProvider(providerId)
    await loadAiConfig()
    ElMessage.success('已切换供应商')
  } catch (err: any) {
    ElMessage.error(err.message || '切换失败')
  }
}

async function handleSetActiveModel(providerId: string, model: string) {
  try {
    await setXianyuChatAiProviderActiveModel(providerId, model)
    await loadAiConfig()
  } catch (err: any) {
    ElMessage.error(err.message || '切换模型失败')
  }
}

function openCreateProviderDialog() {
  editingProvider.value = null
  apiKeyConfigured.value = false
  newModelInput.value = ''
  providerForm.value = {
    name: '',
    base_url: 'https://api.openai.com/v1',
    api_key: '',
    models: ['gpt-4o-mini'],
    active_model: 'gpt-4o-mini',
    system_prompt: '你是闲鱼客服助手，回复要简洁、礼貌、像真人卖家。',
  }
  showProviderDialog.value = true
}

async function openEditProviderDialog(provider: XianyuChatAiProvider) {
  editingProvider.value = provider
  apiKeyConfigured.value = provider.api_key_configured
  newModelInput.value = ''
  providerForm.value = {
    name: provider.name,
    base_url: provider.base_url,
    api_key: '',
    models: [...(provider.models || [])],
    active_model: provider.active_model || (provider.models?.[0] || ''),
    system_prompt: provider.system_prompt,
  }
  showProviderDialog.value = true
  if (provider.api_key_configured) {
    try {
      const res = await getXianyuChatAiProviderApiKey(provider.id)
      if (res.data?.api_key) {
        providerForm.value.api_key = res.data.api_key
      }
    } catch {
      // ignore
    }
  }
}

function addModel() {
  const m = newModelInput.value.trim()
  if (!m) return
  if (providerForm.value.models.includes(m)) {
    ElMessage.warning('模型已存在')
    return
  }
  providerForm.value.models.push(m)
  if (!providerForm.value.active_model) {
    providerForm.value.active_model = m
  }
  newModelInput.value = ''
}

function removeModel(index: number) {
  const removed = providerForm.value.models.splice(index, 1)
  if (providerForm.value.active_model === removed[0]) {
    providerForm.value.active_model = providerForm.value.models[0] || ''
  }
}

function removeActiveModel() {
  const idx = providerForm.value.models.indexOf(providerForm.value.active_model)
  if (idx >= 0) {
    providerForm.value.models.splice(idx, 1)
  }
  providerForm.value.active_model = providerForm.value.models[0] || ''
}

async function handleSaveProvider() {
  if (!providerForm.value.name.trim()) {
    ElMessage.warning('请输入供应商名称')
    return
  }
  if (!providerForm.value.base_url.trim()) {
    ElMessage.warning('请输入 Base URL')
    return
  }
  if (!providerForm.value.models.length) {
    ElMessage.warning('请至少添加一个模型')
    return
  }

  try {
    if (editingProvider.value) {
      const payload: Record<string, any> = {
        name: providerForm.value.name.trim(),
        base_url: providerForm.value.base_url.trim(),
        models: providerForm.value.models,
        active_model: providerForm.value.active_model || providerForm.value.models[0],
        system_prompt: providerForm.value.system_prompt.trim(),
      }
      const apiKey = providerForm.value.api_key.trim()
      if (apiKey) {
        payload.api_key = apiKey
      }
      await updateXianyuChatAiProvider(editingProvider.value.id, payload)
      ElMessage.success('供应商已更新')
    } else {
      await createXianyuChatAiProvider({
        name: providerForm.value.name.trim(),
        base_url: providerForm.value.base_url.trim(),
        api_key: providerForm.value.api_key.trim(),
        models: providerForm.value.models,
        active_model: providerForm.value.active_model || providerForm.value.models[0],
        system_prompt: providerForm.value.system_prompt.trim(),
      })
      ElMessage.success('供应商已创建')
    }
    showProviderDialog.value = false
    await loadAiConfig()
  } catch (err: any) {
    ElMessage.error(err.message || '保存失败')
  }
}

async function handleTestProvider() {
  if (!providerForm.value.base_url.trim()) {
    ElMessage.warning('请输入 Base URL')
    return
  }
  if (!providerForm.value.models.length) {
    ElMessage.warning('请至少添加一个模型')
    return
  }
  if (!editingProvider.value && !providerForm.value.api_key.trim()) {
    ElMessage.warning('请输入 API Key')
    return
  }

  providerTesting.value = true
  try {
    const res = await testXianyuChatAiProvider({
      name: providerForm.value.name.trim() || '测试供应商',
      base_url: providerForm.value.base_url.trim(),
      api_key: providerForm.value.api_key.trim(),
      models: providerForm.value.models,
      active_model: providerForm.value.active_model || providerForm.value.models[0],
      system_prompt: providerForm.value.system_prompt.trim(),
      provider_id: editingProvider.value?.id || '',
    })
    ElMessage.success(`AI 回复: ${res.data?.reply || '无回复'}`)
  } catch (err: any) {
    ElMessage.error(err.message || '测试失败')
  } finally {
    providerTesting.value = false
  }
}

async function handleDeleteProvider(provider: XianyuChatAiProvider) {
  try {
    await ElMessageBox.confirm(`确定删除供应商「${provider.name}」吗？`, '确认删除', {
      type: 'warning',
    })
    await deleteXianyuChatAiProvider(provider.id)
    ElMessage.success('供应商已删除')
    await loadAiConfig()
  } catch (err: any) {
    if (err !== 'cancel') {
      ElMessage.error(err.message || '删除失败')
    }
  }
}

async function handleTestAi() {
  aiTesting.value = true
  try {
    const res = await testXianyuChatAi({ text: '你好，请简单介绍一下你自己。' })
    ElMessage.success(`AI 回复: ${res.data?.reply || '无回复'}`)
  } catch (err: any) {
    ElMessage.error(err.message || '测试失败')
  } finally {
    aiTesting.value = false
  }
}
</script>

<template>
  <div v-loading="loading" class="settings-page max-w-5xl mx-auto">
    <el-tabs v-model="activeTab" class="settings-tabs">
      <el-tab-pane label="Cookies 管理" name="cookies">
        <div class="settings-panel">
          <div class="panel-summary">
            <div class="summary-chip">
              <span class="summary-chip__label">抖音</span>
              <el-tag :type="dyConfigured ? 'success' : 'danger'" size="small">
                {{ dyConfigured ? '已配置' : '未配置' }}
              </el-tag>
            </div>
            <div class="summary-chip">
              <span class="summary-chip__label">闲鱼</span>
              <el-tag :type="xianyuConfigured ? 'success' : 'danger'" size="small">
                {{ xianyuConfigured ? '已配置' : '未配置' }}
              </el-tag>
            </div>
            <div class="summary-chip">
              <span class="summary-chip__label">夸克</span>
              <el-tag :type="quarkFallbackConfigured ? 'success' : 'warning'" size="small">
                {{ quarkFallbackConfigured ? '已配置' : '未配置' }}
              </el-tag>
            </div>
          </div>

          <div class="section-card">
            <div class="section-card__head">
              <div>
                <h3>抖音 Cookie</h3>
                <p>用于作品查询、用户查询、全能搜索等功能。</p>
              </div>
            </div>

            <div class="config-grid">
              <div class="config-item">
                <div class="config-item__head">
                  <label>抖音 Cookie</label>
                  <el-tag :type="dyConfigured ? 'success' : 'danger'" size="small">
                    {{ dyConfigured ? '已配置' : '未配置' }}
                  </el-tag>
                </div>
                <p class="config-item__desc">用于作品查询、用户查询、全能搜索等功能。</p>
                <el-input
                  v-model="dyCookieInput"
                  type="textarea"
                  :rows="4"
                  placeholder="请粘贴抖音 Cookie..."
                  class="cookie-input"
                />
                <div class="config-actions">
                  <el-button
                    type="primary"
                    size="small"
                    :loading="dySaving"
                    @click="handleSaveDyCookie"
                  >
                    保存
                  </el-button>
                  <el-button size="small" @click="dyCookieInput = ''">
                    清空
                  </el-button>
                </div>
              </div>

              <div class="config-item">
                <div class="config-item__head">
                  <label>直播 Cookie</label>
                  <el-tag :type="liveConfigured ? 'success' : 'info'" size="small">
                    {{ liveConfigured ? '已配置' : '可选' }}
                  </el-tag>
                </div>
                <p class="config-item__desc">用于直播间查询和直播数据获取，可按需配置。</p>
                <el-input
                  v-model="liveCookieInput"
                  type="textarea"
                  :rows="4"
                  placeholder="请粘贴直播 Cookie（可选）..."
                  class="cookie-input"
                />
                <div class="config-actions">
                  <el-button
                    type="primary"
                    size="small"
                    :loading="liveSaving"
                    @click="handleSaveLiveCookie"
                  >
                    保存
                  </el-button>
                  <el-button size="small" @click="liveCookieInput = ''">
                    清空
                  </el-button>
                </div>
              </div>
            </div>
          </div>

          <div class="section-card">
            <div class="section-card__head">
              <div>
                <h3>闲鱼 Cookie</h3>
                <p>用于闲鱼搜索、筛选和聊天功能。</p>
              </div>
            </div>

            <div class="config-grid">
              <div class="config-item">
                <div class="config-item__head">
                  <label>闲鱼 Cookie</label>
                  <el-tag :type="xianyuConfigured ? 'success' : 'danger'" size="small">
                    {{ xianyuConfigured ? '已配置' : '未配置' }}
                  </el-tag>
                </div>
                <p class="config-item__desc">用于闲鱼搜索、筛选和聊天功能，建议从浏览器已登录状态完整复制。</p>
                <el-input
                  v-model="xianyuCookieInput"
                  type="textarea"
                  :rows="4"
                  placeholder="请粘贴闲鱼 Cookie..."
                  class="cookie-input"
                />
                <div class="config-actions">
                  <el-button
                    type="primary"
                    size="small"
                    :loading="xianyuSaving"
                    @click="handleSaveXianyuCookie"
                  >
                    保存
                  </el-button>
                  <el-button size="small" @click="xianyuCookieInput = ''">
                    清空
                  </el-button>
                </div>
              </div>
            </div>
          </div>

          <div class="section-card">
            <div class="section-card__head">
              <div>
                <h3>夸克 Cookie</h3>
                <p>用于夸克网盘相关功能。</p>
              </div>
            </div>

            <div class="config-grid">
              <div class="config-item">
                <div class="config-item__head">
                  <label>夸克 Cookie</label>
                  <el-tag :type="quarkFallbackConfigured ? 'success' : 'warning'" size="small">
                    {{ quarkFallbackConfigured ? '已配置' : '未配置' }}
                  </el-tag>
                </div>
                <p class="config-item__desc">用于夸克网盘相关功能，建议从浏览器已登录状态完整复制。</p>
                <el-input
                  v-model="quarkCookieInput"
                  type="textarea"
                  :rows="4"
                  placeholder="请粘贴夸克 Cookie..."
                  class="cookie-input"
                />
                <div class="config-actions">
                  <el-button
                    type="primary"
                    size="small"
                    :loading="quarkSaving"
                    @click="handleSaveQuarkCookie"
                  >
                    保存
                  </el-button>
                  <el-button size="small" @click="quarkCookieInput = ''">
                    清空
                  </el-button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane label="AI 配置" name="ai">
        <div class="settings-panel">
          <div class="section-card">
            <div class="section-card__head">
              <div>
                <h3>闲鱼聊天 AI 助手</h3>
                <p>配置 AI 模型用于闲鱼聊天自动回复功能，支持多供应商管理。</p>
              </div>
            </div>

            <div v-loading="aiConfigLoading" class="ai-config-content">
              <div class="ai-global-toggle">
                <label class="ai-switch" :class="{ 'is-on': aiConfig?.enabled }">
                  <input
                    type="checkbox"
                    :checked="aiConfig?.enabled"
                    @change="handleToggleAiEnabled(!aiConfig?.enabled)"
                  >
                  <span class="ai-switch__slider" />
                  <span class="ai-switch__label">AI {{ aiConfig?.enabled ? '已启用' : '已关闭' }}</span>
                </label>
                <el-button
                  :loading="aiTesting"
                  :disabled="!aiConfig?.providers?.length"
                  @click="handleTestAi"
                >
                  测试回复
                </el-button>
              </div>

              <div class="ai-runtime-card">
                <div class="ai-runtime-card__info">
                  <h4>聊天保活</h4>
                  <p>参考 XianYuApis，定时刷新聊天登录态。间隔越短越稳，但请求会更频繁。</p>
                </div>
                <div class="ai-runtime-card__actions">
                  <el-input-number
                    v-model="keepaliveIntervalSeconds"
                    :min="30"
                    :max="3600"
                    :step="30"
                  />
                  <span class="ai-runtime-card__suffix">秒</span>
                  <el-button
                    type="primary"
                    :loading="aiKeepaliveSaving"
                    @click="handleSaveKeepaliveInterval"
                  >
                    保存
                  </el-button>
                </div>
              </div>

              <div class="ai-providers">
                <div class="ai-providers__header">
                  <h4>供应商列表</h4>
                  <el-button type="primary" size="small" :icon="Plus" @click="openCreateProviderDialog">
                    添加供应商
                  </el-button>
                </div>

                <div v-if="!aiConfig?.providers?.length" class="ai-providers__empty">
                  <p>暂无供应商，点击上方按钮添加</p>
                </div>

                <div v-else class="ai-provider-list">
                  <div
                    v-for="provider in aiConfig?.providers"
                    :key="provider.id"
                    class="ai-provider-card"
                    :class="{ 'is-active': provider.is_active }"
                  >
                    <div class="ai-provider-card__main">
                      <div class="ai-provider-card__info">
                        <div class="ai-provider-card__name">
                          {{ provider.name }}
                          <el-tag v-if="provider.is_active" type="success" size="small">
                            当前使用
                          </el-tag>
                        </div>
                        <div class="ai-provider-card__meta">
                          <el-select
                            v-if="provider.models?.length"
                            :model-value="provider.active_model || provider.models[0]"
                            size="small"
                            class="model-select"
                            popper-class="dark-select-dropdown"
                            @change="(m: string) => handleSetActiveModel(provider.id, m)"
                          >
                            <el-option
                              v-for="m in provider.models"
                              :key="m"
                              :label="m"
                              :value="m"
                            />
                          </el-select>
                          <span v-else>未设置模型</span>
                          <span class="ai-provider-card__divider">|</span>
                          <span>{{ provider.base_url }}</span>
                        </div>
                        <div v-if="provider.api_key_configured" class="ai-provider-card__key">
                          API Key: {{ provider.api_key_masked }}
                        </div>
                        <div v-else class="ai-provider-card__key ai-provider-card__key--empty">
                          API Key: 未配置
                        </div>
                      </div>
                    </div>
                    <div class="ai-provider-card__actions">
                      <el-button
                        v-if="!provider.is_active"
                        type="success"
                        size="small"
                        :icon="Check"
                        @click="handleSetActiveProvider(provider.id)"
                      >
                        使用
                      </el-button>
                      <el-button size="small" :icon="Edit" @click="openEditProviderDialog(provider)">
                        编辑
                      </el-button>
                      <el-button
                        type="danger"
                        size="small"
                        :icon="Delete"
                        :disabled="aiConfig?.providers?.length <= 1"
                        @click="handleDeleteProvider(provider)"
                      >
                        删除
                      </el-button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>

    <el-dialog
      v-model="showProviderDialog"
      :title="editingProvider ? '编辑供应商' : '添加供应商'"
      width="520px"
      :close-on-click-modal="false"
    >
      <el-form label-width="100px">
        <el-form-item label="名称">
          <el-input v-model="providerForm.name" placeholder="如 OpenAI、DeepSeek" />
        </el-form-item>
        <el-form-item label="Base URL">
          <el-input v-model="providerForm.base_url" placeholder="如 https://api.openai.com/v1" />
        </el-form-item>
        <el-form-item label="API Key">
          <el-input
            v-model="providerForm.api_key"
            show-password
            :placeholder="apiKeyConfigured ? '已配置，留空保留原值，输入则更新' : '请输入 API Key'"
          />
        </el-form-item>
        <el-form-item label="模型">
          <div class="model-manager">
            <el-select
              v-model="providerForm.active_model"
              placeholder="选择模型"
              class="model-select-full"
              popper-class="dark-select-dropdown"
            >
              <el-option
                v-for="m in providerForm.models"
                :key="m"
                :label="m"
                :value="m"
              />
            </el-select>
            <div class="model-add-row">
              <el-input
                v-model="newModelInput"
                placeholder="输入新模型名称，如 gpt-4o"
                size="small"
                @keyup.enter="addModel"
              />
              <el-button size="small" type="primary" @click="addModel">添加</el-button>
              <el-button
                v-if="providerForm.active_model"
                size="small"
                type="danger"
                @click="removeActiveModel"
              >
                删除当前
              </el-button>
            </div>
          </div>
        </el-form-item>
        <el-form-item label="系统提示词">
          <el-input
            v-model="providerForm.system_prompt"
            type="textarea"
            :rows="4"
            placeholder="设置 AI 助手的角色和行为..."
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showProviderDialog = false">取消</el-button>
        <el-button :loading="providerTesting" @click="handleTestProvider">测试</el-button>
        <el-button type="primary" @click="handleSaveProvider">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.settings-page {
  color: rgb(var(--app-text-rgb));
}

.settings-tabs {
  margin-bottom: 20px;
}

.settings-tabs :deep(.el-tabs__header) {
  margin-bottom: 20px;
}

.settings-tabs :deep(.el-tabs__nav-wrap::after) {
  display: none;
}

.settings-tabs :deep(.el-tabs__item) {
  font-size: 15px;
  font-weight: 600;
  padding: 0 24px;
}

.settings-panel {
  display: grid;
  gap: 18px;
}

.panel-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.summary-chip {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 999px;
  background-color: rgba(var(--app-surface-rgb) / 0.96);
  border: 1px solid rgba(var(--app-border-rgb) / 0.7);
}

.summary-chip__label {
  color: rgb(var(--app-text-rgb));
  font-size: 13px;
  font-weight: 600;
}

.section-card {
  padding: 20px;
  border-radius: 14px;
  background: rgba(var(--app-surface-alt-rgb) / 0.88);
  border: 1px solid rgba(var(--app-border-rgb) / 0.55);
}

.section-card__head h3 {
  margin: 0 0 6px;
  color: rgb(var(--app-text-strong-rgb));
  font-size: 18px;
}

.section-card__head p {
  margin: 0;
  color: rgb(var(--app-text-muted-rgb));
  font-size: 13px;
  line-height: 1.7;
}

.config-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  margin-top: 16px;
}

.config-item {
  padding: 16px;
  background-color: rgba(var(--app-surface-rgb) / 0.78);
  border-radius: 12px;
  border: 1px solid rgba(var(--app-border-rgb) / 0.45);
}

.config-item__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.config-item__head label {
  color: rgb(var(--app-text-strong-rgb));
  font-size: 14px;
  font-weight: 600;
}

.config-item__desc {
  margin: 0 0 10px;
  color: rgb(var(--app-text-muted-rgb));
  font-size: 12px;
  line-height: 1.7;
}

.config-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.cookie-input :deep(.el-textarea__inner) {
  background-color: rgba(var(--app-bg-rgb) / 0.92) !important;
  border-color: rgba(var(--app-border-rgb) / 0.8) !important;
  color: rgb(var(--app-text-strong-rgb)) !important;
  font-family: monospace;
  font-size: 12px;
}

.cookie-input :deep(.el-textarea__inner:focus) {
  border-color: var(--primary-color) !important;
}

.ai-config-content {
  margin-top: 16px;
}

.ai-global-toggle {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
}

.ai-switch {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 10px 18px;
  border-radius: 12px;
  background: rgba(var(--app-surface-rgb) / 0.9);
  border: 1px solid rgba(var(--app-border-rgb) / 0.5);
  cursor: pointer;
  transition: all 0.2s ease;
  user-select: none;
}

.ai-switch:hover {
  border-color: rgba(var(--app-accent-rgb) / 0.4);
}

.ai-switch input {
  display: none;
}

.ai-switch__slider {
  position: relative;
  width: 40px;
  height: 22px;
  border-radius: 11px;
  background: rgba(var(--app-border-rgb) / 0.4);
  transition: all 0.2s ease;
}

.ai-switch__slider::after {
  content: '';
  position: absolute;
  top: 2px;
  left: 2px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: white;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
  transition: all 0.2s ease;
}

.ai-switch.is-on .ai-switch__slider {
  background: linear-gradient(135deg, rgb(99, 102, 241), rgb(139, 92, 246));
}

.ai-switch.is-on .ai-switch__slider::after {
  left: 20px;
}

.ai-switch__label {
  font-size: 14px;
  font-weight: 600;
  color: rgb(var(--app-text-rgb));
}

.ai-switch.is-on .ai-switch__label {
  color: rgb(99, 102, 241);
}

.ai-runtime-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
  padding: 16px;
  border-radius: 12px;
  background: rgba(var(--app-surface-rgb) / 0.8);
  border: 1px solid rgba(var(--app-border-rgb) / 0.4);
}

.ai-runtime-card__info h4 {
  margin: 0 0 6px;
  font-size: 15px;
  color: rgb(var(--app-text-strong-rgb));
}

.ai-runtime-card__info p {
  margin: 0;
  font-size: 13px;
  color: rgb(var(--app-text-muted-rgb));
}

.ai-runtime-card__actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.ai-runtime-card__suffix {
  color: rgb(var(--app-text-muted-rgb));
  font-size: 13px;
}

.ai-providers__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.ai-providers__header h4 {
  margin: 0;
  font-size: 15px;
  color: rgb(var(--app-text-strong-rgb));
}

.ai-providers__empty {
  padding: 40px 20px;
  text-align: center;
  color: rgb(var(--app-text-muted-rgb));
  background: rgba(var(--app-surface-rgb) / 0.5);
  border-radius: 12px;
  border: 1px dashed rgba(var(--app-border-rgb) / 0.5);
}

.ai-provider-list {
  display: grid;
  gap: 12px;
}

.ai-provider-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px;
  background: rgba(var(--app-surface-rgb) / 0.8);
  border-radius: 12px;
  border: 1px solid rgba(var(--app-border-rgb) / 0.4);
  transition: all 0.2s ease;
}

.ai-provider-card:hover {
  border-color: rgba(var(--app-accent-rgb) / 0.3);
}

.ai-provider-card.is-active {
  border-color: rgba(99, 102, 241, 0.4);
  background: rgba(99, 102, 241, 0.05);
}

.ai-provider-card__main {
  flex: 1;
  min-width: 0;
}

.ai-provider-card__name {
  font-size: 15px;
  font-weight: 600;
  color: rgb(var(--app-text-strong-rgb));
  display: flex;
  align-items: center;
  gap: 8px;
}

.ai-provider-card__meta {
  margin-top: 4px;
  font-size: 12px;
  color: rgb(var(--app-text-muted-rgb));
}

.ai-provider-card__divider {
  margin: 0 8px;
  opacity: 0.5;
}

.ai-provider-card__key {
  margin-top: 6px;
  font-size: 12px;
  font-family: monospace;
  color: rgb(var(--app-text-subtle-rgb));
}

.ai-provider-card__key--empty {
  color: rgb(239, 68, 68);
}

.ai-provider-card__actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.api-key-toggle {
  cursor: pointer;
  color: rgb(var(--app-text-muted-rgb));
  font-size: 16px;
  transition: color 0.2s ease;
}

.api-key-toggle:hover {
  color: rgb(var(--app-text-strong-rgb));
}

.model-manager {
  width: 100%;
}

.model-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
  min-height: 28px;
}

.model-tags .el-tag {
  cursor: pointer;
}

.model-empty {
  font-size: 12px;
  color: rgb(var(--app-text-muted-rgb));
}

.model-add-row {
  display: flex;
  gap: 8px;
}

.model-add-row .el-input {
  flex: 1;
}

.model-hint {
  margin: 6px 0 0;
  font-size: 11px;
  color: rgb(var(--app-text-muted-rgb));
}

.model-select {
  width: auto;
  min-width: 120px;
}

.model-select-full {
  width: 100%;
  margin-bottom: 8px;
}

@media (max-width: 900px) {
  .config-grid {
    grid-template-columns: 1fr;
  }

  .ai-runtime-card {
    flex-direction: column;
    align-items: stretch;
  }

  .ai-provider-card {
    flex-direction: column;
    align-items: stretch;
  }

  .ai-provider-card__actions {
    justify-content: flex-end;
  }
}
</style>

<style>
.ai-provider-card .el-select .el-select__wrapper,
.ai-provider-card .el-select .el-input__wrapper {
  background-color: rgba(var(--app-surface-rgb) / 0.6) !important;
  box-shadow: 0 0 0 1px rgba(var(--app-border-rgb) / 0.3) inset !important;
}

.ai-provider-card .el-select .el-select__placeholder,
.ai-provider-card .el-select .el-input__inner,
.ai-provider-card .el-select .el-select__selected-item span {
  color: rgb(var(--app-text-strong-rgb)) !important;
}

.el-dialog .model-select-full .el-select__wrapper,
.el-dialog .model-select-full .el-input__wrapper {
  background-color: rgba(var(--app-surface-rgb) / 0.6) !important;
  box-shadow: 0 0 0 1px rgba(var(--app-border-rgb) / 0.3) inset !important;
}

.el-dialog .model-select-full .el-select__placeholder,
.el-dialog .model-select-full .el-input__inner,
.el-dialog .model-select-full .el-select__selected-item span {
  color: rgb(var(--app-text-strong-rgb)) !important;
}
</style>
