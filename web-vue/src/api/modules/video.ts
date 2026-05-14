import { request } from '../request'

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

// 视频质量
export interface VideoQuality {
  quality_type: number
  url: string
  width?: number
  height?: number
}

// 作品信息
export interface WorkInfo {
  aweme_id: string
  title: string
  desc: string
  author_nickname: string
  author_uid: string
  author_avatar: string
  create_time: number
  digg_count: number
  comment_count: number
  share_count: number
  collect_count: number
  play_count: number
  cover_url: string
  video_url: string
  video_qualities?: Record<string, VideoQuality>
  images: string[]
  is_video: boolean
  duration: number
  music_title: string
}

// 评论
export interface Comment {
  cid: string
  text: string
  create_time: number
  digg_count: number
  user: {
    uid: string
    nickname: string
    avatar: string
  }
  reply_comment?: Comment[]
}

// 评论响应
interface CommentsResponse {
  data: Comment[]
  has_more: boolean
  cursor: number
}

// 获取作品信息（通过 URL）
export function getWorkInfo(url: string) {
  return request.post<ApiResponse<WorkInfo>>('/douyin/work/info', { url })
}

// 获取作品信息（通过 aweme_id）- store 使用
export function getVideoInfo(aweme_id: string) {
  return request.post<ApiResponse<WorkInfo>>('/douyin/work/info', { aweme_id })
}

// 获取作品评论（通过 URL）
export function getWorkComments(url: string, limit = 20) {
  return request.post<ApiResponse<Comment[]>>('/douyin/work/comments', { url, limit })
}

// 获取作品评论（通过 aweme_id）- store 使用
export function getVideoComments(params: { aweme_id: string; cursor?: number; count?: number }) {
  return request.post<ApiResponse<CommentsResponse>>('/douyin/work/comments', params)
}

// 下载作品（通过 URL）
export function downloadWork(url: string, saveType: 'media' | 'video' | 'image' = 'media', quality: string = 'super') {
  return request.post<ApiResponse<{ 
    title: string
    author: string
    aweme_id: string
    video_url?: string
    video_qualities?: Record<string, VideoQuality>
    images?: string[]
    filename?: string
    selected_quality?: string
  }>>('/douyin/work/download', { 
    url, 
    save_type: saveType,
    quality
  })
}

// 下载作品（通过 URL）- composable 使用
export function downloadVideo(url: string, saveType: 'media' | 'video' | 'image' = 'media', quality: string = 'super') {
  return request.post<ApiResponse<{ 
    title: string
    author: string
    aweme_id: string
    video_url?: string
    video_qualities?: Record<string, VideoQuality>
    images?: string[]
    filename?: string
    selected_quality?: string
  }>>('/douyin/work/download', { 
    url, 
    save_type: saveType,
    quality
  })
}
