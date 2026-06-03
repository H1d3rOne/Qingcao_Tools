import { request } from '../request'
import type { VideoQuality } from './video'

// API 响应类型
interface ApiResponse<T = any> {
  success: boolean
  data: T
  error?: string
  message?: string
  total?: number
  has_more?: boolean
  cursor?: number
}

// 用户信息
export interface UserInfo {
  uid: string
  sec_uid: string
  nickname: string
  signature: string
  avatar: string
  gender?: number
  user_age?: number
  ip_location?: string
  country?: string
  follower_count: number
  following_count: number
  aweme_count: number
  favoriting_count: number
  is_verify?: number
  verify_info?: string
  unique_id: string
}

// 用户作品
export interface UserWork {
  aweme_id: string
  desc: string
  create_time: number
  digg_count: number
  comment_count: number
  share_count: number
  play_count: number
  cover_url: string  // 封面URL
  cover?: {
    url_list: string[]
    uri?: string
  }
  video_url?: string // 视频URL
  video_qualities?: Record<string, VideoQuality>  // 不同清晰度的视频链接
  images?: string[]  // 图集
  is_video: boolean
  duration?: number
}

// 作品列表响应
export interface UserWorksResponse {
  data: UserWork[]
  has_more: boolean
  cursor: number
}

export type UserWorksPayload = UserWork[] | UserWorksResponse

// 获取用户信息（通过 URL）
export function getUserInfo(url: string) {
  return request.post<ApiResponse<UserInfo>>('/douyin/user/info', { url })
}

// 获取用户信息（通过 sec_uid）- store 使用
export function getUserInfoBySecUid(sec_uid: string) {
  return request.post<ApiResponse<UserInfo>>('/douyin/user/info', { sec_uid })
}

// 获取用户作品列表（通过 URL）
export function getUserWorks(url: string, limit = 20) {
  return request.post<ApiResponse<UserWork[]>>('/douyin/user/works', { url, limit })
}

// 获取用户作品列表（通过 sec_uid）- store 使用
export function getUserVideos(params: { sec_uid: string; cursor?: number; count?: number }) {
  return request.post<ApiResponse<UserWorksPayload>>('/douyin/user/works', params)
}

// 获取用户喜欢列表 - store 使用
export function getUserLikes(params: { sec_uid: string; cursor?: number; count?: number }) {
  return request.post<ApiResponse<UserWorksResponse>>('/douyin/user/likes', params)
}

// 下载结果
export interface DownloadResult {
  title: string
  author: string
  aweme_id: string
  video_url?: string
  video_qualities?: Record<string, VideoQuality>
  images?: string[]
  filename?: string
  selected_quality?: string
}

// 下载用户作品
export function downloadUserWork(params: { url?: string; aweme_id?: string; save_type?: string; quality?: string }) {
  return request.post<ApiResponse<DownloadResult>>('/douyin/work/download', params)
}
