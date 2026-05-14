import { request } from '../request'

interface ApiResponse<T = any> {
  success: boolean
  data: T
  error?: string
  message?: string
}

interface WebhookConfig {
  enabled: boolean
  webhook_url: string | null
}

interface NotifyConfig {
  wecom: WebhookConfig
  dingtalk: WebhookConfig
  feishu: WebhookConfig
}

interface UpdateWebhookRequest {
  webhook_url: string
  enabled: boolean
}

export function getNotifyConfig() {
  return request.get<ApiResponse<NotifyConfig>>('/notify/config')
}

export function updateWecomConfig(data: UpdateWebhookRequest) {
  return request.post<ApiResponse<void>>('/notify/config/wecom', data)
}

export function updateDingtalkConfig(data: UpdateWebhookRequest) {
  return request.post<ApiResponse<void>>('/notify/config/dingtalk', data)
}

export function updateFeishuConfig(data: UpdateWebhookRequest) {
  return request.post<ApiResponse<void>>('/notify/config/feishu', data)
}

export function testWecomNotify(message: string = '测试消息') {
  return request.post<ApiResponse<void>>('/notify/test/wecom', { message })
}

export function testDingtalkNotify(message: string = '测试消息') {
  return request.post<ApiResponse<void>>('/notify/test/dingtalk', { message })
}

export function testFeishuNotify(message: string = '测试消息') {
  return request.post<ApiResponse<void>>('/notify/test/feishu', { message })
}
