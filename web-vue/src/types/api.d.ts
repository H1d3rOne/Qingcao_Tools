// API 响应通用类型
export interface ApiResponse<T = any> {
  code: number
  message: string
  data: T
}

// 分页响应
export interface PaginationResponse<T> {
  data: T[]
  has_more: boolean
  cursor: number
  total?: number
}

// 视频/作品类型
export interface Video {
  aweme_id: string
  desc: string
  create_time: number
  cover?: Cover | string
  cover_url?: string  // 后端返回的封面URL
  video?: VideoInfo
  video_url?: string  // 后端返回的视频URL
  video_qualities?: Record<string, VideoQuality>
  images?: string[]   // 后端返回的图片列表
  statistics?: Statistics
  author?: Author
  author_uid?: string
  author_nickname?: string
  author_avatar?: string
  author_sec_uid?: string
  music?: Music
  share_info?: ShareInfo
  text_extra?: TextExtra[]
  is_top?: number
  duration?: number
  is_video?: boolean
}

export interface VideoQuality {
  quality_type: number
  url: string
  width?: number
  height?: number
}

export interface Cover {
  url_list: string[]
  uri?: string
}

export interface VideoInfo {
  play_addr: PlayAddr
  cover: Cover
  width: number
  height: number
  ratio: string
  duration: number
}

export interface PlayAddr {
  url_list: string[]
  uri: string
}

export interface Image {
  url_list: string[]
  uri: string
  width: number
  height: number
}

export interface Statistics {
  play_count: number
  digg_count: number
  comment_count: number
  share_count: number
  collect_count: number
  forward_count?: number
}

export interface UserWorksResponse {
  data: Video[]
  has_more: boolean
  cursor: number
}

export interface UserInfo {
  uid: string
  sec_uid: string
  nickname: string
  signature: string
  avatar?: string
  gender?: number
  user_age?: number
  ip_location?: string
  country?: string
  follower_count: number
  following_count: number
  aweme_count: number
  favoriting_count?: number
  is_verify?: number
  verify_info?: string
  unique_id?: string
}

export interface Avatar {
  url_list: string[]
  uri: string
}

export interface Music {
  id: string
  title: string
  author: string
  cover_thumb: Avatar
  play_url: PlayAddr
}

export interface ShareInfo {
  share_url: string
  share_title: string
  share_desc: string
}

export interface TextExtra {
  text: string
  type: number
  hashtag_name?: string
  aweme_id?: string
}

// 评论类型
export interface Comment {
  cid: string
  text: string
  create_time: number
  digg_count: number
  user: CommentUser
  reply_comment?: Comment[]
  reply_count?: number
}

export interface CommentUser {
  uid: string
  nickname: string
  avatar?: string
}

// 作者类型 (用于视频作者)
export interface Author {
  uid: string
  sec_uid: string
  nickname: string
  avatar?: string
  signature?: string
  follower_count?: number
  following_count?: number
  aweme_count?: number
  favoriting_count?: number
  is_verify?: number
  verify_info?: string
  unique_id?: string
}

// 用户类型
export interface User {
  uid: string
  sec_uid: string
  nickname: string
  signature: string
  avatar?: string
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
  unique_id?: string
  short_id?: string
  province?: string
  city?: string
  location?: string
  birthday?: string
  school?: string
}

// 直播类型
export interface LiveRoom {
  room_id: string
  owner: Author
  title: string
  cover: Cover
  user_count: number
  like_count: number
  status: number
  create_time: number
  stream_url?: StreamUrl
}

export interface StreamUrl {
  rtmp_pull_url: string
  hls_pull_url: string
  flv_pull_url: string
}

// 搜索类型
export interface SearchParams {
  keyword: string
  cursor?: number
  count?: number
  sort_type?: number
  publish_time?: number
  filter_duration?: number
}

export interface SearchResult<T> {
  data: T[]
  has_more: boolean
  cursor: number
}

// 下载类型
export interface DownloadParams {
  aweme_id: string
  type: 'video' | 'image'
  index?: number
}

export interface DownloadResult {
  url: string
  filename: string
  size: number
}
