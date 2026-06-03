import { request } from '../request'

// API 响应类型
interface ApiResponse<T = any> {
  success: boolean
  data: T
  error?: string
  message?: string
}

// 搜索视频项 - 匹配后端 _parse_work_info 返回的完整字段
export interface SearchVideo {
  aweme_id: string
  title: string
  desc: string
  author?: string
  author_uid: string
  author_nickname: string
  author_avatar: string
  author_sec_uid: string
  cover?: string
  cover_url: string
  video_url: string | null
  video_qualities?: Record<string, {
    quality_type: number
    url: string
    width: number
    height: number
  }> | null
  images?: string[] | null
  duration: number
  music_title: string
  music_url: string | null
  digg_count: number
  comment_count: number
  share_count: number
  collect_count: number
  play_count: number
  is_video: boolean
  create_time: number
  work_url: string
}

// 搜索用户项
export interface SearchUser {
  uid: string
  sec_uid: string
  unique_id: string
  nickname: string
  gender: number
  user_age: number
  ip_location: string
  country: string
  signature: string
  avatar: string
  follower_count: number
  following_count: number
  aweme_count: number
  favoriting_count: number
}

// 搜索直播项
export interface SearchLive {
  room_id: string
  title: string
  user_count: number
  author_nickname: string
  author_sec_uid: string
  author_avatar: string
  cover: string
  stream_url?: {
    hls: string
    flv: string
    rtmp: string
  }
}

// 分页搜索结果
interface SearchPageResult<T> {
  keyword: string
  data?: T[]
  items: T[]
  has_more: boolean
  next_offset: string
  search_id?: string
}

// 搜索作品（综合）
export function searchVideos(params: {
  keyword: string
  offset?: string
  count?: number
  search_id?: string
  sort_type?: string
  publish_time?: string
  filter_duration?: string
  search_range?: string
  content_type?: string
}) {
  return request.post<ApiResponse<SearchPageResult<SearchVideo>>>('/douyin/search/work', params)
}

// 视频搜索
export function searchVideoSearch(params: {
  keyword: string
  offset?: string
  count?: number
  search_id?: string
  sort_type?: string
  publish_time?: string
  filter_duration?: string
  search_range?: string
}) {
  return request.post<ApiResponse<SearchPageResult<SearchVideo>>>('/douyin/search/video', params)
}

// 搜索用户
export function searchUsers(params: {
  keyword: string
  offset?: string
  cursor?: number
  count?: number
  limit?: number
  search_id?: string
}) {
  return request.post<ApiResponse<SearchPageResult<SearchUser>>>('/douyin/search/user', params)
}

// 搜索直播
export function searchLive(params: { keyword: string; offset?: string; count?: number }) {
  return request.post<ApiResponse<SearchPageResult<SearchLive>>>('/douyin/search/live', params)
}
