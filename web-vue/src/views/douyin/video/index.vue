<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import { getWorkInfo, getWorkComments } from '@/api'
import type { WorkInfo, Comment } from '@/api/modules/video'
import { useNotification } from '@/composables'

const router = useRouter()
const { error, success } = useNotification()

const inputUrl = ref('')
const loading = ref(false)
const workInfo = ref<WorkInfo | null>(null)
const comments = ref<Comment[]>([])
const selectedQuality = ref('super')
const showQualityPanel = ref(false)
const showComments = ref(false)
const showDownloadDropdown = ref(false)

// 下载相关
const downloading = ref(false)
const downloadComplete = ref(false)
const downloadProgress = ref(0)
const downloadFilename = ref('')
const downloadedBytes = ref(0)
const totalBytes = ref(0)
const downloadStartTime = ref(0)
const abortController = ref<AbortController | null>(null)
const downloadedBlob = ref<Blob | null>(null)

const qualityOptions = [
  { value: 'hd2k', label: '2K', desc: '超高清' },
  { value: 'super', label: '超清', desc: '1080P' },
  { value: 'high', label: '高清', desc: '720P' },
  { value: 'standard', label: '标清', desc: '480P' }
]

const availableQualities = computed(() => {
  if (!workInfo.value?.video_qualities) return []
  const qualities = workInfo.value.video_qualities
  return qualityOptions.filter(q => qualities[q.value])
})

const originalVideoUrl = computed(() => {
  if (!workInfo.value) return null
  const qualities = workInfo.value.video_qualities
  if (qualities && qualities[selectedQuality.value]) {
    return qualities[selectedQuality.value].url
  }
  return workInfo.value.video_url
})

const currentVideoUrl = computed(() => {
  if (!originalVideoUrl.value) return null
  return `/api/v1/douyin/work/proxy?url=${encodeURIComponent(originalVideoUrl.value)}`
})

const currentQualityLabel = computed(() => {
  const q = qualityOptions.find(o => o.value === selectedQuality.value)
  return q ? q.label : ''
})

const downloadedSize = computed(() => formatSize(downloadedBytes.value))
const totalSize = computed(() => formatSize(totalBytes.value))
const downloadSpeed = computed(() => {
  if (downloadedBytes.value === 0 || !downloadStartTime.value) return ''
  const elapsed = (Date.now() - downloadStartTime.value) / 1000
  const speed = downloadedBytes.value / elapsed
  return `${formatSize(speed)}/s`
})

function formatSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

function formatNumber(num: number): string {
  if (num >= 10000) return (num / 10000).toFixed(1) + 'w'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'k'
  return num.toString()
}

async function handleSearch() {
  if (!inputUrl.value.trim()) {
    error('请输入视频链接')
    return
  }

  loading.value = true
  workInfo.value = null
  comments.value = []
  
  try {
    const res = await getWorkInfo(inputUrl.value.trim())
    workInfo.value = res.data
    
    if (res.data.video_qualities) {
      for (const q of ['super', 'high', 'standard', 'hd2k']) {
        if (res.data.video_qualities[q]) {
          selectedQuality.value = q
          break
        }
      }
    }
    
    success('查询成功')
    loadComments()
  } catch (err) {
    // console.error('查询失败:', err)
  } finally {
    loading.value = false
  }
}

async function loadComments() {
  if (!inputUrl.value.trim()) return
  
  try {
    const res = await getWorkComments(inputUrl.value.trim(), 50)
    comments.value = res.data || []
  } catch (err) {
    console.error('获取评论失败:', err)
  }
}

function handlePaste() {
  navigator.clipboard.readText().then(text => {
    inputUrl.value = text
  })
}

function selectQuality(quality: string) {
  selectedQuality.value = quality
  showQualityPanel.value = false
}

async function startDownload(quality: string) {
  const videoUrl = workInfo.value?.video_qualities?.[quality]?.url || workInfo.value?.video_url
  if (!videoUrl) {
    error('视频链接不可用')
    return
  }

  downloadFilename.value = `${workInfo.value?.title || workInfo.value?.aweme_id || 'video'}_${quality}.mp4`
  downloading.value = true
  downloadComplete.value = false
  downloadProgress.value = 0
  downloadedBytes.value = 0
  totalBytes.value = 0
  downloadStartTime.value = Date.now()
  showQualityPanel.value = false
  showDownloadDropdown.value = false

  abortController.value = new AbortController()

  try {
    const proxyUrl = `/api/v1/douyin/work/proxy?url=${encodeURIComponent(videoUrl)}`
    const response = await fetch(proxyUrl, { signal: abortController.value.signal })

    if (!response.ok) throw new Error(`HTTP ${response.status}`)

    const contentLength = response.headers.get('content-length')
    totalBytes.value = contentLength ? parseInt(contentLength, 10) : 0

    const reader = response.body?.getReader()
    if (!reader) throw new Error('无法读取响应流')

    const chunks: Uint8Array[] = []
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      chunks.push(value)
      downloadedBytes.value += value.length
      if (totalBytes.value > 0) {
        downloadProgress.value = Math.min(100, Math.round((downloadedBytes.value / totalBytes.value) * 100))
      }
    }

    downloadedBlob.value = new Blob(chunks as BlobPart[], { type: 'video/mp4' })
    downloadProgress.value = 100
    downloadComplete.value = true
    downloading.value = false
    success('下载完成')
  } catch (error: any) {
    if (error.name !== 'AbortError') {
      console.error('下载失败:', error)
      error('下载失败')
    }
    downloading.value = false
  }
}

function cancelDownload() {
  if (abortController.value) {
    abortController.value.abort()
  }
  downloading.value = false
  downloadComplete.value = false
}

function saveFile() {
  if (!downloadedBlob.value) return
  const url = URL.createObjectURL(downloadedBlob.value)
  const a = document.createElement('a')
  a.href = url
  a.download = downloadFilename.value
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
  downloadComplete.value = false
  downloadedBlob.value = null
}

function formatTime(timestamp: number) {
  return new Date(timestamp * 1000).toLocaleString('zh-CN')
}
</script>

<template>
  <div class="video-page">
    <!-- 搜索栏 -->
    <div class="search-bar">
      <el-input
        v-model="inputUrl"
        placeholder="粘贴抖音视频链接..."
        size="large"
        clearable
        @keyup.enter="handleSearch"
      >
        <template #prefix>
          <el-icon><Link /></el-icon>
        </template>
      </el-input>
      <el-button
        type="primary"
        size="large"
        :loading="loading"
        @click="handleSearch"
      >
        查询
      </el-button>
      <el-button
        size="large"
        @click="handlePaste"
      >
        <el-icon><DocumentCopy /></el-icon>
      </el-button>
    </div>

    <!-- 视频信息区 -->
    <div
      v-if="workInfo"
      class="video-content"
    >
      <!-- 返回按钮 -->
      <div class="back-row">
        <el-button @click="router.back()">
          <el-icon class="mr-1">
            <ArrowLeft />
          </el-icon>
          返回
        </el-button>
      </div>
      
      <!-- 第一行：作者信息 -->
      <div class="author-row">
        <img
          :src="workInfo.author_avatar"
          class="author-avatar"
        >
        <div class="author-info">
          <span class="author-name">{{ workInfo.author_nickname }}</span>
        </div>
      </div>

      <!-- 第二行：标题 -->
      <div class="title-row">
        {{ workInfo.title }}
      </div>

      <!-- 第三行：视频播放器 -->
      <div class="video-row">
        <div class="video-player">
          <video
            v-if="currentVideoUrl"
            :src="currentVideoUrl"
            :poster="workInfo.cover_url"
            controls
            playsinline
            webkit-playsinline
            preload="metadata"
          />
          <img
            v-else
            :src="workInfo.cover_url"
          >

          <!-- 右下角浮动按钮（竖向排列） -->
          <div class="video-actions">
            <div class="action-item">
              <el-icon><VideoPlay /></el-icon>
              <span>{{ formatNumber(workInfo.play_count) }}</span>
            </div>
            <div class="action-item">
              <el-icon><Star /></el-icon>
              <span>{{ formatNumber(workInfo.digg_count) }}</span>
            </div>
            <div
              class="action-item"
              @click="showComments = true"
            >
              <el-icon><ChatDotRound /></el-icon>
              <span>{{ formatNumber(workInfo.comment_count) }}</span>
            </div>
            <div class="action-item">
              <el-icon><Share /></el-icon>
              <span>{{ formatNumber(workInfo.share_count) }}</span>
            </div>
            <div
              class="action-item quality-btn"
              @click="showQualityPanel = !showQualityPanel"
            >
              <el-icon><Film /></el-icon>
              <span>{{ currentQualityLabel }}</span>
            </div>
          </div>

          <!-- 画质选择浮层（在按钮左边） -->
          <transition name="fade">
            <div
              v-if="showQualityPanel"
              class="quality-panel"
            >
              <div
                v-for="q in qualityOptions"
                :key="q.value"
                class="quality-item"
                :class="{ active: selectedQuality === q.value, disabled: !workInfo.video_qualities?.[q.value] }"
                @click="workInfo.video_qualities?.[q.value] && selectQuality(q.value)"
              >
                <span class="q-name">{{ q.label }}</span>
                <el-icon
                  v-if="selectedQuality === q.value"
                  color="rgb(var(--primary-color-rgb))"
                >
                  <Check />
                </el-icon>
              </div>
            </div>
          </transition>
        </div>
      </div>

      <!-- 第四行：描述 -->
      <div class="desc-row">
        {{ workInfo.desc }}
      </div>

      <!-- 第五行：时间 -->
      <div class="time-row">
        <span>{{ formatTime(workInfo.create_time) }}</span>
        <span v-if="workInfo.duration"> · {{ workInfo.duration }}秒</span>
      </div>

      <!-- 第六行：下载按钮 -->
      <div class="download-row">
        <div class="download-btn-wrapper">
          <el-button
            type="primary"
            :disabled="downloading"
            @click="showDownloadDropdown = !showDownloadDropdown"
          >
            <el-icon class="mr-1">
              <Download />
            </el-icon>
            下载视频
            <el-icon class="ml-1">
              <ArrowDown />
            </el-icon>
          </el-button>
          <!-- 下载画质下拉框 -->
          <transition name="slide-down">
            <div
              v-if="showDownloadDropdown"
              class="download-dropdown"
            >
              <div
                v-for="q in qualityOptions"
                :key="q.value"
                class="dropdown-item"
                :class="{ disabled: !workInfo.video_qualities?.[q.value] }"
                @click="workInfo.video_qualities?.[q.value] && startDownload(q.value)"
              >
                <span>{{ q.label }}</span>
                <span class="dropdown-desc">{{ q.desc }}</span>
              </div>
            </div>
          </transition>
        </div>
      </div>

      <!-- 第七行：下载进度 -->
      <transition name="slide-up">
        <div
          v-if="downloading || downloadComplete"
          class="progress-row"
        >
          <div class="progress-header">
            <div class="progress-info">
              <el-icon
                v-if="downloadComplete"
                color="rgb(var(--primary-color-rgb))"
              >
                <CircleCheck />
              </el-icon>
              <el-icon
                v-else
                class="is-loading"
                color="rgb(var(--primary-color-rgb))"
              >
                <Loading />
              </el-icon>
              <span class="progress-filename">{{ downloadFilename }}</span>
              <el-tag
                size="small"
                type="primary"
              >
                {{ currentQualityLabel }}
              </el-tag>
            </div>
            <el-button
              v-if="downloadComplete"
              type="primary"
              size="small"
              @click="saveFile"
            >
              保存
            </el-button>
            <el-button
              v-else
              size="small"
              @click="cancelDownload"
            >
              取消
            </el-button>
          </div>
          <el-progress
            :percentage="downloadProgress"
            :stroke-width="6"
          />
          <div class="progress-stats">
            <span>{{ downloadedSize }} / {{ totalSize }}</span>
            <span v-if="!downloadComplete">{{ downloadSpeed }}</span>
            <span>{{ downloadProgress }}%</span>
          </div>
        </div>
      </transition>
    </div>

    <!-- 评论抽屉 -->
    <el-drawer
      v-model="showComments"
      title="评论"
      size="400px"
      direction="rtl"
    >
      <div class="comments-list">
        <div
          v-for="comment in comments"
          :key="comment.cid"
          class="comment-item"
        >
          <img
            :src="comment.user?.avatar"
            class="comment-avatar"
          >
          <div class="comment-content">
            <div class="comment-header">
              <span class="comment-user">{{ comment.user?.nickname }}</span>
            </div>
            <div class="comment-text-row">
              <span class="comment-text">{{ comment.text }}</span>
              <div class="comment-like">
                <el-icon><Star /></el-icon>
                <span>{{ comment.digg_count || 0 }}</span>
              </div>
            </div>
            <div class="comment-time">
              {{ formatTime(comment.create_time) }}
            </div>
          </div>
        </div>
        <EmptyState
          v-if="comments.length === 0"
          text="暂无评论"
        />
      </div>
    </el-drawer>

    <!-- 空状态 -->
    <div
      v-if="!workInfo"
      class="empty-state"
    >
      <el-icon class="empty-icon">
        <VideoPlay />
      </el-icon>
      <h3>输入视频链接开始</h3>
      <p>粘贴抖音视频分享链接，获取视频信息和下载</p>
    </div>
  </div>
</template>

<style scoped>
.video-page {
  max-width: 800px;
  margin: 0 auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 24px;
  min-height: 100%;
}

.search-bar {
  display: flex;
  gap: 12px;
  padding: 18px;
  margin-top: 8vh;
  border-radius: 16px;
  border: 1.5px solid rgba(var(--app-border-rgb) / 0.7);
  background: rgba(var(--app-surface-rgb) / 0.95);
  box-shadow:
    0 8px 20px rgba(var(--app-shadow-rgb) / 0.08),
    inset 0 1px 0 rgba(var(--utility-white-rgb) / 0.6);
}

.search-bar .el-input {
  flex: 1;
}

.video-content {
  border-radius: 16px;
  padding: 24px;
  border: 1.5px solid rgba(var(--app-border-rgb) / 0.7);
  background: rgba(var(--app-surface-rgb) / 0.95);
  box-shadow:
    0 8px 24px rgba(var(--app-shadow-rgb) / 0.08),
    inset 0 1px 0 rgba(var(--utility-white-rgb) / 0.5);
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.back-row {
  padding-bottom: 16px;
  border-bottom: 1.5px solid rgba(var(--app-border-rgb) / 0.5);
}

.author-row {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 18px;
  border-radius: 14px;
  border: 1.5px solid rgba(var(--app-border-rgb) / 0.55);
  background: rgba(var(--app-surface-alt-rgb) / 0.8);
}

.author-avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  object-fit: cover;
  border: 2px solid rgba(var(--app-border-rgb) / 0.6);
}

.author-name {
  font-size: 16px;
  font-weight: 600;
  color: rgb(var(--app-text-strong-rgb));
}

.title-row {
  font-size: 18px;
  font-weight: 600;
  color: rgb(var(--app-text-strong-rgb));
  line-height: 1.5;
  padding: 16px 18px;
  border-radius: 12px;
  background: rgba(var(--app-surface-alt-rgb) / 0.7);
  border: 1.5px solid rgba(var(--app-border-rgb) / 0.5);
}

.video-row {
  margin: 4px 0;
}

.video-player {
  position: relative;
  width: 100%;
  aspect-ratio: 16/9;
  background: rgb(var(--app-text-strong-rgb));
  border-radius: 14px;
  overflow: hidden;
  border: 1.5px solid rgba(var(--app-border-rgb) / 0.5);
  box-shadow: 0 8px 24px rgba(var(--app-shadow-rgb) / 0.12);
}

.video-player video,
.video-player img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.video-actions {
  position: absolute;
  right: 14px;
  bottom: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.action-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 10px 14px;
  background: rgba(var(--app-text-strong-rgb) / 0.65);
  backdrop-filter: blur(8px);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.action-item:hover {
  background: rgba(var(--app-text-strong-rgb) / 0.82);
  transform: scale(1.05);
}

.action-item .el-icon {
  font-size: 22px;
  color: rgb(var(--utility-white-rgb));
}

.action-item span {
  font-size: 11px;
  color: rgb(var(--utility-white-rgb));
}

.quality-panel {
  position: absolute;
  right: 62px;
  bottom: 14px;
  background: rgba(var(--app-surface-rgb) / 0.96);
  backdrop-filter: blur(12px);
  border: 1.5px solid rgba(var(--app-border-rgb) / 0.7);
  border-radius: 14px;
  padding: 10px;
  min-width: 90px;
  box-shadow: 0 8px 24px rgba(var(--app-shadow-rgb) / 0.12);
}

.quality-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
}

.quality-item:hover:not(.disabled) {
  background: rgba(var(--primary-color-rgb) / 0.12);
}

.quality-item.active {
  background: rgba(var(--primary-color-rgb) / 0.18);
}

.quality-item.disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.q-name {
  font-size: 14px;
  font-weight: 500;
  color: rgb(var(--app-text-rgb));
}

.desc-row {
  font-size: 14px;
  color: rgb(var(--app-text-muted-rgb));
  line-height: 1.7;
  padding: 16px 18px;
  border-radius: 12px;
  background: rgba(var(--app-surface-alt-rgb) / 0.75);
  border: 1.5px solid rgba(var(--app-border-rgb) / 0.5);
}

.time-row {
  font-size: 13px;
  color: rgb(var(--app-text-subtle-rgb));
  padding: 12px 0;
  border-top: 1.5px solid rgba(var(--app-border-rgb) / 0.4);
}

.download-row {
  padding-top: 20px;
  border-top: 1.5px solid rgba(var(--app-border-rgb) / 0.4);
}

.download-btn-wrapper {
  position: relative;
  display: inline-block;
}

.download-btn-wrapper .el-button {
  min-width: 140px;
}

.download-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  margin-top: 10px;
  background: rgba(var(--app-surface-rgb) / 0.98);
  border: 1.5px solid rgba(var(--app-border-rgb) / 0.7);
  border-radius: 14px;
  padding: 10px;
  min-width: 180px;
  z-index: 100;
  box-shadow: 0 8px 24px rgba(var(--app-shadow-rgb) / 0.12);
}

.dropdown-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  color: rgb(var(--app-text-rgb));
}

.dropdown-item:hover:not(.disabled) {
  background: rgba(var(--primary-color-rgb) / 0.12);
}

.dropdown-item.disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.dropdown-desc {
  font-size: 12px;
  color: rgb(var(--app-text-subtle-rgb));
}

.progress-row {
  border-radius: 14px;
  padding: 18px;
  border: 1.5px solid rgba(var(--app-border-rgb) / 0.6);
  background: rgba(var(--app-surface-alt-rgb) / 0.85);
  box-shadow: 0 6px 16px rgba(var(--app-shadow-rgb) / 0.06);
}

.progress-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.progress-info {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  overflow: hidden;
}

.progress-filename {
  font-size: 14px;
  font-weight: 500;
  color: rgb(var(--app-text-strong-rgb));
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.progress-stats {
  display: flex;
  justify-content: space-between;
  margin-top: 10px;
  font-size: 12px;
  color: rgb(var(--app-text-subtle-rgb));
}

.comments-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.comment-item {
  display: flex;
  gap: 14px;
  padding: 14px;
  border-radius: 14px;
  border: 1.5px solid rgba(var(--app-border-rgb) / 0.5);
  background: rgba(var(--app-surface-alt-rgb) / 0.7);
  transition: background 0.2s ease;
}

.comment-item:hover {
  background: rgba(var(--app-surface-alt-rgb) / 0.85);
}

.comment-avatar {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
  border: 1.5px solid rgba(var(--app-border-rgb) / 0.5);
}

.comment-content {
  flex: 1;
  min-width: 0;
}

.comment-header {
  margin-bottom: 8px;
}

.comment-user {
  font-size: 15px;
  font-weight: 600;
  color: rgb(var(--app-text-strong-rgb));
}

.comment-text-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.comment-text {
  flex: 1;
  font-size: 15px;
  color: rgb(var(--app-text-rgb));
  line-height: 1.7;
  word-break: break-word;
}

.comment-like {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: rgb(var(--app-text-subtle-rgb));
  flex-shrink: 0;
}

.comment-like .el-icon {
  font-size: 16px;
}

.comment-time {
  font-size: 12px;
  color: rgb(var(--app-text-subtle-rgb));
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(var(--app-border-rgb) / 0.35);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  color: rgb(var(--app-text-muted-rgb));
  margin: auto 0;
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 20px;
  color: rgb(var(--app-text-subtle-rgb));
}

.empty-state h3 {
  font-size: 20px;
  color: rgb(var(--app-text-strong-rgb));
  margin-bottom: 10px;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.slide-down-enter-active,
.slide-down-leave-active {
  transition: all 0.2s ease;
}

.slide-down-enter-from,
.slide-down-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

.slide-up-enter-active,
.slide-up-leave-active {
  transition: all 0.3s ease;
}

.slide-up-enter-from,
.slide-up-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

.is-loading {
  animation: rotating 2s linear infinite;
}

@keyframes rotating {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
