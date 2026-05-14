import { request } from '../request'

// API 响应类型
interface ApiResponse<T = any> {
  success: boolean
  data: T
  error?: string
  message?: string
  total?: number
}

// 搜索结果
interface SearchResult<T> {
  keyword: string
  total: number
  items: T[]
}

// 搜索视频项 - 匹配后端 _parse_work_info 返回的完整字段
export interface SearchVideo {
  aweme_id: string
  title: string
  desc: string
  author_uid: string
  author_nickname: string
  author_avatar: string
  author_sec_uid: string
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

// 搜索用户项 - 匹配后端 _parse_user_info 返回的完整字段
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

// 搜索直播项 - 匹配后端 _parse_live_info_v3 返回的完整字段
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

// 分页响应适配器
interface PaginatedResponse<T> {
  data: T[]
  has_more: boolean
  cursor: number
}

// 搜索作品
export function searchVideos(params: { 
  keyword: string
  limit?: number
  sort_type?: string
  publish_time?: string
  filter_duration?: string
  content_type?: string
  cursor?: number
  count?: number
}) {
  const { keyword, cursor, count, ...rest } = params
  return request.post<ApiResponse<SearchResult<SearchVideo>>>('/douyin/search/work', { 
    keyword, 
    limit: count || 20,
    ...rest
  }).then(res => ({
    data: {
      data: res.data?.items || [],
      has_more: false,
      cursor: 0
    }
  }))
}

// 搜索用户
export function searchUsers(params: { keyword: string; limit?: number; cursor?: number; count?: number }) {
  const { keyword, cursor, count } = params
  return request.post<ApiResponse<SearchResult<SearchUser>>>('/douyin/search/user', { 
    keyword, 
    limit: count || 20 
  }).then(res => ({
    data: {
      data: res.data?.items || [],
      has_more: false,
      cursor: 0
    }
  }))
}

// 搜索直播
export function searchLive(params: { keyword: string; limit?: number; cursor?: number; count?: number }) {
  const { keyword, cursor, count } = params
  return request.post<ApiResponse<SearchResult<SearchLive>>>('/douyin/search/live', { 
    keyword, 
    limit: count || 20 
  }).then(res => ({
    data: {
      data: res.data?.items || [],
      has_more: false,
      cursor: 0
    }
  }))
}
