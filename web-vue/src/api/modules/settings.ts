import { request } from '../request'

// API 响应类型
interface ApiResponse<T = any> {
  success: boolean
  data: T
  error?: string
  message?: string
}

// Cookie 配置信息
interface CookieInfo {
  dy_configured: boolean
  dy_preview?: string
  live_configured: boolean
  live_preview?: string
  quark_configured: boolean
  quark_preview?: string
  xianyu_configured: boolean
  xianyu_preview?: string
}

export interface XianyuCookieValue {
  configured: boolean
  cookie: string
}

// 获取 Cookie 配置
export function getCookieSettings() {
  return request.get<ApiResponse<CookieInfo>>('/settings/cookie')
}

export function getFullXianyuCookie() {
  return request.get<ApiResponse<XianyuCookieValue>>('/settings/cookie/xianyu/full')
}

// 更新抖音 Cookie 配置
export function updateDyCookie(cookie: string) {
  return request.post<ApiResponse<void>>('/settings/cookie/dy', { cookie })
}

// 更新直播 Cookie 配置
export function updateLiveCookie(cookie: string) {
  return request.post<ApiResponse<void>>('/settings/cookie/live', { cookie })
}

// 更新夸克 Cookie 配置
export function updateQuarkCookie(cookie: string) {
  return request.post<ApiResponse<void>>('/settings/cookie/quark', { cookie })
}

// 更新闲鱼 Cookie 配置
export function updateXianyuCookie(cookie: string) {
  return request.post<ApiResponse<void>>('/settings/cookie/xianyu', { cookie })
}
