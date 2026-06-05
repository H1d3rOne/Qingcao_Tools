import { request } from '../request'

interface ApiResponse<T = any> {
  success: boolean
  data: T
  error?: string
  message?: string
}

export interface XianyuFilterOption {
  label: string
  value: string
  checked: boolean
}

export interface XianyuFilterGroup {
  name: string
  pid: string
  options: XianyuFilterOption[]
}

export interface XianyuSearchItem {
  item_id: string
  title: string
  price: string
  image: string
  area: string
  seller: string
  seller_avatar: string
  want: string
  tags: string[]
  detail_url: string
}

export interface XianyuSearchResult {
  keyword: string
  total: number
  page: number
  page_size: number
  has_more: boolean
  location: string
  search_id: string
  items: XianyuSearchItem[]
  filters: XianyuFilterGroup[]
}

export interface XianyuMonitorHit {
  item_id: string
  title: string
  price: string
  image: string
  detail_url: string
  discovered_at: number
}

export interface XianyuMonitorTask {
  id: string
  name: string
  keyword: string
  page: number
  page_size: number
  sort_field: string
  sort_value: string
  prop_values: Record<string, string>
  min_price?: number | null
  max_price?: number | null
  interval_seconds: number
  enabled: boolean
  created_at: number
  updated_at: number
  last_run_at: number
  last_status: string
  last_error: string
  seen_item_ids: string[]
  latest_hits: XianyuMonitorHit[]
  // 触发条件
  max_hits?: number | null
  published_within_hours?: number | null
  // 执行动作
  webhook_url?: string
  contact_seller_enabled?: boolean
}

export interface XianyuMonitorTaskCreate {
  name: string
  keyword: string
  page?: number
  page_size?: number
  sort_field?: string
  sort_value?: string
  prop_values?: Record<string, string>
  min_price?: number | null
  max_price?: number | null
  interval_seconds?: number
  enabled?: boolean
  // 触发条件
  max_hits?: number | null
  published_within_hours?: number | null
  // 执行动作
  webhook_url?: string
  contact_seller_enabled?: boolean
}

export interface XianyuMonitorTaskUpdate {
  name?: string
  keyword?: string
  page?: number
  page_size?: number
  sort_field?: string
  sort_value?: string
  prop_values?: Record<string, string>
  min_price?: number | null
  max_price?: number | null
  interval_seconds?: number
  enabled?: boolean
  // 触发条件
  max_hits?: number | null
  published_within_hours?: number | null
  // 执行动作
  webhook_url?: string
  contact_seller_enabled?: boolean
}

export interface XianyuUserProfile {
  display_name: string
  avatar?: string
  sold_count?: number
  purchase_count?: number
  followers?: number
  following?: number
  collection_count?: number
}

export interface XianyuDetailAttribute {
  name: string
  value: string
}

export interface XianyuItemDetail {
  item_id: string
  title: string
  price: string
  original_price: string
  desc: string
  images: string[]
  location: string
  publish_time: string
  status: string
  transport_fee: string
  browse_count: number
  want_count: number
  collect_count: number
  tags: string[]
  attributes: XianyuDetailAttribute[]
  seller_name: string
  seller_user_id: string
  seller_avatar: string
  seller_summary: string
  seller_city: string
  seller_last_visit: string
  seller_item_count: number
  detail_url: string
}

export interface XianyuOrder {
  order_id: string
  item_id: string
  item_title: string
  item_image: string
  item_price: string
  buyer_id: string
  buyer_nick: string
  buyer_avatar: string
  amount: string
  status_code: string
  status_text: string
  status_group: string
  created_at: string
  paid_at: string
  finished_at: string
  is_dummy: boolean
  quantity: number
  remark: string
}

export interface XianyuOrderPage {
  orders: XianyuOrder[]
  page: number
  page_size: number
  total: number
  has_more: boolean
}

export interface XianyuOrderShipResult {
  order_id: string
  success: boolean
  message: string
}

export interface XianyuOrderListParams {
  page?: number
  page_size?: number
  status?: string
  order_id?: string
}

export interface XianyuManageItem {
  item_id: string
  item_title: string
  item_price: string
  item_image: string
  item_status: string
  item_detail: string
  multi_quantity_delivery: boolean
  synced_at: number
  updated_at: number
}

export interface XianyuManageItemPage {
  items: XianyuManageItem[]
  total: number
  page: number
  page_size: number
  has_more: boolean
}

export interface XianyuDeliveryRule {
  id: string
  name: string
  enabled: boolean
  item_id: string
  keyword: string
  match_mode: 'item_id' | 'keyword'
  match_value?: string
  delivery_text: string
  send_chat_text: boolean
  send_dummy_ship: boolean
  created_at: number
  updated_at: number
}

export interface XianyuDeliveryRulePayload {
  name: string
  match_mode: 'item_id' | 'keyword'
  match_value?: string
  item_id?: string
  keyword?: string
  enabled?: boolean
  delivery_text: string
  send_chat_text: boolean
  send_dummy_ship: boolean
}

export interface XianyuDeliveryExecutionRecord {
  id: string
  rule_id: string
  rule_name: string
  order_id: string
  item_id: string
  buyer_id: string
  status: string
  message: string
  created_at: number
}

export interface XianyuDeliveryRuntimeStatus {
  running: boolean
  last_event_at: number
  last_success_at: number
  last_failure_at: number
  last_error: string
  enabled_rule_count: number
  recent_success_count: number
  recent_failure_count: number
}

export interface XianyuChatProfile {
  user_id: string
  main_user_id: string
  domain: string
  display_name: string
  avatar: string
}

export interface XianyuChatConversation {
  cid: string
  session_id: string
  session_type: number
  biz_type: string
  title: string
  peer_user_id: string
  peer_display_name: string
  peer_avatar: string
  item_id: string
  item_title: string
  item_image: string
  last_message_id: string
  last_message_summary: string
  last_message_time: number
  last_message_time_text: string
  unread_count: number
  red_point: number
  top_rank: number
  muted: boolean
  visible: boolean
  can_send: boolean
}

export interface XianyuChatConversationPage {
  total: number
  offset: number
  limit: number
  conversations: XianyuChatConversation[]
}

export interface XianyuChatMessage {
  cid: string
  message_id: string
  numeric_message_id: number
  sender_uid: string
  sender_display_name: string
  direction: 'in' | 'out' | string
  content_type: number
  summary: string
  text: string
  image_url: string
  create_at: number
  create_at_text: string
  read_status: number
  raw_extension: Record<string, string>
}

export interface XianyuChatMessagePage {
  cid: string
  cursor?: string | null
  has_more: boolean
  messages: XianyuChatMessage[]
}

export interface XianyuChatSendPayload {
  cid: string
  text: string
}

export interface XianyuChatOpenSessionPayload {
  item_id: string
  peer_user_id: string
}

export interface XianyuChatOpenSessionResponse {
  success: boolean
  message: string
  cid?: string
  session?: XianyuChatConversation | null
}

export interface XianyuChatSendResult {
  cid: string
  message_id: string
  uuid: string
  create_at: number
  summary: string
}

export interface XianyuChatAiProvider {
  id: string
  name: string
  base_url: string
  models: string[]
  active_model: string
  system_prompt: string
  api_key_configured: boolean
  api_key_masked: string
  is_active: boolean
}

export interface XianyuChatAiConfig {
  enabled: boolean
  chat_keepalive_interval_seconds: number
  providers: XianyuChatAiProvider[]
  active_provider_id: string
}

export interface XianyuChatAiProviderCreatePayload {
  name: string
  base_url: string
  api_key: string
  models: string[]
  active_model: string
  system_prompt: string
  provider_id?: string
}

export interface XianyuChatAiProviderUpdatePayload {
  name?: string
  base_url?: string
  api_key?: string
  models?: string[]
  active_model?: string
  system_prompt?: string
}

export interface XianyuChatAiSessionState {
  cid: string
  enabled: boolean
}

export interface XianyuChatAiSessionUpdatePayload {
  enabled: boolean
}

export interface XianyuChatAiTestResponse {
  reply: string
}

export interface XianyuChatHealthStatus {
  ok: boolean
  status: 'ok' | 'risk_blocked' | 'auth_invalid' | 'cookie_missing' | 'error' | string
  message: string
  captcha_url: string
  shared_ws_connected: boolean
  cookie_configured: boolean
}

export interface XianyuSearchPayload {
  keyword: string
  page?: number
  page_size?: number
  province?: string
  city?: string
  sort_field?: string
  sort_value?: string
  prop_values?: Record<string, string>
}

export interface XianyuAuthLoginPayload {
  method?: 'cookie'
  cookies?: string
}

export interface XianyuAuthLoginResponse {
  success: boolean
  message: string
  login_token?: string
}

export interface XianyuAuthStatusResponse {
  success: boolean
  message?: string
  is_logged_in: boolean
  user_info?: Record<string, unknown> | null
}

export interface XianyuAuthLogoutResponse {
  success: boolean
  message: string
}

export function searchXianyuItems(payload: XianyuSearchPayload) {
  return request.post<ApiResponse<XianyuSearchResult>>('/xianyu/search', payload)
}

export function loginXianyu(payload: XianyuAuthLoginPayload) {
  return request.post<XianyuAuthLoginResponse>('/xianyu/auth/login', payload)
}

export function getXianyuAuthStatus() {
  return request.get<XianyuAuthStatusResponse>('/xianyu/auth/status')
}

export function logoutXianyu() {
  return request.post<XianyuAuthLogoutResponse>('/xianyu/auth/logout')
}

export function listXianyuMonitorTasks() {
  return request.get<ApiResponse<XianyuMonitorTask[]>>('/xianyu/monitor/tasks')
}

export function createXianyuMonitorTask(payload: XianyuMonitorTaskCreate) {
  return request.post<ApiResponse<XianyuMonitorTask>>('/xianyu/monitor/tasks', payload)
}

export function updateXianyuMonitorTask(taskId: string, payload: XianyuMonitorTaskUpdate) {
  return request.put<ApiResponse<XianyuMonitorTask>>(`/xianyu/monitor/tasks/${taskId}`, payload)
}

export function deleteXianyuMonitorTask(taskId: string) {
  return request.delete<ApiResponse<{ deleted: boolean }>>(`/xianyu/monitor/tasks/${taskId}`)
}

export function toggleXianyuMonitorTask(taskId: string) {
  return request.post<ApiResponse<XianyuMonitorTask>>(`/xianyu/monitor/tasks/${taskId}/toggle`)
}

export function runXianyuMonitorTask(taskId: string) {
  return request.post<ApiResponse<XianyuMonitorTask>>(`/xianyu/monitor/tasks/${taskId}/run`)
}

export function getXianyuMonitorHits(taskId: string) {
  return request.get<ApiResponse<XianyuMonitorHit[]>>(`/xianyu/monitor/tasks/${taskId}/hits`)
}

export function getXianyuUserProfile() {
  return request.get<ApiResponse<XianyuUserProfile>>('/xianyu/user/profile')
}

export function getXianyuItemDetail(itemId: string) {
  return request.get<ApiResponse<XianyuItemDetail>>('/xianyu/detail', { item_id: itemId })
}

export function listXianyuOrders(params: XianyuOrderListParams = {}) {
  return request.get<ApiResponse<XianyuOrderPage>>('/xianyu/orders', {
    page: params.page ?? 1,
    page_size: params.page_size ?? 20,
    status: params.status ?? 'ALL',
    order_id: params.order_id ?? '',
  })
}

export function shipXianyuOrder(orderId: string, tradeText = '') {
  return request.post<ApiResponse<XianyuOrderShipResult>>('/xianyu/orders/ship', {
    order_id: orderId,
    trade_text: tradeText,
  })
}

export function listXianyuManageItems(params?: { page?: number; page_size?: number }) {
  return request.get<ApiResponse<XianyuManageItemPage>>('/xianyu/manage/items', params)
}

export function syncXianyuManageItemsPage(payload: { page: number; page_size: number }) {
  return request.post<ApiResponse<XianyuManageItemPage>>('/xianyu/manage/items/sync-page', payload)
}

export function syncXianyuManageItemsAll() {
  return request.post<ApiResponse<{ synced: number; pages: number }>>('/xianyu/manage/items/sync-all')
}

export function getXianyuManageItem(itemId: string) {
  return request.get<ApiResponse<XianyuManageItem>>(`/xianyu/manage/items/${itemId}`)
}

export function updateXianyuManageItem(itemId: string, payload: { item_detail: string }) {
  return request.put<ApiResponse<XianyuManageItem>>(`/xianyu/manage/items/${itemId}`, payload)
}

export function deleteXianyuManageItem(itemId: string) {
  return request.delete<ApiResponse<{ deleted: boolean }>>(`/xianyu/manage/items/${itemId}`)
}

export function setXianyuManageItemMultiQuantityDelivery(itemId: string, enabled: boolean) {
  return request.put<ApiResponse<XianyuManageItem>>(`/xianyu/manage/items/${itemId}/multi-quantity-delivery`, {
    enabled,
  })
}

export function polishXianyuManageItem(itemId: string, enableNotification = false) {
  return request.post<ApiResponse<{ success: boolean; item_id: string; message: string }>>('/xianyu/manage/items/polish', {
    item_id: itemId,
    enable_notification: enableNotification,
  })
}

export function polishAllXianyuManageItems() {
  return request.post<ApiResponse<{ total: number; polished: number }>>('/xianyu/manage/items/polish-all')
}

export function listXianyuDeliveryRules() {
  return request.get<ApiResponse<XianyuDeliveryRule[]>>('/xianyu/manage/delivery-rules')
}

export function createXianyuDeliveryRule(payload: XianyuDeliveryRulePayload) {
  return request.post<ApiResponse<XianyuDeliveryRule>>('/xianyu/manage/delivery-rules', payload)
}

export function updateXianyuDeliveryRule(ruleId: string, payload: Partial<XianyuDeliveryRulePayload>) {
  return request.put<ApiResponse<XianyuDeliveryRule>>(`/xianyu/manage/delivery-rules/${ruleId}`, payload)
}

export function deleteXianyuDeliveryRule(ruleId: string) {
  return request.delete<ApiResponse<{ deleted: boolean }>>(`/xianyu/manage/delivery-rules/${ruleId}`)
}

export function toggleXianyuDeliveryRule(ruleId: string) {
  return request.post<ApiResponse<XianyuDeliveryRule>>(`/xianyu/manage/delivery-rules/${ruleId}/toggle`)
}

export function getXianyuDeliveryRuntimeStatus() {
  return request.get<ApiResponse<XianyuDeliveryRuntimeStatus>>('/xianyu/manage/runtime/status')
}

export function listXianyuDeliveryExecutions(params?: { limit?: number }) {
  return request.get<ApiResponse<XianyuDeliveryExecutionRecord[]>>('/xianyu/manage/runtime/executions', params)
}

export function getXianyuChatProfile() {
  return request.get<ApiResponse<XianyuChatProfile>>('/xianyu/chat/profile')
}

export function getXianyuChatAiConfig() {
  return request.get<ApiResponse<XianyuChatAiConfig>>('/xianyu/chat/ai/config')
}

export function setXianyuChatAiEnabled(enabled: boolean) {
  return request.post<ApiResponse<XianyuChatAiConfig>>('/xianyu/chat/ai/enabled', null, {
    params: { enabled },
  })
}

export function setXianyuChatKeepaliveInterval(seconds: number) {
  return request.post<ApiResponse<XianyuChatAiConfig>>('/xianyu/chat/ai/keepalive-interval', null, {
    params: { seconds },
  })
}

export function createXianyuChatAiProvider(payload: XianyuChatAiProviderCreatePayload) {
  return request.post<ApiResponse<XianyuChatAiProvider>>('/xianyu/chat/ai/providers', payload)
}

export function testXianyuChatAiProvider(payload: XianyuChatAiProviderCreatePayload) {
  return request.post<ApiResponse<XianyuChatAiTestResponse>>('/xianyu/chat/ai/providers/test', payload)
}

export function updateXianyuChatAiProvider(providerId: string, payload: XianyuChatAiProviderUpdatePayload) {
  return request.patch<ApiResponse<XianyuChatAiProvider>>(`/xianyu/chat/ai/providers/${providerId}`, payload)
}

export function deleteXianyuChatAiProvider(providerId: string) {
  return request.delete<ApiResponse<{ deleted: boolean }>>(`/xianyu/chat/ai/providers/${providerId}`)
}

export function setActiveXianyuChatAiProvider(providerId: string) {
  return request.post<ApiResponse<{ active: string }>>(`/xianyu/chat/ai/providers/${providerId}/active`)
}

export function getXianyuChatAiProviderApiKey(providerId: string) {
  return request.get<ApiResponse<{ api_key: string }>>(`/xianyu/chat/ai/providers/${providerId}/api-key`)
}

export function setXianyuChatAiProviderActiveModel(providerId: string, model: string) {
  return request.post<ApiResponse<XianyuChatAiProvider>>(`/xianyu/chat/ai/providers/${providerId}/active-model`, null, {
    params: { model },
  })
}

export function getXianyuChatAiSessions(cids: string[]) {
  return request.get<ApiResponse<XianyuChatAiSessionState[]>>('/xianyu/chat/ai/sessions', { cid: cids })
}

export function updateXianyuChatAiSession(cid: string, payload: XianyuChatAiSessionUpdatePayload) {
  return request.post<ApiResponse<XianyuChatAiSessionState>>(`/xianyu/chat/ai/sessions/${cid}`, payload)
}

export function testXianyuChatAi(payload: { text: string; cid?: string }) {
  return request.post<ApiResponse<{ reply: string }>>('/xianyu/chat/ai/test', payload)
}

export function getXianyuChatHealth() {
  return request.get<ApiResponse<XianyuChatHealthStatus>>('/xianyu/chat/health')
}

export function getXianyuChatConversations(params?: { offset?: number; limit?: number }) {
  return request.get<ApiResponse<XianyuChatConversationPage>>('/xianyu/chat/conversations', params)
}

export function openXianyuChatSession(payload: XianyuChatOpenSessionPayload) {
  return request.post<XianyuChatOpenSessionResponse>('/xianyu/chat/open-session', payload)
}

export function getXianyuChatMessages(params: {
  cid: string
  cursor?: string | null
  limit?: number
  direction?: 'prev' | 'next'
}) {
  return request.get<ApiResponse<XianyuChatMessagePage>>('/xianyu/chat/messages', params)
}

export function sendXianyuChatMessage(payload: XianyuChatSendPayload) {
  return request.post<ApiResponse<XianyuChatSendResult>>('/xianyu/chat/send', payload)
}

export function clearXianyuChatRedPoint(cids: string[]) {
  return request.post<ApiResponse<{ success_count: number }>>('/xianyu/chat/clear-red-point', { cids })
}

export function sendXianyuChatImage(payload: { cid: string; image_url: string; width?: number; height?: number }) {
  return request.post<ApiResponse<XianyuChatSendResult>>('/xianyu/chat/send-image', payload)
}

export function recallXianyuChatMessage(messageId: string) {
  return request.post<ApiResponse<{ success: boolean }>>('/xianyu/chat/recall', { message_id: messageId })
}

export function markXianyuChatRead(cid: string) {
  return request.post<ApiResponse<{ success: boolean }>>('/xianyu/chat/mark-read', { cid })
}

export function createXianyuChatSession(payload: { peer_user_id: string; item_id?: string }) {
  return request.post<ApiResponse<{ success: boolean; cid?: string; message?: string }>>('/xianyu/chat/create-session', payload)
}

export function uploadAndSendXianyuChatImage(cid: string, file: File) {
  const formData = new FormData()
  formData.append('cid', cid)
  formData.append('file', file)
  return request.post<ApiResponse<XianyuChatSendResult>>('/xianyu/chat/upload-and-send-image', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function getXianyuUserInfo(userId: string) {
  return request.get<ApiResponse<Record<string, any>>>('/xianyu/chat/user-info', {
    params: { user_id: userId },
  })
}

export interface XianyuChatPushEvent {
  type: 'connected' | 'push' | 'pong' | 'error' | 'disconnected'
  lwp?: string
  headers?: Record<string, any>
  body?: any
  decoded?: {
    type: string
    items?: Array<{
      biz_type: number
      biz_label: string
      decoded: Record<string, any>
    }>
    data?: any
    lwp?: string
  }
  message?: string
}

export interface XianyuChatWebSocketCallbacks {
  onConnected?: () => void
  onPush?: (event: XianyuChatPushEvent) => void
  onError?: (message: string) => void
  onDisconnected?: () => void
}

export function createXianyuChatWebSocket(
  callbacks: XianyuChatWebSocketCallbacks = {}
): {
  ws: WebSocket | null
  connect: () => void
  disconnect: () => void
  isConnected: () => boolean
} {
  let ws: WebSocket | null = null
  let heartbeatTimer: number | null = null
  let reconnectTimer: number | null = null
  let reconnectAttempts = 0
  let manualClose = false
  let allowReconnect = true

  function startHeartbeat() {
    stopHeartbeat()
    heartbeatTimer = window.setInterval(() => {
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ action: 'ping' }))
      }
    }, 20000)
  }

  function stopHeartbeat() {
    if (heartbeatTimer !== null) {
      clearInterval(heartbeatTimer)
      heartbeatTimer = null
    }
  }

  function clearReconnect() {
    if (reconnectTimer !== null) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  function scheduleReconnect() {
    if (manualClose || !allowReconnect || reconnectTimer !== null) {
      return
    }
    const delay = Math.min(1500 * Math.max(reconnectAttempts, 1), 8000)
    reconnectAttempts += 1
    reconnectTimer = window.setTimeout(() => {
      reconnectTimer = null
      connect()
    }, delay)
  }

  function connect() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      return
    }

    manualClose = false
    allowReconnect = true
    clearReconnect()
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    ws = new WebSocket(`${protocol}//${location.host}/api/v1/xianyu/chat/ws`)

    ws.onopen = () => {
      reconnectAttempts = 0
      startHeartbeat()
    }

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as XianyuChatPushEvent
        if (payload.type === 'connected') {
          callbacks.onConnected?.()
          return
        }
        if (payload.type === 'push') {
          callbacks.onPush?.(payload)
          return
        }
        if (payload.type === 'error') {
          if ((payload.message || '').match(/token is not found|FAIL_SYS_USER_VALIDATE|Cookie/i)) {
            allowReconnect = false
          }
          callbacks.onError?.(payload.message || '闲鱼聊天连接失败')
          return
        }
        if (payload.type === 'disconnected') {
          callbacks.onDisconnected?.()
        }
      } catch {
        callbacks.onError?.('闲鱼聊天消息解析失败')
      }
    }

    ws.onerror = () => {
      callbacks.onError?.('闲鱼聊天连接异常')
    }

    ws.onclose = () => {
      stopHeartbeat()
      const shouldReconnect = !manualClose
      ws = null
      callbacks.onDisconnected?.()
      if (shouldReconnect && allowReconnect) {
        scheduleReconnect()
      }
    }
  }

  function disconnect() {
    manualClose = true
    allowReconnect = false
    stopHeartbeat()
    clearReconnect()
    if (ws) {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ action: 'close' }))
      }
      ws.close(1000, '主动关闭')
      ws = null
    }
  }

  function isConnected() {
    return ws?.readyState === WebSocket.OPEN
  }

  return {
    get ws() {
      return ws
    },
    connect,
    disconnect,
    isConnected,
  }
}
