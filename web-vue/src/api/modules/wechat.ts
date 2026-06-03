import { request } from '../request'

interface ApiResponse<T = unknown> {
  success: boolean
  data: T
  error?: string
  message?: string
}

export interface WechatListenerStatus {
  listening: boolean
  proxy_running: boolean
  local_server_running: boolean
  system_proxy_enabled: boolean
  proxy_host: string
  proxy_port: number
  local_server_port: number
  video_count: number
  download_dir: string
  last_error?: string | null
}

export interface WechatProxyConfig {
  proxy_host: string
  proxy_port: number
  local_server_host: string
  local_server_port: number
}

export interface WechatCertificateStatus {
  platform: string
  architecture: string
  supported: boolean
  certificate_exists: boolean
  trusted: boolean
  certificate_path: string
  message: string
}

export interface WechatVideoItem {
  id: string
  description: string
  url: string
  cover_url: string
  file_size: number
  file_size_text: string
  duration: number
  decode_key: string
  created_at: number
}

export interface WechatVideoListResponse {
  items: WechatVideoItem[]
  total: number
}

export interface WechatDownloadTaskItem {
  id: string
  video_id: string
  description: string
  cover_url: string
  url: string
  file_size: number
  file_size_text: string
  duration: number
  status: string
  progress: number
  downloaded_size: number
  downloaded_size_text: string
  raw_file: string
  decoded_file: string
  error?: string | null
  created_at: number
  updated_at: number
}

export interface WechatDownloadTaskListResponse {
  items: WechatDownloadTaskItem[]
  total: number
}

export function getWechatListenerStatus() {
  return request.get<ApiResponse<WechatListenerStatus>>('/wechat/listener/status')
}

export function startWechatListener() {
  return request.post<ApiResponse<WechatListenerStatus>>('/wechat/listener/start')
}

export function stopWechatListener() {
  return request.post<ApiResponse<WechatListenerStatus>>('/wechat/listener/stop')
}

export function getWechatProxyConfig() {
  return request.get<ApiResponse<WechatProxyConfig>>('/wechat/config')
}

export function updateWechatProxyConfig(proxyPort: number, localServerPort: number) {
  return request.post<ApiResponse<WechatProxyConfig>>('/wechat/config', {
    proxy_port: proxyPort,
    local_server_port: localServerPort
  })
}

export function getWechatCertificateStatus() {
  return request.get<ApiResponse<WechatCertificateStatus>>('/wechat/certificate/status')
}

export function installWechatCertificate() {
  return request.post<ApiResponse<WechatCertificateStatus>>('/wechat/certificate/install', undefined, {
    timeout: 180000
  })
}

export function getWechatVideos() {
  return request.get<ApiResponse<WechatVideoListResponse>>('/wechat/videos')
}

export function clearWechatVideos() {
  return request.post<ApiResponse<Record<string, number>>>('/wechat/videos/clear')
}

export function getWechatDownloadTasks() {
  return request.get<ApiResponse<WechatDownloadTaskListResponse>>('/wechat/download/tasks')
}

export function setWechatDownloadDir(path: string) {
  return request.post<ApiResponse<WechatListenerStatus>>('/wechat/download/dir', { path })
}

export function selectWechatDownloadDir() {
  return request.post<ApiResponse<WechatListenerStatus>>('/wechat/download/dir/select')
}

export function retryWechatDownloadTask(taskId: string) {
  return request.post<ApiResponse<WechatDownloadTaskItem>>(`/wechat/download/tasks/${taskId}/retry`)
}

export function cancelWechatDownloadTask(taskId: string) {
  return request.post<ApiResponse<Record<string, string>>>(`/wechat/download/tasks/${taskId}/cancel`)
}

export function openWechatDownloadTaskDir(taskId: string) {
  return request.post<ApiResponse<Record<string, string>>>(`/wechat/download/tasks/${taskId}/open-dir`)
}

export function getWechatDownloadTaskPreviewUrl(taskId: string, updatedAt?: number) {
  const query = updatedAt ? `?t=${encodeURIComponent(updatedAt)}` : ''
  return `/api/v1/wechat/download/tasks/${taskId}/preview${query}`
}

export function deleteWechatDownloadTask(taskId: string) {
  return request.delete<ApiResponse<Record<string, string>>>(
    `/wechat/download/tasks/${taskId}`
  )
}

export function clearWechatDownloadTasks(statuses?: string[]) {
  return request.post<ApiResponse<Record<string, unknown>>>('/wechat/download/tasks/clear', { statuses })
}

export function queueWechatVideoDownload(videoId: string) {
  return request.post<ApiResponse<WechatDownloadTaskItem>>('/wechat/download/tasks', { video_id: videoId })
}

export function downloadWechatVideo(videoId: string) {
  return request.post<ApiResponse<Record<string, string>>>('/wechat/download', { video_id: videoId })
}
