/**
 * 格式化数字（如 12345 -> 1.2万）
 */
export function formatNumber(num?: number): string {
  if (!num && num !== 0) return '0'
  
  if (num >= 100000000) {
    return (num / 100000000).toFixed(1) + '亿'
  }
  
  if (num >= 10000) {
    return (num / 10000).toFixed(1) + '万'
  }
  
  return num.toLocaleString()
}

/**
 * 格式化时间戳
 */
export function formatTime(timestamp?: number, format = 'YYYY-MM-DD HH:mm'): string {
  if (!timestamp) return ''
  
  const date = new Date(timestamp * 1000)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  const seconds = String(date.getSeconds()).padStart(2, '0')
  
  return format
    .replace('YYYY', String(year))
    .replace('MM', month)
    .replace('DD', day)
    .replace('HH', hours)
    .replace('mm', minutes)
    .replace('ss', seconds)
}

/**
 * 格式化时长（秒 -> mm:ss）
 */
export function formatDuration(seconds?: number): string {
  if (!seconds) return '00:00'
  
  const minutes = Math.floor(seconds / 60)
  const secs = seconds % 60
  
  return `${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
}

/**
 * 格式化文件大小
 */
export function formatFileSize(bytes?: number): string {
  if (!bytes) return '0 B'
  
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0
  let size = bytes
  
  while (size >= 1024 && i < units.length - 1) {
    size /= 1024
    i++
  }
  
  return size.toFixed(2) + ' ' + units[i]
}

/**
 * 截断文本
 */
export function truncate(text?: string, length = 100): string {
  if (!text) return ''
  if (text.length <= length) return text
  return text.slice(0, length) + '...'
}

/**
 * 提取 URL 中的视频 ID
 */
export function extractVideoId(url: string): string | null {
  // 支持多种抖音链接格式
  const patterns = [
    /video\/(\d+)/,
    /aweme_id=(\d+)/,
    /modal_id=(\d+)/,
    /\/(\d{19})\//
  ]
  
  for (const pattern of patterns) {
    const match = url.match(pattern)
    if (match) return match[1]
  }
  
  return null
}

/**
 * 提取 URL 中的用户 sec_uid
 */
export function extractSecUid(url: string): string | null {
  const patterns = [
    /user\/([^?/]+)/,
    /sec_uid=([^&]+)/
  ]
  
  for (const pattern of patterns) {
    const match = url.match(pattern)
    if (match) return match[1]
  }
  
  return null
}
