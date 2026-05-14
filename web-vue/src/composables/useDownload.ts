import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { downloadVideo } from '@/api'

export function useDownload() {
  const downloading = ref(false)
  const progress = ref(0)

  async function download(aweme_id: string, filename?: string) {
    if (downloading.value) return

    downloading.value = true
    progress.value = 0

    try {
      const res = await downloadVideo(aweme_id)
      
      if (res.data?.url) {
        // 创建下载链接
        const link = document.createElement('a')
        link.href = res.data.url
        link.download = filename || res.data.filename || `${aweme_id}.mp4`
        link.target = '_blank'
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        
        ElMessage.success('开始下载')
      }
      
      return res.data
    } catch (error) {
      console.error('下载失败:', error)
      ElMessage.error('下载失败')
      throw error
    } finally {
      downloading.value = false
      progress.value = 100
    }
  }

  async function batchDownload(aweme_ids: string[]) {
    if (downloading.value) return

    downloading.value = true
    progress.value = 0

    try {
      const results = []
      const total = aweme_ids.length

      for (let i = 0; i < total; i++) {
        try {
          const res = await downloadVideo(aweme_ids[i])
          results.push(res.data)
          progress.value = Math.round(((i + 1) / total) * 100)
        } catch (error) {
          console.error(`下载 ${aweme_ids[i]} 失败:`, error)
        }
      }

      ElMessage.success(`成功下载 ${results.length}/${total} 个视频`)
      return results
    } finally {
      downloading.value = false
    }
  }

  return {
    downloading,
    progress,
    download,
    batchDownload
  }
}
