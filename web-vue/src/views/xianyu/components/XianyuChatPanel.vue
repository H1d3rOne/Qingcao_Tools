<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { RefreshRight } from '@element-plus/icons-vue'
import {
  clearXianyuChatRedPoint,
  createXianyuChatWebSocket,
  getXianyuChatAiConfig,
  getXianyuChatAiSessions,
  getXianyuChatConversations,
  getXianyuChatMessages,
  getXianyuChatProfile,
  markXianyuChatRead,
  recallXianyuChatMessage,
  sendXianyuChatMessage,
  testXianyuChatAi,
  updateXianyuChatAiConfig,
  updateXianyuChatAiSession,
  uploadAndSendXianyuChatImage,
  type XianyuChatAiConfig,
  type XianyuChatAiSessionState,
  type XianyuChatConversation,
  type XianyuChatMessage,
  type XianyuChatProfile,
  type XianyuChatPushEvent,
  type XianyuUserProfile,
} from '@/api/modules/xianyu'
import XianyuChatAiConfigDialog from './XianyuChatAiConfigDialog.vue'

type EditableXianyuChatAiConfig = XianyuChatAiConfig & { api_key: string }

const props = defineProps<{
  currentUser?: XianyuUserProfile | null
  preferredCid?: string
}>()

const chatProfile = ref<XianyuChatProfile | null>(null)
const profileLoading = ref(false)
const conversationLoading = ref(false)
const messageLoading = ref(false)
const sending = ref(false)
const uploadingImage = ref(false)
const sessions = ref<XianyuChatConversation[]>([])
const activeCid = ref('')
const messages = ref<XianyuChatMessage[]>([])
const messageCursor = ref<string | null>(null)
const hasMoreMessages = ref(false)
const sessionKeyword = ref('')
const composer = ref('')
const connectionStatus = ref<'connecting' | 'connected' | 'disconnected' | 'error'>('connecting')
const messageStreamRef = ref<HTMLElement | null>(null)
const pendingPreferredCid = ref('')
const imageInputRef = ref<HTMLInputElement | null>(null)
const contextMenu = ref<{ visible: boolean; x: number; y: number; message: XianyuChatMessage | null }>({
  visible: false,
  x: 0,
  y: 0,
  message: null,
})
const chatAiConfig = ref<EditableXianyuChatAiConfig | null>(null)
const chatAiConfigDialogVisible = ref(false)
const chatAiConfigSaving = ref(false)
const chatAiTesting = ref(false)
const sessionAiStateMap = ref<Record<string, boolean>>({})

let wsClient: ReturnType<typeof createXianyuChatWebSocket> | null = null
let refreshTimer: number | null = null
let syncTimer: number | null = null

const currentAccount = computed(() => {
  if (props.currentUser) {
    return {
      display_name: props.currentUser.display_name,
      avatar: props.currentUser.avatar,
      user_id: chatProfile.value?.main_user_id || chatProfile.value?.user_id || '',
    }
  }

  return {
    display_name: chatProfile.value?.display_name || '闲鱼账号',
    avatar: chatProfile.value?.avatar || '',
    user_id: chatProfile.value?.main_user_id || chatProfile.value?.user_id || '',
  }
})

const filteredSessions = computed(() => {
  const keyword = sessionKeyword.value.trim().toLowerCase()
  const list = sessions.value
    .filter((item) => item.visible)
    .sort((a, b) => {
      if (b.top_rank !== a.top_rank) return b.top_rank - a.top_rank
      return b.last_message_time - a.last_message_time
    })

  if (!keyword) return list

  return list.filter((item) => {
    return [
      item.title,
      item.item_title,
      item.last_message_summary,
      item.peer_user_id,
    ].some((value) => value.toLowerCase().includes(keyword))
  })
})

const activeSession = computed(() => sessions.value.find((item) => item.cid === activeCid.value) || null)
const canSendCurrentSession = computed(() => Boolean(activeSession.value?.can_send))
const currentSessionAiEnabled = computed(() => Boolean(activeCid.value && sessionAiStateMap.value[activeCid.value]))
const connectionLabel = computed(() => {
  switch (connectionStatus.value) {
    case 'connected':
      return '实时在线'
    case 'connecting':
      return '连接中'
    case 'error':
      return '连接异常'
    default:
      return '已断开'
  }
})

async function loadChatAiConfig() {
  try {
    const response = await getXianyuChatAiConfig()
    chatAiConfig.value = {
      ...response.data,
      api_key: '',
    }
  } catch {
    chatAiConfig.value = null
  }
}

async function loadChatAiSessionStates() {
  const cids = sessions.value.map((item) => item.cid).filter(Boolean)
  if (!cids.length) {
    sessionAiStateMap.value = {}
    return
  }

  try {
    const response = await getXianyuChatAiSessions(cids)
    const states: XianyuChatAiSessionState[] = response.data || []
    sessionAiStateMap.value = Object.fromEntries(states.map((item) => [item.cid, item.enabled]))
  } catch {
    sessionAiStateMap.value = {}
  }
}

function buildChatAiConfigPayload(payload: EditableXianyuChatAiConfig) {
  return {
    enabled: payload.enabled,
    base_url: payload.base_url,
    api_key: payload.api_key,
    model: payload.model,
    system_prompt: payload.system_prompt,
    temperature: payload.temperature,
  }
}

async function persistChatAiConfig(
  payload: EditableXianyuChatAiConfig,
  options: { closeDialog?: boolean; successMessage?: string } = {},
) {
  chatAiConfigSaving.value = true
  try {
    const response = await updateXianyuChatAiConfig(buildChatAiConfigPayload(payload))
    chatAiConfig.value = {
      ...response.data,
      api_key: '',
    }
    if (options.closeDialog ?? true) {
      chatAiConfigDialogVisible.value = false
    }
    if (options.successMessage) {
      ElMessage.success(options.successMessage)
    }
  } finally {
    chatAiConfigSaving.value = false
  }
}

async function saveChatAiConfig(payload: EditableXianyuChatAiConfig) {
  await persistChatAiConfig(payload, {
    closeDialog: true,
    successMessage: 'AI 配置已保存',
  })
}

async function handleTestChatAi() {
  chatAiTesting.value = true
  try {
    const sampleText = activeCid.value && activeSession.value
      ? `${activeSession.value.item_title || '当前商品'}，这个还在吗？`
      : '你好，在吗？'
    const response = await testXianyuChatAi({
      text: sampleText,
      cid: activeCid.value || undefined,
    })
    ElMessage.success(`测试成功：${response.data.reply}`)
  } finally {
    chatAiTesting.value = false
  }
}

async function handleToggleGlobalAi(enabled: string | number | boolean) {
  if (!chatAiConfig.value) return
  const nextEnabled = Boolean(enabled)
  await persistChatAiConfig(
    {
      ...chatAiConfig.value,
      enabled: nextEnabled,
      api_key: '',
    },
    {
      closeDialog: false,
      successMessage: nextEnabled ? '已开启 AI 总开关' : '已关闭 AI 总开关',
    },
  )
}

async function handleToggleCurrentSessionAi(enabled: string | number | boolean) {
  if (!activeCid.value) return
  const nextEnabled = Boolean(enabled)
  await updateXianyuChatAiSession(activeCid.value, { enabled: nextEnabled })
  sessionAiStateMap.value = {
    ...sessionAiStateMap.value,
    [activeCid.value]: nextEnabled,
  }
  ElMessage.success(nextEnabled ? '当前会话已启用 AI' : '当前会话已关闭 AI')
}

function connectChatSocket() {
  connectionStatus.value = 'connecting'
  wsClient?.disconnect()

  wsClient = createXianyuChatWebSocket({
    onConnected() {
      connectionStatus.value = 'connected'
    },
    onPush(event: XianyuChatPushEvent) {
      handlePushEvent(event)
    },
    onError(message) {
      connectionStatus.value = 'error'
      ElMessage.warning(message)
    },
    onDisconnected() {
      if (connectionStatus.value !== 'error') {
        connectionStatus.value = 'disconnected'
      }
    },
  })

  wsClient.connect()
}

function disconnectChatSocket() {
  wsClient?.disconnect()
  wsClient = null
}

function startSyncPolling() {
  stopSyncPolling()
  syncTimer = window.setInterval(async () => {
    if (conversationLoading.value || messageLoading.value || sending.value) return
    await loadConversations(false)
    if (activeCid.value) {
      await loadMessages(activeCid.value, null, 'replace')
    }
  }, 12000)
}

function stopSyncPolling() {
  if (syncTimer !== null) {
    clearInterval(syncTimer)
    syncTimer = null
  }
}

function scheduleRefresh() {
  if (refreshTimer !== null) {
    clearTimeout(refreshTimer)
  }

  refreshTimer = window.setTimeout(async () => {
    await loadConversations(false)
    if (activeCid.value) {
      await loadMessages(activeCid.value, null, 'replace')
    }
  }, 360)
}

function handlePushEvent(event: XianyuChatPushEvent) {
  const decoded = event.decoded
  const lwp = event.lwp || ''

  if (!decoded) {
    scheduleRefresh()
    return
  }

  if (decoded.type === 'sync' && decoded.items) {
    const hasNewMessage = decoded.items.some(
      (item) => item.biz_type === 40000 || item.biz_type === 40104 || item.biz_type === 40102
    )
    if (hasNewMessage) {
      scheduleRefresh()
    }
    return
  }

  if (decoded.type === 'kickout' && lwp === '/push/kickout') {
    connectionStatus.value = 'error'
    ElMessage.warning('闲鱼聊天连接被踢出，请重新登录')
    return
  }

  scheduleRefresh()
}

async function handleUploadImage() {
  if (!activeSession.value || !canSendCurrentSession.value || uploadingImage.value) return
  imageInputRef.value?.click()
}

async function handleImageSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file || !activeSession.value) return

  if (!file.type.startsWith('image/')) {
    ElMessage.warning('请选择图片文件')
    return
  }

  uploadingImage.value = true
  try {
    await uploadAndSendXianyuChatImage(activeSession.value.cid, file)
    await Promise.all([
      loadConversations(false),
      loadMessages(activeSession.value.cid, null, 'replace'),
    ])
    await scrollMessagesToBottom()
  } catch (err: any) {
    ElMessage.error(err?.message || '发送图片失败')
  } finally {
    uploadingImage.value = false
    input.value = ''
  }
}

async function handleRecallMessage(messageId: string) {
  try {
    await recallXianyuChatMessage(messageId)
    ElMessage.success('消息已撤回')
    if (activeCid.value) {
      await loadMessages(activeCid.value, null, 'replace')
    }
  } catch (err: any) {
    ElMessage.error(err?.message || '撤回失败')
  }
}

async function handleMarkRead() {
  if (!activeCid.value) return
  try {
    await markXianyuChatRead(activeCid.value)
  } catch {
    // ignore
  }
}

function handleBubbleContext(event: MouseEvent, message: XianyuChatMessage) {
  contextMenu.value = {
    visible: true,
    x: event.clientX,
    y: event.clientY,
    message,
  }
  document.addEventListener('click', closeContextMenu, { once: true })
}

function closeContextMenu() {
  contextMenu.value.visible = false
}

function handleContextRecall() {
  const msg = contextMenu.value.message
  closeContextMenu()
  if (msg && msg.direction === 'out' && msg.message_id) {
    handleRecallMessage(msg.message_id)
  }
}

function handleContextCopy() {
  const msg = contextMenu.value.message
  closeContextMenu()
  if (msg) {
    const text = msg.text || msg.summary || ''
    if (text) {
      navigator.clipboard.writeText(text).catch(() => {})
    }
  }
}

async function loadChatProfile() {
  profileLoading.value = true
  try {
    const response = await getXianyuChatProfile()
    chatProfile.value = response.data
  } catch {
    chatProfile.value = null
  } finally {
    profileLoading.value = false
  }
}

async function loadConversations(
  showLoading = true,
  options: { skipAutoSelect?: boolean } = {},
) {
  if (showLoading) {
    conversationLoading.value = true
  }

  try {
    const response = await getXianyuChatConversations({ offset: 0, limit: 40 })
    sessions.value = response.data.conversations || []
    await loadChatAiSessionStates()

    const preferredCid = pendingPreferredCid.value.trim()
    if (preferredCid) {
      const preferredSession = sessions.value.find((item) => item.cid === preferredCid)
      if (preferredSession) {
        pendingPreferredCid.value = ''
        if (activeCid.value !== preferredSession.cid) {
          await handleSelectSession(preferredSession)
        } else if (!messages.value.length) {
          await loadMessages(preferredSession.cid, null, 'replace')
        }
        return
      }
    }

    if (options.skipAutoSelect) return

    if (!activeCid.value || !sessions.value.some((item) => item.cid === activeCid.value)) {
      const firstSession = filteredSessions.value[0]
      if (firstSession) {
        activeCid.value = firstSession.cid
        await loadMessages(firstSession.cid, null, 'replace')
      }
    }
  } catch (err: any) {
    ElMessage.error(err?.message || '获取会话列表失败')
  } finally {
    conversationLoading.value = false
  }
}

async function loadMessages(
  cid: string,
  cursor: string | null = null,
  mode: 'replace' | 'prepend' = 'replace',
) {
  if (!cid) return

  messageLoading.value = true
  try {
    const response = await getXianyuChatMessages({
      cid,
      cursor,
      limit: 20,
      direction: 'prev',
    })
    const nextMessages = response.data.messages || []
    messages.value = mode === 'prepend'
      ? mergeMessages(nextMessages, messages.value)
      : mergeMessages(nextMessages)
    messageCursor.value = response.data.cursor || null
    hasMoreMessages.value = Boolean(response.data.has_more)
  } catch (err: any) {
    ElMessage.error(err?.message || '获取会话消息失败')
  } finally {
    messageLoading.value = false
    if (mode === 'replace') {
      await scrollMessagesToBottom()
    }
  }
}

function mergeMessages(incoming: XianyuChatMessage[], current: XianyuChatMessage[] = []) {
  const map = new Map<string, XianyuChatMessage>()
  for (const item of [...incoming, ...current]) {
    map.set(item.message_id, item)
  }

  return Array.from(map.values()).sort((a, b) => a.create_at - b.create_at)
}

async function handleSelectSession(session: XianyuChatConversation) {
  activeCid.value = session.cid
  await Promise.all([
    loadMessages(session.cid, null, 'replace'),
    clearChatRedPoint(session.cid),
    handleMarkRead(),
  ])
}

async function focusPreferredConversation(cid: string) {
  const normalizedCid = cid.trim()
  if (!normalizedCid) return

  let matched = sessions.value.find((item) => item.cid === normalizedCid)
  if (!matched) {
    await loadConversations(false, { skipAutoSelect: true })
    matched = sessions.value.find((item) => item.cid === normalizedCid)
  }
  if (!matched) return

  pendingPreferredCid.value = ''
  if (activeCid.value === matched.cid) {
    if (!messages.value.length) {
      await loadMessages(matched.cid, null, 'replace')
    }
    return
  }

  await handleSelectSession(matched)
}

async function clearChatRedPoint(cid: string) {
  try {
    await clearXianyuChatRedPoint([cid])
    sessions.value = sessions.value.map((item) => {
      if (item.cid !== cid) return item
      return { ...item, unread_count: 0, red_point: 0 }
    })
  } catch {
    // ignore
  }
}

async function handleLoadMoreMessages() {
  if (!activeCid.value || !messageCursor.value || messageLoading.value) return
  await loadMessages(activeCid.value, messageCursor.value, 'prepend')
}

async function handleSendMessage() {
  if (!activeSession.value || !canSendCurrentSession.value) return

  const text = composer.value.trim()
  if (!text) {
    ElMessage.warning('请输入消息内容')
    return
  }

  sending.value = true
  try {
    await sendXianyuChatMessage({
      cid: activeSession.value.cid,
      text,
    })
    composer.value = ''
    await Promise.all([
      loadConversations(false),
      loadMessages(activeSession.value.cid, null, 'replace'),
    ])
    await scrollMessagesToBottom()
  } catch (err: any) {
    ElMessage.error(err?.message || '发送消息失败')
  } finally {
    sending.value = false
  }
}

async function scrollMessagesToBottom() {
  await nextTick()
  if (!messageStreamRef.value) return
  messageStreamRef.value.scrollTop = messageStreamRef.value.scrollHeight
}

function formatMessageText(message: XianyuChatMessage) {
  return message.text || message.summary || '[暂不支持该消息展示]'
}

async function handleRefreshAll() {
  await Promise.all([
    loadChatProfile(),
    loadChatAiConfig(),
    loadConversations(false),
    activeCid.value ? loadMessages(activeCid.value, null, 'replace') : Promise.resolve(),
  ])
}

watch(
  () => props.preferredCid,
  async (cid) => {
    const normalizedCid = (cid || '').trim()
    if (!normalizedCid) return
    pendingPreferredCid.value = normalizedCid
    await focusPreferredConversation(normalizedCid)
  },
  { immediate: true }
)

onMounted(async () => {
  await Promise.all([loadChatProfile(), loadConversations(), loadChatAiConfig()])
  connectChatSocket()
  startSyncPolling()
})

onBeforeUnmount(() => {
  if (refreshTimer !== null) {
    clearTimeout(refreshTimer)
  }
  stopSyncPolling()
  disconnectChatSocket()
})
</script>

<template>
  <section class="chat-panel theme-surface-card">
    <div class="chat-shell">
      <aside class="chat-sidebar theme-surface-soft">
        <div class="chat-sidebar__account">
          <div class="chat-account">
            <img
              v-if="currentAccount.avatar"
              :src="currentAccount.avatar"
              :alt="currentAccount.display_name"
              class="chat-account__avatar"
            >
            <div
              v-else
              class="chat-account__avatar chat-account__avatar--placeholder"
            >
              {{ currentAccount.display_name.slice(0, 1) || '鱼' }}
            </div>

            <div class="chat-account__main">
              <strong>{{ currentAccount.display_name }}</strong>
              <span>{{ currentAccount.user_id || '账号识别中...' }}</span>
            </div>

            <div class="chat-account__ai-actions">
              <div
                class="chat-status"
                :class="`is-${connectionStatus}`"
              >
                {{ connectionLabel }}
              </div>
              <template v-if="chatAiConfig">
                <el-switch
                  :model-value="chatAiConfig.enabled"
                  inline-prompt
                  active-text="AI 总开"
                  inactive-text="AI 总关"
                  @change="handleToggleGlobalAi"
                />
                <el-switch
                  :model-value="currentSessionAiEnabled"
                  :disabled="!activeCid"
                  inline-prompt
                  active-text="会话 AI"
                  inactive-text="会话 AI"
                  @change="handleToggleCurrentSessionAi"
                />
                <el-button
                  size="small"
                  @click="chatAiConfigDialogVisible = true"
                >
                  AI 配置
                </el-button>
              </template>
            </div>
          </div>
        </div>

        <div class="chat-sidebar__header">
          <div>
            <strong>会话列表</strong>
            <span>{{ filteredSessions.length }} 个可见会话</span>
          </div>

          <el-button
            circle
            size="small"
            :loading="conversationLoading || profileLoading"
            @click="handleRefreshAll"
          >
            <el-icon><RefreshRight /></el-icon>
          </el-button>
        </div>

        <el-input
          v-model="sessionKeyword"
          class="chat-sidebar__search"
          placeholder="筛选会话、商品或用户"
          clearable
        />

        <div class="chat-session-list">
          <button
            v-for="session in filteredSessions"
            :key="session.cid"
            type="button"
            class="chat-session"
            :class="{ 'is-active': activeCid === session.cid }"
            @click="handleSelectSession(session)"
          >
            <div class="chat-session__cover">
              <img
                v-if="session.peer_avatar"
                :src="session.peer_avatar"
                :alt="session.title"
              >
              <div
                v-else
                class="chat-session__cover-placeholder"
              >
                {{ session.title.slice(0, 1) || '聊' }}
              </div>
            </div>

            <div class="chat-session__main">
              <div class="chat-session__title-row">
                <div class="chat-session__title-main">
                  <strong>{{ session.title }}</strong>
                  <span
                    class="chat-session__ai-state"
                    :class="sessionAiStateMap[session.cid] ? 'is-enabled' : 'is-disabled'"
                  >
                    {{ sessionAiStateMap[session.cid] ? 'AI 开' : 'AI 关' }}
                  </span>
                </div>
                <span>{{ session.last_message_time_text.slice(5, 16) }}</span>
              </div>

              <p class="chat-session__summary">
                {{ session.last_message_summary || '暂无消息' }}
              </p>
            </div>

            <div
              v-if="session.unread_count > 0"
              class="chat-session__badge"
            >
              {{ session.unread_count > 99 ? '99+' : session.unread_count }}
            </div>
          </button>

          <el-empty
            v-if="!filteredSessions.length && !conversationLoading"
            description="暂无会话"
          />
        </div>
      </aside>

      <section class="chat-main theme-surface-soft">
        <template v-if="activeSession">
          <header class="chat-main__header">
            <div class="chat-main__header-main">
              <div class="chat-main__cover">
                <img
                  v-if="activeSession.item_image"
                  :src="activeSession.item_image"
                  :alt="activeSession.item_title || activeSession.title"
                >
                <div
                  v-else
                  class="chat-main__cover-placeholder"
                >
                  {{ activeSession.title.slice(0, 1) || '聊' }}
                </div>
              </div>

              <div class="chat-main__summary">
                <strong>{{ activeSession.item_title || '闲鱼一对一会话' }}</strong>
                <span>{{ activeSession.peer_display_name || activeSession.title || '未知卖家' }}</span>
                <p>{{ activeSession.peer_user_id || '未知用户' }} · {{ activeSession.cid }}</p>
              </div>
            </div>

            <div class="chat-main__header-side">
              <span class="chat-main__chip">{{ activeSession.can_send ? '可发送' : '只读会话' }}</span>
              <span class="chat-main__chip">{{ activeSession.last_message_time_text.slice(0, 16) }}</span>
            </div>
          </header>

          <div class="chat-message-area">
            <div class="chat-message-area__toolbar">
              <el-button
                v-if="hasMoreMessages"
                size="small"
                text
                :loading="messageLoading"
                @click="handleLoadMoreMessages"
              >
                加载更早消息
              </el-button>

              <span v-else>已到更早消息顶部</span>
            </div>

            <div
              ref="messageStreamRef"
              class="chat-message-stream"
            >
              <div
                v-for="message in messages"
                :key="message.message_id"
                class="chat-bubble-row"
                :class="{ 'is-out': message.direction === 'out' }"
                @contextmenu.prevent="handleBubbleContext($event, message)"
              >
                <div class="chat-bubble theme-surface-card">
                  <img
                    v-if="message.image_url"
                    :src="message.image_url"
                    :alt="message.summary || '闲鱼图片消息'"
                    class="chat-bubble__image"
                  >
                  <p>{{ formatMessageText(message) }}</p>
                  <span>{{ message.create_at_text.slice(11, 16) }}</span>
                </div>
              </div>

              <el-empty
                v-if="!messages.length && !messageLoading"
                description="当前会话暂无消息"
              />
            </div>
          </div>

          <div class="chat-composer">
            <div
              v-if="!canSendCurrentSession"
              class="chat-composer__readonly"
            >
              当前会话为系统或特殊场景会话，先展示消息，不开放发送。
            </div>

            <div
              v-else
              class="chat-composer__editor"
            >
              <div class="chat-composer__actions">
                <input
                  ref="imageInputRef"
                  type="file"
                  accept="image/*"
                  class="chat-composer__file-input"
                  @change="handleImageSelected"
                >
                <el-button
                  size="small"
                  text
                  :disabled="uploadingImage"
                  :loading="uploadingImage"
                  @click="handleUploadImage"
                >
                  图片
                </el-button>
              </div>
              <div class="chat-composer__input-row">
                <el-input
                  v-model="composer"
                  type="textarea"
                  :rows="2"
                  resize="none"
                  :disabled="sending"
                  placeholder="输入消息，Enter 发送，Shift+Enter 换行"
                  @keydown.enter.exact.prevent="handleSendMessage"
                />
                <el-button
                  type="primary"
                  :loading="sending"
                  @click="handleSendMessage"
                >
                  发送
                </el-button>
              </div>
            </div>
          </div>
        </template>

        <div
          v-else
          class="chat-empty"
        >
          <el-empty description="请选择左侧会话开始查看" />
        </div>
      </section>
    </div>

    <XianyuChatAiConfigDialog
      v-if="chatAiConfig"
      :visible="chatAiConfigDialogVisible"
      :saving="chatAiConfigSaving"
      :testing="chatAiTesting"
      :model-value="chatAiConfig"
      @update:visible="chatAiConfigDialogVisible = $event"
      @save="saveChatAiConfig"
      @test="handleTestChatAi"
    />

    <Teleport to="body">
      <div
        v-if="contextMenu.visible"
        class="chat-context-menu"
        :style="{ left: contextMenu.x + 'px', top: contextMenu.y + 'px' }"
      >
        <button
          class="chat-context-menu__item"
          @click="handleContextCopy"
        >
          复制文字
        </button>
        <button
          v-if="contextMenu.message?.direction === 'out'"
          class="chat-context-menu__item chat-context-menu__item--danger"
          @click="handleContextRecall"
        >
          撤回消息
        </button>
      </div>
    </Teleport>
  </section>
</template>

<style scoped>
.chat-panel {
  display: grid;
  gap: 16px;
  padding: 18px;
}

.chat-sidebar__account {
  margin-bottom: 14px;
  padding: 14px;
  border-radius: 22px;
  border: 1px solid rgba(var(--app-border-rgb), 0.28);
  background: linear-gradient(135deg, rgba(var(--app-surface-rgb), 0.62), rgba(var(--app-surface-alt-rgb), 0.58));
}

.chat-account {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
}

.chat-account__avatar {
  width: 56px;
  height: 56px;
  border-radius: 18px;
  object-fit: cover;
  flex-shrink: 0;
}

.chat-account__avatar--placeholder {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(var(--app-accent-rgb), 0.94), rgba(var(--app-accent-alt-rgb), 0.84));
  color: white;
  font-size: 22px;
  font-weight: 700;
}

.chat-account__main {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.chat-account__main strong {
  font-size: 18px;
}

.chat-account__main span {
  color: rgb(var(--app-text-subtle-rgb));
  font-size: 12px;
  word-break: break-all;
}

.chat-account__ai-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}

.chat-status {
  padding: 8px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  background: rgba(var(--app-border-rgb), 0.2);
  color: rgb(var(--app-text-subtle-rgb));
}

.chat-status.is-connected {
  background: rgba(34, 197, 94, 0.14);
  color: rgb(34, 197, 94);
}

.chat-status.is-connecting {
  background: rgba(245, 158, 11, 0.14);
  color: rgb(245, 158, 11);
}

.chat-status.is-error {
  background: rgba(239, 68, 68, 0.14);
  color: rgb(239, 68, 68);
}

.chat-shell {
  display: grid;
  grid-template-columns: 340px minmax(0, 1fr);
  gap: 16px;
  height: 720px;
}

.chat-sidebar,
.chat-main {
  border-radius: 26px;
  border: 1px solid rgba(var(--app-border-rgb), 0.42);
}

.chat-sidebar {
  display: flex;
  flex-direction: column;
  padding: 16px;
  min-height: 0;
}

.chat-sidebar__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.chat-sidebar__header div {
  display: grid;
  gap: 4px;
}

.chat-sidebar__header strong {
  font-size: 16px;
}

.chat-sidebar__header span {
  color: rgb(var(--app-text-subtle-rgb));
  font-size: 12px;
}

.chat-sidebar__search {
  margin-top: 14px;
}

.chat-session-list {
  margin-top: 14px;
  display: grid;
  gap: 10px;
  overflow: auto;
  min-height: 0;
  padding-right: 2px;
}

.chat-session {
  display: grid;
  grid-template-columns: 64px minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  padding: 12px;
  border-radius: 20px;
  text-align: left;
  border: 1px solid rgba(var(--app-border-rgb), 0.22);
  background: rgba(var(--app-surface-rgb), 0.5);
  transition: all 0.22s ease;
}

.chat-session:hover,
.chat-session.is-active {
  border-color: rgba(var(--app-accent-rgb), 0.38);
  background: linear-gradient(135deg, rgba(var(--app-accent-rgb), 0.1), rgba(var(--app-accent-alt-rgb), 0.08));
  transform: translateY(-1px);
}

.chat-session__cover,
.chat-main__cover {
  width: 64px;
  height: 64px;
  border-radius: 18px;
  overflow: hidden;
  background: rgba(var(--app-border-rgb), 0.14);
  flex-shrink: 0;
}

.chat-session__cover img,
.chat-main__cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.chat-session__cover-placeholder,
.chat-main__cover-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  font-weight: 700;
  color: white;
  background: linear-gradient(135deg, rgba(var(--app-accent-rgb), 0.9), rgba(var(--app-accent-alt-rgb), 0.86));
}

.chat-session__main {
  min-width: 0;
  display: grid;
  gap: 6px;
}

.chat-session__title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.chat-session__title-main {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.chat-session__title-row strong {
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-session__title-row span,
.chat-session__meta {
  font-size: 12px;
  color: rgb(var(--app-text-subtle-rgb));
}

.chat-session__ai-state {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 44px;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  line-height: 1.4;
  white-space: nowrap;
}

.chat-session__ai-state.is-enabled {
  background: rgba(34, 197, 94, 0.18);
  color: #8ff0b3;
}

.chat-session__ai-state.is-disabled {
  background: rgba(148, 163, 184, 0.16);
  color: #b9c4d4;
}

.chat-session__summary {
  margin: 0;
  font-size: 13px;
  line-height: 1.55;
  color: rgb(var(--app-text-rgb));
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.chat-session__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.chat-session__badge {
  min-width: 24px;
  height: 24px;
  padding: 0 7px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(var(--app-accent-rgb), 0.92);
  color: white;
  font-size: 12px;
  font-weight: 700;
}

.chat-main {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.chat-main__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px 16px;
  border-bottom: 1px solid rgba(var(--app-border-rgb), 0.22);
}

.chat-main__header-main {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}

.chat-main__summary {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.chat-main__summary strong {
  font-size: 17px;
}

.chat-main__summary span,
.chat-main__summary p {
  margin: 0;
  color: rgb(var(--app-text-subtle-rgb));
  font-size: 12px;
  line-height: 1.5;
  word-break: break-all;
}

.chat-main__header-side {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.chat-main__chip {
  padding: 8px 10px;
  border-radius: 999px;
  font-size: 12px;
  color: rgb(var(--app-text-subtle-rgb));
  background: rgba(var(--app-border-rgb), 0.14);
}

.chat-message-area {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.chat-message-area__toolbar {
  padding: 10px 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgb(var(--app-text-subtle-rgb));
  font-size: 12px;
}

.chat-message-stream {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 10px 20px 18px;
  display: grid;
  gap: 12px;
  align-content: start;
}

.chat-bubble-row {
  display: flex;
  justify-content: flex-start;
}

.chat-bubble-row.is-out {
  justify-content: flex-end;
}

.chat-bubble {
  max-width: min(72%, 540px);
  padding: 12px 14px 10px;
  border-radius: 20px;
  border: 1px solid rgba(var(--app-border-rgb), 0.26);
  display: grid;
  gap: 8px;
}

.chat-bubble-row.is-out .chat-bubble {
  background: linear-gradient(135deg, rgba(var(--app-accent-rgb), 0.14), rgba(var(--app-accent-alt-rgb), 0.12));
  border-color: rgba(var(--app-accent-rgb), 0.22);
}

.chat-bubble p {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.72;
}

.chat-bubble span {
  justify-self: flex-end;
  font-size: 12px;
  color: rgb(var(--app-text-subtle-rgb));
}

.chat-bubble__image {
  max-width: 220px;
  max-height: 220px;
  border-radius: 16px;
  object-fit: cover;
}

.chat-composer {
  border-top: 1px solid rgba(var(--app-border-rgb), 0.22);
  padding: 16px 20px 20px;
  display: grid;
  gap: 10px;
  position: sticky;
  bottom: 0;
  background:
    linear-gradient(180deg, rgba(var(--app-surface-rgb), 0.92), rgba(var(--app-surface-alt-rgb), 0.96));
  backdrop-filter: blur(12px);
}

.chat-composer__readonly {
  padding: 10px 14px;
  border-radius: 16px;
  color: rgb(var(--app-text-subtle-rgb));
  background: rgba(var(--app-border-rgb), 0.1);
  font-size: 12px;
}

.chat-composer__editor {
  display: grid;
  gap: 8px;
}

.chat-composer__actions {
  display: flex;
  gap: 4px;
  align-items: center;
}

.chat-composer__input-row {
  display: flex;
  gap: 10px;
  align-items: stretch;
}

.chat-composer__input-row .el-input {
  flex: 1;
  min-width: 0;
}

.chat-composer__input-row :deep(.el-textarea) {
  width: 100%;
}

.chat-composer__input-row :deep(.el-textarea__inner) {
  min-height: 52px;
  background: rgba(var(--app-surface-rgb), 0.96) !important;
  border: 1px solid rgba(var(--app-border-rgb), 0.72) !important;
  color: rgb(var(--app-text-strong-rgb)) !important;
  -webkit-text-fill-color: rgb(var(--app-text-strong-rgb)) !important;
  caret-color: rgb(var(--app-text-strong-rgb)) !important;
  box-shadow: 0 0 0 1px rgba(var(--app-border-rgb), 0.36) inset !important;
}

.chat-composer__input-row :deep(.el-textarea__inner::placeholder) {
  color: rgb(var(--app-text-subtle-rgb)) !important;
  -webkit-text-fill-color: rgb(var(--app-text-subtle-rgb)) !important;
}

.chat-composer__input-row :deep(.el-textarea__inner:focus) {
  border-color: rgba(var(--primary-color-rgb), 0.82) !important;
  box-shadow: 0 0 0 1px rgba(var(--primary-color-rgb), 0.58) inset !important;
}

.chat-composer__input-row .el-button {
  flex-shrink: 0;
  height: auto;
  align-self: flex-end;
}

.chat-composer__file-input {
  display: none;
}

.chat-context-menu {
  position: fixed;
  z-index: 9999;
  min-width: 120px;
  padding: 4px 0;
  border-radius: 12px;
  border: 1px solid rgba(var(--app-border-rgb), 0.3);
  background: rgba(var(--app-surface-rgb), 0.98);
  backdrop-filter: blur(12px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);
}

.chat-context-menu__item {
  display: block;
  width: 100%;
  padding: 8px 16px;
  border: none;
  background: none;
  text-align: left;
  font-size: 13px;
  cursor: pointer;
  color: rgb(var(--app-text-rgb));
}

.chat-context-menu__item:hover {
  background: rgba(var(--app-accent-rgb), 0.08);
}

.chat-context-menu__item--danger {
  color: rgb(239, 68, 68);
}

.chat-context-menu__item--danger:hover {
  background: rgba(239, 68, 68, 0.08);
}

.chat-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

@media (max-width: 1200px) {
  .chat-shell {
    grid-template-columns: 1fr;
  }

  .chat-shell {
    min-height: auto;
  }

  .chat-sidebar {
    max-height: 360px;
  }
}

@media (max-width: 768px) {
  .chat-panel {
    padding: 14px;
  }

  .chat-composer__input-row {
    flex-direction: column;
  }

  .chat-composer__input-row .el-button {
    width: 100%;
    height: auto;
  }

  .chat-bubble {
    max-width: 92%;
  }
}
</style>
