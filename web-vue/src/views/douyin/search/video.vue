<script setup lang="ts">
import { ref, onUnmounted, computed, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Search, Star, VideoPlay, ChatDotRound, Share, Collection, View, Picture, ArrowLeft, ArrowRight, Mute, Bell, Download, Check, Finished } from '@element-plus/icons-vue'
import { searchVideos, searchVideoSearch, searchUsers, searchLive, downloadUserWork } from '@/api'
import type { SearchVideo, SearchUser, SearchLive } from '@/api/modules/search'
import { useNotification } from '@/composables'
import { useSearchStore } from '@/stores'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import EmptyState from '@/components/common/EmptyState.vue'

// 定义组件名称，用于 keep-alive
defineOptions({
  name: 'DouyinSearch'
})

const router = useRouter()
const { error, success } = useNotification()
const searchStore = useSearchStore()

const keyword = ref('')
const activeType = ref('general')
const loading = ref(false)

// 搜索条件
const searchFilters = ref({
  sortType: '0',           // 排序: 0综合, 1最多点赞, 2最新
  publishTime: '0',        // 发布时间: 0不限, 1一天内, 7一周内, 180半年内
  filterDuration: '',      // 视频时长: 空/不限, 0-60一分钟以下, 60-300一分钟到五分钟, 300-五分钟以上
  contentType: ''          // 内容形式: 空/不限, 0视频, 1图文
})

// 筛选选项
const sortOptions = [
  { label: '综合排序', value: '0' },
  { label: '最多点赞', value: '1' },
  { label: '最新发布', value: '2' }
]

const publishTimeOptions = [
  { label: '不限', value: '0' },
  { label: '一天内', value: '1' },
  { label: '一周内', value: '7' },
  { label: '半年内', value: '180' }
]

const durationOptions = [
  { label: '不限', value: '' },
  { label: '一分钟以下', value: '0-60' },
  { label: '1-5分钟', value: '60-300' },
  { label: '5分钟以上', value: '300-' }
]

const contentTypeOptions = [
  { label: '不限', value: '' },
  { label: '视频', value: '0' },
  { label: '图文', value: '1' }
]

const videoResults = ref<SearchVideo[]>([])
const userResults = ref<SearchUser[]>([])
const liveResults = ref<SearchLive[]>([])

// 当前悬停的作品ID
const hoveredVideoId = ref<string | null>(null)
// 视频元素引用
const videoRefs = ref<Map<string, HTMLVideoElement>>(new Map())
// 音频元素引用
const audioRefs = ref<Map<string, HTMLAudioElement>>(new Map())
// 轮播索引
const carouselIndexes = ref<Map<string, number>>(new Map())
// 全局静音状态
const isMuted = ref(true)

// 选中状态
const selectedVideoIds = ref<Set<string>>(new Set())
const isSelectMode = ref(false)

// 下载相关状态
const showDownloadPopover = ref(false)
const downloadingVideos = ref<SearchVideo[]>([])
const selectedQuality = ref('super')
const isDownloading = ref(false)
const downloadProgress = ref({ current: 0, total: 0 })

// 视频质量选项
const qualityOptions = [
  { value: 'standard', label: '标清', desc: '节省空间，清晰度较低' },
  { value: 'high', label: '高清', desc: '平衡清晰度与大小' },
  { value: 'super', label: '超清', desc: '高清画质，推荐使用' },
  { value: 'hd2k', label: '2K', desc: '最高画质，文件较大' },
]

// 计算属性
const selectedVideos = computed(() => {
  return videoResults.value.filter(v => selectedVideoIds.value.has(v.aweme_id))
})

const isAllSelected = computed(() => {
  return videoResults.value.length > 0 && selectedVideoIds.value.size === videoResults.value.length
})

const isIndeterminate = computed(() => {
  const size = selectedVideoIds.value.size
  return size > 0 && size < videoResults.value.length
})

// 切换选择模式
function toggleSelectMode() {
  isSelectMode.value = !isSelectMode.value
  if (!isSelectMode.value) {
    selectedVideoIds.value.clear()
  }
}

// 全选/取消全选
function toggleSelectAll() {
  if (isAllSelected.value) {
    selectedVideoIds.value.clear()
  } else {
    videoResults.value.forEach(v => selectedVideoIds.value.add(v.aweme_id))
  }
}

// 切换单个选中
function toggleVideoSelect(video: SearchVideo, event: Event) {
  event.stopPropagation()
  if (selectedVideoIds.value.has(video.aweme_id)) {
    selectedVideoIds.value.delete(video.aweme_id)
  } else {
    selectedVideoIds.value.add(video.aweme_id)
  }
}

// 打开下载弹窗
function openDownloadPopover() {
  if (selectedVideoIds.value.size === 0) {
    error('请先选择要下载的作品')
    return
  }
  downloadingVideos.value = selectedVideos.value
  showDownloadPopover.value = true
}

// 执行下载
async function executeDownload() {
  isDownloading.value = true
  downloadProgress.value = { current: 0, total: downloadingVideos.value.length }
  
  const failedVideos: string[] = []
  
  for (let i = 0; i < downloadingVideos.value.length; i++) {
    const video = downloadingVideos.value[i]
    downloadProgress.value.current = i + 1
    
    try {
      const res = await downloadUserWork({
        aweme_id: video.aweme_id,
        quality: selectedQuality.value,
        save_type: video.images && video.images.length > 0 ? 'image' : 'video'
      })
      
      if (res.data?.video_url) {
        await triggerDownload(res.data.video_url, video.desc || video.aweme_id)
      } else if (res.data?.images && res.data.images.length > 0) {
        for (let j = 0; j < res.data.images.length; j++) {
          await triggerDownload(res.data.images[j], `${video.desc || video.aweme_id}_${j + 1}`)
        }
      }
    } catch (err) {
      console.error(`下载失败: ${video.aweme_id}`, err)
      failedVideos.push(video.desc || video.aweme_id)
    }
    
    await new Promise(resolve => setTimeout(resolve, 500))
  }
  
  isDownloading.value = false
  
  if (failedVideos.length === 0) {
    success(`成功下载 ${downloadingVideos.value.length} 个作品`)
  } else {
    error(`部分下载失败: ${failedVideos.join(', ')}`)
  }
  
  showDownloadPopover.value = false
  selectedVideoIds.value.clear()
}

// 触发下载
async function triggerDownload(url: string, filename: string) {
  try {
    const proxyUrl = `/api/v1/douyin/work/proxy?url=${encodeURIComponent(url)}`
    const response = await fetch(proxyUrl)
    const blob = await response.blob()
    const downloadUrl = URL.createObjectURL(blob)
    
    const a = document.createElement('a')
    a.href = downloadUrl
    a.download = `${filename.replace(/[\\/:*?"<>|]/g, '_')}.mp4`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(downloadUrl)
  } catch (err) {
    console.error('下载失败:', err)
    throw err
  }
}

// 格式化数字
function formatNumber(num: number): string {
  if (num >= 10000) {
    return (num / 10000).toFixed(1) + 'w'
  }
  return num.toString()
}

// 解析标题中的话题标签 #xxx
interface TitlePart {
  text: string
  isHashtag: boolean
}

function parseHashtags(text: string): TitlePart[] {
  if (!text) return []
  
  // 匹配 #关键字（支持中文、英文、数字、下划线）
  const hashtagRegex = /(#[\u4e00-\u9fa5\w]+)/g
  const parts: TitlePart[] = []
  let lastIndex = 0
  let match
  
  while ((match = hashtagRegex.exec(text)) !== null) {
    // 添加前面的普通文本
    if (match.index > lastIndex) {
      parts.push({
        text: text.substring(lastIndex, match.index),
        isHashtag: false
      })
    }
    // 添加话题标签
    parts.push({
      text: match[0],
      isHashtag: true
    })
    lastIndex = match.index + match[0].length
  }
  
  // 添加剩余的普通文本
  if (lastIndex < text.length) {
    parts.push({
      text: text.substring(lastIndex),
      isHashtag: false
    })
  }
  
  return parts
}

// 点击话题标签搜索
let searchAbortController: AbortController | null = null

async function searchByHashtag(tag: string, event: Event) {
  event.stopPropagation()
  
  // 如果有正在进行的搜索，取消它
  if (searchAbortController) {
    searchAbortController.abort()
  }
  
  // 如果正在加载，直接返回
  if (loading.value) {
    return
  }
  
  // 去掉 # 符号，只保留关键字
  const kw = tag.substring(1)
  // 切换到作品搜索
  activeType.value = 'video'
  // 设置关键字并搜索
  keyword.value = kw
  // 先立即滚动到顶部
  const scrollContainer = document.getElementById('main-scroll-container')
  if (scrollContainer) {
    scrollContainer.scrollTo({ top: 0, behavior: 'smooth' })
  } else {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }
  // 然后执行搜索
  await handleSearch()
}

// 格式化发布时间
function formatCreateTime(timestamp: number): string {
  if (!timestamp) return ''
  const date = new Date(timestamp * 1000) // 转换为毫秒
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  
  const minute = 60 * 1000
  const hour = 60 * minute
  const day = 24 * hour
  const week = 7 * day
  const month = 30 * day
  const year = 365 * day
  
  if (diff < hour) {
    return Math.floor(diff / minute) + '分钟前'
  } else if (diff < day) {
    return Math.floor(diff / hour) + '小时前'
  } else if (diff < week) {
    return Math.floor(diff / day) + '天前'
  } else if (diff < month) {
    return Math.floor(diff / week) + '周前'
  } else if (diff < year) {
    return Math.floor(diff / month) + '月前'
  } else {
    return Math.floor(diff / year) + '年前'
  }
}

// 跳转到用户主页
function goToUserProfile(secUid: string, event: Event) {
  event.stopPropagation()
  // 保存当前搜索状态到 state，以便返回时恢复
  router.push({
    path: '/douyin/user',
    query: { sec_uid: secUid, from: 'search' }
  })
}

// 跳转到直播间
function goToLive(live: SearchLive) {
  // 跳转到直播查询页面，传递 room_id 和 stream_url
  router.push({
    path: '/douyin/live',
    query: { 
      room_id: live.room_id,
      // 如果有直播流地址，也传递过去
      ...(live.stream_url?.hls && { hls: live.stream_url.hls }),
      ...(live.stream_url?.flv && { flv: live.stream_url.flv }),
      ...(live.stream_url?.rtmp && { rtmp: live.stream_url.rtmp }),
      title: live.title,
      nickname: live.author_nickname,
      avatar: live.author_avatar,
      cover: live.cover
    }
  })
}

// 跳转到直播用户主页
function goToLiveUserProfile(secUid: string, event: Event) {
  event.stopPropagation()
  // 保存当前搜索状态到 state，以便返回时恢复
  router.push({
    path: '/douyin/user',
    query: { sec_uid: secUid, from: 'search' }
  })
}

// 判断是否为图文作品
function isImagePost(video: SearchVideo): boolean {
  return !!(video.images && video.images.length > 0)
}

// 获取代理视频URL - 用于绕过防盗链
function getProxyVideoUrl(url: string | null | undefined): string {
  if (!url) return ''
  return `/api/v1/douyin/work/proxy?url=${encodeURIComponent(url)}`
}

// 获取当前轮播索引
function getCarouselIndex(awemeId: string): number {
  return carouselIndexes.value.get(awemeId) || 0
}

// 鼠标悬停处理
function handleMouseEnter(video: SearchVideo) {
  hoveredVideoId.value = video.aweme_id

  if (isImagePost(video)) {
    // 图文作品：开始轮播和播放音乐
    startImageCarousel(video)
    if (!isMuted.value) {
      playMusic(video)
    }
  } else if (video.video_url) {
    // 视频作品：播放视频（始终静音预览）
    const videoEl = videoRefs.value.get(video.aweme_id)
    // console.log('悬停视频:', video.aweme_id, 'videoEl:', videoEl, 'video_url:', video.video_url)
    if (videoEl) {
      videoEl.play().catch((err) => {
        // console.error('视频播放失败:', err)
      })
    }
  }
}

function handleMouseLeave(video: SearchVideo) {
  hoveredVideoId.value = null

  if (isImagePost(video)) {
    // 图文作品：停止轮播和音乐
    stopImageCarousel(video)
    stopMusic(video)
  } else {
    // 视频作品：暂停并重置
    const videoEl = videoRefs.value.get(video.aweme_id)
    if (videoEl) {
      videoEl.pause()
      videoEl.currentTime = 0
    }
  }
}

// 图文轮播 - 改为3秒间隔
const carouselIntervals = ref<Map<string, number>>(new Map())

function startImageCarousel(video: SearchVideo) {
  if (!video.images || video.images.length <= 1) return

  // 初始化索引
  if (!carouselIndexes.value.has(video.aweme_id)) {
    carouselIndexes.value.set(video.aweme_id, 0)
  }

  // 清除已有的定时器
  const existingInterval = carouselIntervals.value.get(video.aweme_id)
  if (existingInterval) {
    clearInterval(existingInterval)
  }

  const interval = window.setInterval(() => {
    const currentIdx = carouselIndexes.value.get(video.aweme_id) || 0
    const nextIdx = (currentIdx + 1) % video.images!.length
    carouselIndexes.value.set(video.aweme_id, nextIdx)
  }, 2000)

  carouselIntervals.value.set(video.aweme_id, interval)
}

function stopImageCarousel(video: SearchVideo) {
  const interval = carouselIntervals.value.get(video.aweme_id)
  if (interval) {
    clearInterval(interval)
    carouselIntervals.value.delete(video.aweme_id)
  }
  // 重置索引
  carouselIndexes.value.delete(video.aweme_id)
}

// 手动切换图片
function prevImage(video: SearchVideo) {
  if (!video.images || video.images.length <= 1) return
  const currentIdx = carouselIndexes.value.get(video.aweme_id) || 0
  const prevIdx = (currentIdx - 1 + video.images.length) % video.images.length
  carouselIndexes.value.set(video.aweme_id, prevIdx)
}

function nextImage(video: SearchVideo) {
  if (!video.images || video.images.length <= 1) return
  const currentIdx = carouselIndexes.value.get(video.aweme_id) || 0
  const nextIdx = (currentIdx + 1) % video.images.length
  carouselIndexes.value.set(video.aweme_id, nextIdx)
}

// 音乐播放
function playMusic(video: SearchVideo) {
  if (!video.music_url) return
  const audioEl = audioRefs.value.get(video.aweme_id)
  if (audioEl) {
    audioEl.currentTime = 0
    audioEl.play().catch(() => {})
  }
}

function stopMusic(video: SearchVideo) {
  const audioEl = audioRefs.value.get(video.aweme_id)
  if (audioEl) {
    audioEl.pause()
    audioEl.currentTime = 0
  }
}

function setVideoRef(awemeId: string, el: any) {
  if (el) {
    videoRefs.value.set(awemeId, el)
  }
}

function setAudioRef(awemeId: string, el: any) {
  if (el) {
    audioRefs.value.set(awemeId, el)
  }
}

// 获取当前显示的图片URL
function getCurrentImageUrl(video: SearchVideo): string {
  if (!video.images || video.images.length === 0) {
    return video.cover_url
  }
  const idx = getCarouselIndex(video.aweme_id)
  return video.images[idx] || video.cover_url
}

// 视频预览
const previewVideo = ref<SearchVideo | null>(null)
const showPreview = ref(false)
const previewVideoRef = ref<HTMLVideoElement | null>(null)

function openVideoPreview(video: SearchVideo) {
  if (isSelectMode.value) {
    toggleVideoSelect(video, new Event('click'))
    return
  }
  
  // 停止所有悬停播放
  videoRefs.value.forEach(v => {
    v.pause()
    v.currentTime = 0
  })
  audioRefs.value.forEach(a => {
    a.pause()
    a.currentTime = 0
  })
  carouselIntervals.value.forEach(interval => clearInterval(interval))
  carouselIntervals.value.clear()
  hoveredVideoId.value = null

  previewVideo.value = video
  showPreview.value = true

  // 自动播放预览视频
  nextTick(() => {
    if (previewVideoRef.value && video.video_url) {
      previewVideoRef.value.play().catch(() => {})
    }
  })
}

function closePreview() {
  if (previewVideoRef.value) {
    previewVideoRef.value.pause()
  }
  showPreview.value = false
  previewVideo.value = null
}

// 切换静音状态
function toggleMute() {
  isMuted.value = !isMuted.value
  // 更新所有视频和音频的静音状态
  videoRefs.value.forEach(v => {
    v.muted = isMuted.value
  })
  audioRefs.value.forEach(a => {
    a.muted = isMuted.value
  })
}

async function handleSearch() {
  if (!keyword.value.trim()) {
    error('请输入搜索关键词')
    return
  }

  // 防止重复搜索
  if (loading.value) {
    return
  }

  searchStore.addHistory(keyword.value)
  loading.value = true

  try {
    if (activeType.value === 'general') {
      const res = await searchVideos({
        keyword: keyword.value,
        count: 50,
        sort_type: searchFilters.value.sortType,
        publish_time: searchFilters.value.publishTime,
        filter_duration: searchFilters.value.filterDuration,
        content_type: searchFilters.value.contentType
      })
      videoResults.value = res.data.data || []
    } else if (activeType.value === 'video') {
      const res = await searchVideoSearch({
        keyword: keyword.value,
        count: 50,
        sort_type: searchFilters.value.sortType,
        publish_time: searchFilters.value.publishTime,
        filter_duration: searchFilters.value.filterDuration
      })
      videoResults.value = res.data.data || []
    } else if (activeType.value === 'user') {
      const res = await searchUsers({ keyword: keyword.value, count: 30 })
      userResults.value = res.data.data || []
    } else if (activeType.value === 'live') {
      const res = await searchLive({ keyword: keyword.value, count: 20 })
      liveResults.value = res.data.data || []
    }
  } catch (err) {
    // console.error('搜索失败:', err)
  } finally {
    loading.value = false
  }
}

function handleHistoryClick(word: string) {
  keyword.value = word
  handleSearch()
}

function removeHistory(word: string) {
  searchStore.removeHistory(word)
}

// 清理
onUnmounted(() => {
  videoRefs.value.clear()
  audioRefs.value.clear()
  carouselIntervals.value.forEach(interval => clearInterval(interval))
})
</script>

<template>
  <div class="search-page">
    <div class="search-section" :class="{ 'has-results': keyword }">
      <!-- 搜索框 -->
      <div class="search-box">
        <div class="search-header">
          <div class="logo-icon">
            <el-icon><Search /></el-icon>
          </div>
          <h2 class="search-title">
            全能搜索
          </h2>
          <p class="search-subtitle">
            搜索抖音视频、用户、直播内容
          </p>
        </div>
        <div class="search-type-selector mb-4">
          <el-radio-group
            v-model="activeType"
            size="large"
          >
            <el-radio-button value="general">
              综合
            </el-radio-button>
            <el-radio-button value="video">
              视频
            </el-radio-button>
            <el-radio-button value="user">
              用户
            </el-radio-button>
            <el-radio-button value="live">
              直播
            </el-radio-button>
          </el-radio-group>
        </div>
        <div class="search-input-wrapper">
          <el-input
            v-model="keyword"
            placeholder="请输入搜索关键词"
            size="large"
            clearable
            @keyup.enter="handleSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            @click="handleSearch"
          >
            搜索
          </el-button>
        </div>

        <!-- 搜索条件筛选（综合和视频搜索时显示） -->
        <div v-if="activeType === 'general' || activeType === 'video'" class="search-filters">
          <div class="filter-item">
            <span class="filter-label">排序</span>
            <el-select v-model="searchFilters.sortType" placeholder="选择排序" size="default">
              <el-option
                v-for="item in sortOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </div>
          <div class="filter-item">
            <span class="filter-label">发布时间</span>
            <el-select v-model="searchFilters.publishTime" placeholder="选择时间" size="default">
              <el-option
                v-for="item in publishTimeOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </div>
          <div class="filter-item">
            <span class="filter-label">视频时长</span>
            <el-select v-model="searchFilters.filterDuration" placeholder="选择时长" size="default" clearable>
              <el-option
                v-for="item in durationOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </div>
          <div class="filter-item">
            <span class="filter-label">内容形式</span>
            <el-select v-model="searchFilters.contentType" placeholder="选择类型" size="default" clearable>
              <el-option
                v-for="item in contentTypeOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </div>
        </div>
      </div>

      <!-- 搜索历史 -->
      <div
        v-if="!keyword && searchStore.history.length > 0"
        class="mb-6"
      >
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-white font-medium">
          搜索历史
        </h3>
        <el-button
          text
          type="primary"
          size="small"
          @click="searchStore.clearHistory"
        >
          清空
        </el-button>
      </div>
      <div class="flex flex-wrap gap-2">
        <el-tag
          v-for="word in searchStore.history"
          :key="word"
          closable
          class="cursor-pointer"
          @click="handleHistoryClick(word)"
          @close="removeHistory(word)"
        >
          {{ word }}
        </el-tag>
      </div>
    </div>
    </div>

    <!-- 搜索结果 -->
    <template v-if="keyword">
      <!-- 视频结果（综合和视频共用） -->
      <div
        v-if="activeType === 'general' || activeType === 'video'"
        class="video-results"
      >
        <!-- 批量操作工具栏 -->
        <div v-if="videoResults.length > 0" class="flex items-center justify-between mb-4">
          <h3 class="text-white font-medium">
            搜索结果 ({{ videoResults.length }})
          </h3>
          <div class="flex items-center gap-3">
            <el-button
              :type="isSelectMode ? 'primary' : 'default'"
              size="small"
              @click="toggleSelectMode"
            >
              <el-icon class="mr-1">
                <Finished />
              </el-icon>
              {{ isSelectMode ? '取消选择' : '批量选择' }}
            </el-button>
            <el-button
              v-if="isSelectMode"
              size="small"
              @click="toggleSelectAll"
            >
              <el-icon class="mr-1">
                <Check />
              </el-icon>
              {{ isAllSelected ? '取消全选' : '全选' }}
            </el-button>
            <el-popover
              v-if="isSelectMode && selectedVideoIds.size > 0"
              :visible="showDownloadPopover"
              placement="bottom"
              :width="280"
              trigger="click"
            >
              <template #reference>
                <el-button
                  type="primary"
                  size="small"
                  @click="openDownloadPopover"
                >
                  <el-icon class="mr-1">
                    <Download />
                  </el-icon>
                  下载 ({{ selectedVideoIds.size }})
                </el-button>
              </template>
              
              <div class="py-2">
                <div class="text-sm text-gray-300 mb-3">
                  选择视频质量
                </div>
                <div class="flex flex-col gap-2">
                  <div
                    v-for="option in qualityOptions"
                    :key="option.value"
                    class="flex items-center gap-3 p-2 rounded-lg cursor-pointer transition-colors"
                    :class="selectedQuality === option.value ? 'bg-primary/20 text-primary' : 'hover:bg-gray-700'"
                    @click="selectedQuality = option.value"
                  >
                    <div
                      class="w-4 h-4 rounded-full border-2 flex items-center justify-center"
                      :class="selectedQuality === option.value ? 'border-primary' : 'border-gray-500'"
                    >
                      <div
                        v-if="selectedQuality === option.value"
                        class="w-2 h-2 rounded-full bg-primary"
                      />
                    </div>
                    <div class="flex-1">
                      <div class="text-sm font-medium text-white">
                        {{ option.label }}
                      </div>
                      <div class="text-xs text-gray-400">
                        {{ option.desc }}
                      </div>
                    </div>
                  </div>
                </div>
                
                <!-- 下载进度 -->
                <div
                  v-if="isDownloading"
                  class="mt-3"
                >
                  <el-progress 
                    :percentage="Math.round(downloadProgress.current / downloadProgress.total * 100)" 
                    :format="() => `${downloadProgress.current}/${downloadProgress.total}`"
                    :stroke-width="6"
                  />
                </div>
                
                <div class="flex gap-2 mt-3">
                  <el-button
                    size="small"
                    :disabled="isDownloading"
                    @click="showDownloadPopover = false"
                  >
                    取消
                  </el-button>
                  <el-button
                    type="primary"
                    size="small"
                    :loading="isDownloading"
                    class="flex-1"
                    @click="executeDownload"
                  >
                    开始下载
                  </el-button>
                </div>
              </div>
            </el-popover>
          </div>
        </div>
        
        <div
          v-if="videoResults.length > 0"
          class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4"
        >
          <div
            v-for="video in videoResults"
            :key="video.aweme_id"
            class="video-card group relative rounded-xl overflow-hidden bg-dark-card cursor-pointer hover:scale-[1.02] transition-all"
            :class="{ 'ring-2 ring-primary': selectedVideoIds.has(video.aweme_id) }"
            @click="openVideoPreview(video)"
            @mouseenter="handleMouseEnter(video)"
            @mouseleave="handleMouseLeave(video)"
          >
            <div class="aspect-[9/16] relative">
              <!-- 图文作品：显示当前轮播图片 -->
              <img
                v-if="isImagePost(video)"
                :src="getCurrentImageUrl(video)"
                :alt="video.desc || video.title"
                class="w-full h-full object-cover transition-opacity duration-300"
                loading="lazy"
              >
              <!-- 视频作品：封面图 -->
              <img
                v-else
                :src="video.cover_url"
                :alt="video.desc || video.title"
                class="w-full h-full object-cover"
                :class="{ 'opacity-0': hoveredVideoId === video.aweme_id && video.video_url }"
                loading="lazy"
              >
              <!-- 视频预览（悬停时播放） -->
              <video
                v-if="video.video_url && !isImagePost(video) && !isSelectMode"
                :ref="(el) => setVideoRef(video.aweme_id, el)"
                :src="getProxyVideoUrl(video.video_url)"
                :poster="video.cover_url"
                class="absolute inset-0 w-full h-full object-cover"
                :class="{ 'opacity-100': hoveredVideoId === video.aweme_id, 'opacity-0': hoveredVideoId !== video.aweme_id }"
                :muted="isMuted"
                loop
                playsinline
                preload="metadata"
              />
              <!-- 图文作品音乐 -->
              <audio
                v-if="video.music_url && isImagePost(video)"
                :ref="(el) => setAudioRef(video.aweme_id, el)"
                :src="video.music_url"
                loop
                preload="none"
              />
              <!-- 作品类型标识 -->
              <div class="absolute top-2 left-2">
                <el-tag
                  size="small"
                  :type="isImagePost(video) ? 'info' : 'danger'"
                  effect="dark"
                >
                  {{ isImagePost(video) ? '图文' : '视频' }}
                </el-tag>
              </div>
              <!-- 选中状态遮罩 -->
              <div 
                v-if="isSelectMode"
                class="absolute inset-0 bg-black/30 transition-opacity"
                :class="{ 'opacity-0 hover:opacity-100': !selectedVideoIds.has(video.aweme_id), 'opacity-100': selectedVideoIds.has(video.aweme_id) }"
              />
              <!-- 选择框 -->
              <div 
                v-if="isSelectMode"
                class="absolute top-2 right-2 w-6 h-6 rounded border-2 flex items-center justify-center transition-all z-10"
                :class="selectedVideoIds.has(video.aweme_id) ? 'bg-primary border-primary' : 'border-white/50 bg-black/30'"
                @click.stop="toggleVideoSelect(video, $event)"
              >
                <el-icon
                  v-if="selectedVideoIds.has(video.aweme_id)"
                  class="text-white text-sm"
                >
                  <Check />
                </el-icon>
              </div>
              <!-- 悬停播放提示 -->
              <div
                v-if="!isSelectMode && hoveredVideoId !== video.aweme_id"
                class="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity bg-black/30"
              >
                <el-icon class="text-white text-4xl">
                  <VideoPlay v-if="video.video_url" />
                  <Picture v-else-if="isImagePost(video)" />
                </el-icon>
              </div>
              <!-- 图文轮播左右箭头（鼠标悬浮时显示） -->
              <template v-if="isImagePost(video) && video.images && video.images.length > 1 && hoveredVideoId === video.aweme_id && !isSelectMode">
                <button
                  class="absolute left-2 top-1/2 -translate-y-1/2 z-10 w-8 h-8 flex items-center justify-center rounded-full bg-black/50 text-white hover:bg-black/70 transition-colors"
                  @click.stop="prevImage(video)"
                >
                  <el-icon><ArrowLeft /></el-icon>
                </button>
                <button
                  class="absolute right-2 top-1/2 -translate-y-1/2 z-10 w-8 h-8 flex items-center justify-center rounded-full bg-black/50 text-white hover:bg-black/70 transition-colors"
                  @click.stop="nextImage(video)"
                >
                  <el-icon><ArrowRight /></el-icon>
                </button>
              </template>
              <!-- 图文轮播指示器 -->
              <div
                v-if="isImagePost(video) && video.images && video.images.length > 1"
                class="absolute bottom-10 left-0 right-0 flex justify-center gap-1"
              >
                <span
                  v-for="(_, idx) in video.images"
                  :key="idx"
                  class="w-1.5 h-1.5 rounded-full transition-all"
                  :class="getCarouselIndex(video.aweme_id) === idx ? 'bg-white' : 'bg-white/40'"
                />
              </div>
              <!-- 统计信息 -->
              <div class="absolute bottom-2 left-2 right-2 flex items-center justify-between text-white text-xs">
                <span class="flex items-center gap-1">
                  <el-icon><Star /></el-icon>
                  {{ formatNumber(video.digg_count) }}
                </span>
                <span class="flex items-center gap-1">
                  <el-icon><ChatDotRound /></el-icon>
                  {{ formatNumber(video.comment_count) }}
                </span>
              </div>
              <!-- 声音开关按钮 -->
              <button
                class="absolute bottom-14 right-2 z-10 w-8 h-8 flex items-center justify-center rounded-full bg-black/50 text-white hover:bg-black/70 transition-colors"
                @click.stop="toggleMute"
                :title="isMuted ? '开启声音' : '关闭声音'"
              >
                <!-- 扬声器图标 - 有声音 -->
                <svg v-if="!isMuted" viewBox="0 0 24 24" fill="currentColor" class="w-5 h-5">
                  <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/>
                </svg>
                <!-- 静音图标 -->
                <svg v-else viewBox="0 0 24 24" fill="currentColor" class="w-5 h-5">
                  <path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z"/>
                </svg>
              </button>
            </div>
            <div class="p-3">
              <p class="text-white text-sm line-clamp-2 mb-2">
                <template v-for="(part, idx) in parseHashtags(video.desc || video.title)" :key="idx">
                  <span
                    v-if="part.isHashtag"
                    class="cursor-pointer hover:text-primary hover:underline transition-colors"
                    @click="searchByHashtag(part.text, $event)"
                  >{{ part.text }}</span>
                  <span v-else>{{ part.text }}</span>
                </template>
              </p>
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                  <span 
                    class="text-gray-400 text-xs cursor-pointer hover:text-primary transition-colors"
                    @click="goToUserProfile(video.author_sec_uid, $event)"
                  >
                    @{{ video.author_nickname }}
                  </span>
                  <span v-if="video.create_time" class="text-gray-500 text-xs">
                    · {{ formatCreateTime(video.create_time) }}
                  </span>
                </div>
                <span v-if="video.duration && video.duration > 0" class="text-gray-500 text-xs">
                  {{ Math.floor(video.duration / 1000) }}s
                </span>
              </div>
            </div>
          </div>
        </div>
        <EmptyState
          v-else-if="!loading"
          text="未找到相关视频"
        />
      </div>

      <!-- 用户结果 -->
      <div
        v-if="activeType === 'user'"
        class="user-results"
      >
        <div
          v-if="userResults.length > 0"
          class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
        >
          <div
            v-for="user in userResults"
            :key="user.uid"
            class="user-card flex items-center gap-4 p-4 rounded-xl bg-dark-card cursor-pointer hover:bg-dark-lighter transition-colors"
            @click="goToUserProfile(user.sec_uid, $event)"
          >
            <img
              v-if="user.avatar"
              :src="user.avatar"
              class="w-14 h-14 rounded-full object-cover"
            >
            <div class="flex-1 min-w-0">
              <div class="text-white font-medium">
                {{ user.nickname }}
              </div>
              <p
                v-if="user.signature"
                class="text-gray-400 text-xs mt-1 truncate"
              >
                {{ user.signature }}
              </p>
              <div class="text-gray-400 text-xs mt-2">
                {{ formatNumber(user.follower_count) }} 粉丝
              </div>
            </div>
          </div>
        </div>
        <EmptyState
          v-else-if="!loading"
          text="未找到相关用户"
        />
      </div>

      <!-- 直播结果 -->
      <div
        v-if="activeType === 'live'"
        class="live-results"
      >
        <div
          v-if="liveResults.length > 0"
          class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
        >
          <div
            v-for="live in liveResults"
            :key="live.room_id"
            class="live-card rounded-xl overflow-hidden bg-dark-card cursor-pointer hover:ring-2 hover:ring-blue-500 transition-all"
            @click="goToLive(live)"
          >
            <div class="aspect-video relative">
              <img
                :src="live.cover"
                :alt="live.title"
                class="w-full h-full object-cover"
              >
              <div class="absolute top-2 left-2 px-2 py-1 rounded bg-red-500 text-white text-xs">
                直播中
              </div>
              <div class="absolute bottom-2 left-2 text-white text-xs">
                {{ live.user_count }} 观看
              </div>
            </div>
            <div class="p-3">
              <p class="text-white text-sm font-medium mb-1 truncate">
                {{ live.title }}
              </p>
              <span 
                class="text-gray-400 text-xs cursor-pointer hover:text-blue-400 transition-colors"
                @click.stop="goToLiveUserProfile(live.author_sec_uid, $event)"
              >
                {{ live.author_nickname }}
              </span>
            </div>
          </div>
        </div>
        <EmptyState
          v-else-if="!loading"
          text="未找到相关直播"
        />
      </div>

      <LoadingSpinner
        v-if="loading"
        size="small"
      />
    </template>

    <!-- 视频预览对话框 -->
    <el-dialog
      v-model="showPreview"
      :title="previewVideo?.title || '视频预览'"
      width="80%"
      top="5vh"
      @close="closePreview"
    >
      <div v-if="previewVideo" class="video-preview">
        <!-- 图文作品 -->
        <div v-if="previewVideo.images && previewVideo.images.length > 0" class="images-container mb-4">
          <el-carousel
            :interval="4000"
            type="card"
            height="400px"
            indicator-position="outside"
          >
            <el-carousel-item
              v-for="(img, index) in previewVideo.images"
              :key="index"
            >
              <img
                :src="img"
                class="w-full h-full object-contain"
                loading="lazy"
              >
            </el-carousel-item>
          </el-carousel>
          <div class="text-center text-gray-400 text-sm mt-2">
            共 {{ previewVideo.images.length }} 张图片
          </div>
        </div>
        <!-- 视频播放器 -->
        <div v-else-if="previewVideo.video_url" class="video-container mb-4">
          <video
            ref="previewVideoRef"
            :src="getProxyVideoUrl(previewVideo.video_url)"
            :poster="previewVideo.cover_url"
            controls
            autoplay
            class="w-full max-h-[60vh] mx-auto"
            style="max-width: 400px;"
          />
        </div>
        <div v-else class="text-center text-gray-400 py-8">
          暂无视频链接
        </div>

        <!-- 视频信息 -->
        <div class="video-info">
          <p class="text-white mb-4">{{ previewVideo.desc }}</p>

          <!-- 统计信息 -->
          <div class="flex items-center gap-6 text-gray-400 text-sm mb-4">
            <span class="flex items-center gap-1">
              <el-icon><Star /></el-icon>
              {{ formatNumber(previewVideo.digg_count) }} 点赞
            </span>
            <span class="flex items-center gap-1">
              <el-icon><ChatDotRound /></el-icon>
              {{ formatNumber(previewVideo.comment_count) }} 评论
            </span>
            <span class="flex items-center gap-1">
              <el-icon><Share /></el-icon>
              {{ formatNumber(previewVideo.share_count) }} 分享
            </span>
            <span class="flex items-center gap-1">
              <el-icon><Collection /></el-icon>
              {{ formatNumber(previewVideo.collect_count) }} 收藏
            </span>
            <span class="flex items-center gap-1">
              <el-icon><View /></el-icon>
              {{ formatNumber(previewVideo.play_count) }} 播放
            </span>
          </div>

          <!-- 作者信息 -->
          <div class="flex items-center gap-3">
            <img
              :src="previewVideo.author_avatar"
              class="w-10 h-10 rounded-full"
            >
            <div>
              <div class="text-white font-medium">{{ previewVideo.author_nickname }}</div>
              <a
                :href="previewVideo.work_url"
                target="_blank"
                class="text-primary text-xs hover:underline"
              >
                在抖音查看
              </a>
            </div>
          </div>

          <!-- 视频质量选择 -->
          <div v-if="previewVideo.video_qualities" class="mt-4">
            <span class="text-gray-400 text-sm mr-2">视频质量:</span>
            <el-tag
              v-for="(quality, name) in previewVideo.video_qualities"
              :key="name"
              class="mr-2 cursor-pointer"
              @click="previewVideo.video_url = quality.url"
            >
              {{ name }} ({{ quality.width }}x{{ quality.height }})
            </el-tag>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.search-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-height: 100%;
}

.search-section {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding-top: 12vh;
}

.search-section.has-results {
  padding-top: 0;
}

.search-box {
  position: relative;
  z-index: 1;
  text-align: center;
  padding: 44px 44px 32px;
  background: linear-gradient(180deg, rgba(var(--app-surface-rgb) / 0.96), rgba(var(--app-surface-alt-rgb) / 0.92));
  backdrop-filter: blur(18px);
  border-radius: 28px;
  border: 1px solid rgba(var(--app-border-rgb) / 0.78);
  box-shadow: 0 24px 60px rgba(var(--app-shadow-rgb) / 0.12);
  max-width: 680px;
  width: min(100%, 680px);
  margin: 0 auto;
}

.search-header {
  margin-bottom: 34px;
}

.logo-icon {
  width: 88px;
  height: 88px;
  margin: 0 auto 22px;
  background: linear-gradient(135deg, rgb(var(--primary-color-rgb)), rgb(var(--app-accent-soft-rgb)));
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 42px;
  color: rgb(var(--utility-white-rgb));
  box-shadow: 0 18px 34px rgba(var(--primary-color-rgb) / 0.28);
}

.search-title {
  font-size: 36px;
  font-weight: 700;
  color: rgb(var(--app-text-strong-rgb));
  line-height: 1.1;
  letter-spacing: -0.03em;
  margin: 0 0 12px;
}

.search-subtitle {
  font-size: 15px;
  color: rgb(var(--app-text-muted-rgb));
  line-height: 1.7;
  max-width: 420px;
  margin: 0 auto;
}

.search-type-selector {
  display: flex;
  justify-content: center;
}

.search-input-wrapper {
  display: flex;
  gap: 12px;
}

.search-input-wrapper .el-input {
  flex: 1;
}

.search-filters {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid rgba(var(--app-border-rgb) / 0.35);
}

.filter-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.filter-label {
  font-size: 12px;
  font-weight: 500;
  color: rgb(var(--app-text-subtle-rgb));
  text-align: left;
}

@media (max-width: 768px) {
  .search-filters {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
