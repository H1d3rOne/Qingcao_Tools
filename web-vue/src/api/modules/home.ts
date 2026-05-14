import { request } from '../request'
import type { Video } from '@/types/api'

// API 响应类型
interface ApiResponse<T = any> {
  success: boolean
  data: T
  error?: string
  message?: string
  total?: number
}

// 首页推荐视频项
interface FeedVideo {
  aweme_id: string
  desc: string
  author: string
  digg_count: number
  cover: string
}

// 获取首页推荐
export function getFeed() {
  return request.get<ApiResponse<FeedVideo[]>>('/douyin/feed')
}

// 获取服务状态
export function getStatus() {
  return request.get<ApiResponse<{ cookie_configured: boolean }>>('/settings/status')
}
