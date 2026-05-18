/**
 * 从文本中提取 URL（支持抖音分享文本中夹带的链接）
 */
export function extractUrl(text: string): string {
  if (!text) return text
  const match = text.match(/https?:\/\/[^\s]+/)
  return match ? match[0] : text.trim()
}
