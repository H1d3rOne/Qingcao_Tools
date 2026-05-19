<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { User, DocumentCopy, Grid, Download, Star, VideoPlay, Close, Check, Finished, ArrowLeft } from '@element-plus/icons-vue'
import { getUserInfo, getUserWorks, downloadUserWork, getUserInfoBySecUid, getUserVideos } from '@/api'
import type { UserInfo, UserWork } from '@/api/modules/user'
import { useNotification } from '@/composables'
import { extractUrl } from '@/utils'
import JSZip from 'jszip'
import { saveAs } from 'file-saver'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import EmptyState from '@/components/common/EmptyState.vue'

const route = useRoute()
const router = useRouter()
const { error, success } = useNotification()

const inputUrl = ref('')
const loading = ref(false)
const userInfo = ref<UserInfo | null>(null)
const userWorks = ref<UserWork[]>([])
const worksLoading = ref(false)
const hoveredWorkId = ref<string | null>(null)

// 弹窗播放器状态
const showPlayer = ref(false)
const currentPlayWork = ref<UserWork | null>(null)

// 选中状态
const selectedWorkIds = ref<Set<string>>(new Set())
const isSelectMode = ref(false)

// 下载相关状态
const showDownloadPopover = ref(false)
const downloadingWorks = ref<UserWork[]>([])
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

// 清晰度降级优先级（高到低）
const qualityPriority = ['hd2k', 'super', 'high', 'standard']

// 选中的视频作品（图文除外）
const selectedVideoWorks = computed(() => {
  return downloadingWorks.value.filter(w => w.is_video)
})

// 检查某清晰度是否在选中视频中至少有一个支持
function isQualityAvailable(quality: string): boolean {
  if (selectedVideoWorks.value.length === 0) return true
  return selectedVideoWorks.value.some(w => w.video_qualities?.[quality])
}

// 为单个作品按优先级降级解析清晰度
function resolveQualityForWork(work: UserWork, preferred: string): string {
  if (!work.video_qualities || Object.keys(work.video_qualities).length === 0) {
    return preferred
  }
  const startIdx = qualityPriority.indexOf(preferred)
  if (startIdx === -1) return preferred
  // 优先尝试目标清晰度，然后向下降级
  for (let i = startIdx; i < qualityPriority.length; i++) {
    if (work.video_qualities[qualityPriority[i]]) return qualityPriority[i]
  }
  // 都没有时，向上找一个存在的（极少见，仅作为兜底）
  for (let i = startIdx - 1; i >= 0; i--) {
    if (work.video_qualities[qualityPriority[i]]) return qualityPriority[i]
  }
  return preferred
}

// 计算属性
const selectedWorks = computed(() => {
  return userWorks.value.filter(w => selectedWorkIds.value.has(w.aweme_id))
})

const isAllSelected = computed(() => {
  return userWorks.value.length > 0 && selectedWorkIds.value.size === userWorks.value.length
})

const isIndeterminate = computed(() => {
  const size = selectedWorkIds.value.size
  return size > 0 && size < userWorks.value.length
})

// 切换选择模式
function toggleSelectMode() {
  isSelectMode.value = !isSelectMode.value
  if (!isSelectMode.value) {
    selectedWorkIds.value.clear()
  }
}

// 全选/取消全选
function toggleSelectAll() {
  if (isAllSelected.value) {
    selectedWorkIds.value.clear()
  } else {
    userWorks.value.forEach(w => selectedWorkIds.value.add(w.aweme_id))
  }
}

// 切换单个选中
function toggleWorkSelect(work: UserWork, event: Event) {
  event.stopPropagation()
  if (selectedWorkIds.value.has(work.aweme_id)) {
    selectedWorkIds.value.delete(work.aweme_id)
  } else {
    selectedWorkIds.value.add(work.aweme_id)
  }
}

// 打开下载弹窗
function openDownloadPopover() {
  if (selectedWorkIds.value.size === 0) {
    error('请先选择要下载的作品')
    return
  }
  downloadingWorks.value = selectedWorks.value
  // 如果当前选中的清晰度在选中视频中都不支持，自动切到最高可用清晰度
  if (!isQualityAvailable(selectedQuality.value)) {
    const fallback = qualityPriority.find(q => isQualityAvailable(q))
    if (fallback) selectedQuality.value = fallback
  }
  showDownloadPopover.value = true
}

// 执行下载
async function executeDownload() {
  isDownloading.value = true
  downloadProgress.value = { current: 0, total: downloadingWorks.value.length }
  
  const failedWorks: string[] = []
  
  for (let i = 0; i < downloadingWorks.value.length; i++) {
    const work = downloadingWorks.value[i]
    downloadProgress.value.current = i + 1
    
    try {
      if (!work.is_video) {
        // 图文：先取作品列表里的 images，没有再调接口兜底
        let imgs = work.images || []
        if (imgs.length === 0) {
          const res = await downloadUserWork({
            aweme_id: work.aweme_id,
            save_type: 'image'
          })
          imgs = res.data?.images || []
          if (imgs.length === 0) {
            throw new Error('未获取到图片链接')
          }
        }
        const baseName = (work.desc || work.aweme_id).slice(0, 50)
        if (imgs.length === 1) {
          // 单图：直接下载
          await triggerDownload(imgs[0], baseName, 'auto')
        } else {
          // 多图：打包成 zip 下载
          await downloadImagesAsZip(imgs, baseName)
        }
      } else {
        // 视频：按降级后的清晰度请求下载链接
        const workQuality = resolveQualityForWork(work, selectedQuality.value)
        const res = await downloadUserWork({
          aweme_id: work.aweme_id,
          quality: workQuality,
          save_type: 'video'
        })
        if (res.data?.video_url) {
          await triggerDownload(res.data.video_url, work.desc || work.aweme_id, 'mp4')
        } else {
          throw new Error('未获取到视频链接')
        }
      }
    } catch (err) {
      console.error(`下载失败: ${work.aweme_id}`, err)
      failedWorks.push(work.desc || work.aweme_id)
    }
    
    // 添加延迟避免请求过快
    await new Promise(resolve => setTimeout(resolve, 500))
  }
  
  isDownloading.value = false
  
  if (failedWorks.length === 0) {
    success(`成功下载 ${downloadingWorks.value.length} 个作品`)
  } else {
    error(`部分下载失败: ${failedWorks.join(', ')}`)
  }
  
  showDownloadPopover.value = false
  selectedWorkIds.value.clear()
}

// 多图打包成 zip 下载
async function downloadImagesAsZip(urls: string[], baseName: string) {
  const zip = new JSZip()
  const safeName = baseName.replace(/[\\/:*?"<>|]/g, '_')

  // 并发拉取所有图片
  const fetches = urls.map(async (url, i) => {
    const proxyUrl = `/api/v1/douyin/work/proxy?url=${encodeURIComponent(url)}`
    const response = await fetch(proxyUrl)
    if (!response.ok) throw new Error(`图片 ${i + 1} 下载失败`)
    const blob = await response.blob()
    // 按 MIME 推断扩展名
    const mime = blob.type || ''
    let ext = 'jpg'
    if (mime.includes('png')) ext = 'png'
    else if (mime.includes('webp')) ext = 'webp'
    else if (mime.includes('gif')) ext = 'gif'
    const idx = String(i + 1).padStart(2, '0')
    zip.file(`${safeName}_${idx}.${ext}`, blob)
  })

  await Promise.all(fetches)
  const zipBlob = await zip.generateAsync({ type: 'blob' })
  saveAs(zipBlob, `${safeName}.zip`)
}

// 触发下载
async function triggerDownload(url: string, filename: string, ext: string = 'mp4') {
  try {
    // 使用代理URL
    const proxyUrl = `/api/v1/douyin/work/proxy?url=${encodeURIComponent(url)}`
    const response = await fetch(proxyUrl)
    const blob = await response.blob()
    const downloadUrl = URL.createObjectURL(blob)

    // 从 blob 的 MIME 类型推断扩展名（图片场景）
    let finalExt = ext
    if (ext === 'auto') {
      const mime = blob.type || ''
      if (mime.includes('jpeg') || mime.includes('jpg')) finalExt = 'jpg'
      else if (mime.includes('png')) finalExt = 'png'
      else if (mime.includes('webp')) finalExt = 'webp'
      else if (mime.includes('gif')) finalExt = 'gif'
      else finalExt = 'jpg'
    }

    const a = document.createElement('a')
    a.href = downloadUrl
    a.download = `${filename.replace(/[\\/:*?"<>|]/g, '_')}.${finalExt}`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(downloadUrl)
  } catch (err) {
    console.error('下载失败:', err)
    throw err
  }
}

async function handleSearch() {
  if (!inputUrl.value.trim()) {
    error('请输入用户主页链接')
    return
  }

  inputUrl.value = extractUrl(inputUrl.value)

  loading.value = true
  userInfo.value = null
  userWorks.value = []

  try {
    const res = await getUserInfo(inputUrl.value.trim())
    userInfo.value = res.data
    success('查询成功')
    
    // 自动加载作品
    loadWorks()
  } catch (err) {
    // console.error('查询失败:', err)
  } finally {
    loading.value = false
  }
}

async function loadWorks() {
  if (!inputUrl.value.trim()) return
  
  worksLoading.value = true
  try {
    const res = await getUserWorks(inputUrl.value.trim(), 30)
    userWorks.value = res.data || []
  } catch (err) {
    console.error('获取作品失败:', err)
  } finally {
    worksLoading.value = false
  }
}

// 通过 sec_uid 加载用户信息和作品
async function loadUserBySecUid(secUid: string) {
  loading.value = true
  userInfo.value = null
  userWorks.value = []
  inputUrl.value = '' // 清空输入框
  
  try {
    const res = await getUserInfoBySecUid(secUid)
    userInfo.value = res.data
    success('查询成功')
    
    // 自动加载作品
    loadWorksBySecUid(secUid)
  } catch (err) {
    // console.error('查询失败:', err)
    error('获取用户信息失败')
  } finally {
    loading.value = false
  }
}

// 通过 sec_uid 加载作品
async function loadWorksBySecUid(secUid: string) {
  worksLoading.value = true
  try {
    const res = await getUserVideos({ sec_uid: secUid, count: 30 })
    // 后端返回的是 ApiResponse<List[WorkResponse]>，所以 res.data 直接是作品数组
    userWorks.value = res.data || []
  } catch (err) {
    // console.error('获取作品失败:', err)
  } finally {
    worksLoading.value = false
  }
}

// 监听路由查询参数 sec_uid
watch(() => route.query.sec_uid, (secUid) => {
  if (secUid && typeof secUid === 'string') {
    loadUserBySecUid(secUid)
  }
}, { immediate: true })

// 是否从其他页面跳转过来
const isFromOtherPage = computed(() => route.query.from === 'search')

// 返回上一页
function goBack() {
  router.push('/douyin/search')
}

function handlePaste() {
  navigator.clipboard.readText().then(text => {
    inputUrl.value = extractUrl(text)
  })
}

function handleWorkClick(work: UserWork) {
  // 打开弹窗播放器
  currentPlayWork.value = work
  showPlayer.value = true
}

function closePlayer() {
  showPlayer.value = false
  currentPlayWork.value = null
}

function handleMouseEnter(work: UserWork) {
  hoveredWorkId.value = work.aweme_id
}

function handleMouseLeave() {
  hoveredWorkId.value = null
}

function handleVideoLoaded(event: Event) {
  const video = event.target as HTMLVideoElement
  video.play().catch(() => {
    // 自动播放可能被浏览器阻止，忽略错误
  })
}

function getProxyVideoUrl(url: string | undefined): string {
  if (!url) return ''
  // 使用后端代理来访问视频，绕过防盗链
  return `/api/v1/douyin/work/proxy?url=${encodeURIComponent(url)}`
}

// 格式化数字
function formatNumber(num: number | undefined): string {
  if (!num) return '0'
  if (num >= 10000) {
    return (num / 10000).toFixed(1) + 'w'
  }
  return num.toString()
}
</script>

<template>
  <div class="user-page">
    <el-button
      v-if="isFromOtherPage"
      text
      @click="goBack"
      class="back-btn"
    >
      <el-icon class="mr-1"><ArrowLeft /></el-icon>
      返回
    </el-button>
    <div class="search-section" :class="{ 'has-results': userInfo }">
      <!-- 搜索框 -->
      <div class="search-box">
        <div class="search-header">
          <div class="logo-icon">
            <el-icon><User /></el-icon>
          </div>
          <h2 class="search-title">
            用户查询
          </h2>
          <p class="search-subtitle">
            输入抖音用户主页链接，获取用户详细信息和作品列表
          </p>
        </div>
        <div class="search-input-group">
          <el-input
            v-model="inputUrl"
            placeholder="请输入用户主页链接"
            size="large"
            clearable
            @keyup.enter="handleSearch"
          >
            <template #prefix>
              <el-icon><User /></el-icon>
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
      </div>
    </div>

    <!-- 查询结果 -->
    <template v-if="userInfo">
      <!-- 用户信息卡片 -->
      <div class="user-card">
        <div class="user-card-content">
          <img
            v-if="userInfo.avatar"
            :src="userInfo.avatar"
            class="user-avatar"
          >
          <div class="user-details">
            <!-- 昵称 + 认证标签 -->
            <div class="user-header">
              <span class="user-nickname">{{ userInfo.nickname }}</span>
              <el-tag
                v-if="userInfo.is_verify"
                type="success"
                size="small"
              >
                已认证
              </el-tag>
            </div>

            <!-- 抖音号 + ID -->
            <div class="user-ids">
              <span
                v-if="userInfo.unique_id"
                class="id-item"
              >抖音号：{{ userInfo.unique_id }}</span>
            </div>

            <!-- 额外信息：性别、年龄、IP位置、国家 -->
            <div
              v-if="userInfo.gender || userInfo.user_age || userInfo.ip_location || userInfo.country"
              class="extra-info"
            >
              <el-tag
                v-if="userInfo.gender"
                :type="userInfo.gender === 1 ? 'success' : 'danger'"
                size="small"
              >
                {{ userInfo.gender === 1 ? '男' : '女' }}
              </el-tag>
              <span
                v-if="userInfo.user_age"
                class="info-text"
              >{{ userInfo.user_age }}岁</span>
              <span
                v-if="userInfo.ip_location"
                class="info-text"
              >{{ userInfo.ip_location }}</span>
              <span
                v-if="userInfo.country"
                class="info-text"
              >{{ userInfo.country }}</span>
            </div>

            <!-- 粉丝、关注、作品、获赞 -->
            <div class="stats-row">
              <div class="stat-item">
                <span class="stat-value">{{ userInfo.follower_count }}</span>
                <span class="stat-label">粉丝</span>
              </div>
              <div class="stat-divider" />
              <div class="stat-item">
                <span class="stat-value">{{ userInfo.following_count }}</span>
                <span class="stat-label">关注</span>
              </div>
              <div class="stat-divider" />
              <div class="stat-item">
                <span class="stat-value">{{ userInfo.aweme_count }}</span>
                <span class="stat-label">作品</span>
              </div>
              <div class="stat-divider" />
              <div class="stat-item">
                <span class="stat-value">{{ userInfo.favoriting_count }}</span>
                <span class="stat-label">获赞</span>
              </div>
            </div>

            <!-- 签名 -->
            <p
              v-if="userInfo.signature"
              class="signature-text"
            >
              {{ userInfo.signature }}
            </p>
          </div>
        </div>
      </div>

      <!-- 作品列表 -->
      <div class="works-section">
        <div class="works-header">
          <h3 class="works-title">
            作品列表 ({{ userWorks.length }})
          </h3>
        <div class="works-actions">
          <el-button
            v-if="userWorks.length > 0"
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
            v-if="isSelectMode && userWorks.length > 0"
            size="small"
            @click="toggleSelectAll"
          >
            <el-icon class="mr-1">
              <Check />
            </el-icon>
            {{ isAllSelected ? '取消全选' : '全选' }}
          </el-button>
          <el-popover
            v-if="isSelectMode && selectedWorkIds.size > 0"
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
                下载 ({{ selectedWorkIds.size }})
              </el-button>
            </template>

            <div class="download-popover">
              <div class="download-popover-title">
                选择视频质量
              </div>
              <div class="quality-list">
                <div
                  v-for="option in qualityOptions"
                  :key="option.value"
                  class="quality-option"
                  :class="{
                    active: selectedQuality === option.value,
                    disabled: !isQualityAvailable(option.value)
                  }"
                  @click="isQualityAvailable(option.value) && (selectedQuality = option.value)"
                >
                  <div
                    class="quality-radio"
                    :class="{ checked: selectedQuality === option.value }"
                  >
                    <div
                      v-if="selectedQuality === option.value"
                      class="quality-radio-dot"
                    />
                  </div>
                  <div class="quality-info">
                    <div class="quality-label">
                      {{ option.label }}
                      <span v-if="!isQualityAvailable(option.value)" class="quality-unavailable">（不可用）</span>
                    </div>
                    <div class="quality-desc">
                      {{ option.desc }}
                    </div>
                  </div>
                </div>
              </div>

              <!-- 下载进度 -->
              <div
                v-if="isDownloading"
                class="download-progress"
              >
                <el-progress
                  :percentage="Math.round(downloadProgress.current / downloadProgress.total * 100)"
                  :format="() => `${downloadProgress.current}/${downloadProgress.total}`"
                  :stroke-width="6"
                />
              </div>

              <div class="download-actions">
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
        v-if="userWorks.length > 0"
        class="video-grid"
      >
        <div
          v-for="work in userWorks"
          :key="work.aweme_id"
          class="video-card"
          :class="{ selected: selectedWorkIds.has(work.aweme_id) }"
          @click="isSelectMode ? toggleWorkSelect(work, $event) : handleWorkClick(work)"
          @mouseenter="handleMouseEnter(work)"
          @mouseleave="handleMouseLeave"
        >
          <div class="video-card-cover">
            <!-- 封面图 -->
            <img
              v-if="work.cover_url && hoveredWorkId !== work.aweme_id"
              :src="work.cover_url"
              :alt="work.desc"
              class="cover-img"
              loading="lazy"
            >
            <!-- 视频预览 -->
            <video
              v-if="work.video_url && hoveredWorkId === work.aweme_id && !isSelectMode"
              :src="getProxyVideoUrl(work.video_url)"
              class="cover-img"
              muted
              loop
              playsinline
              @loadeddata="handleVideoLoaded"
            />
            <!-- 无封面时显示占位 -->
            <div
              v-if="!work.cover_url && hoveredWorkId !== work.aweme_id"
              class="cover-placeholder"
            >
              <el-icon class="placeholder-icon">
                <Grid />
              </el-icon>
            </div>
            <!-- 选中状态遮罩 -->
            <div
              v-if="isSelectMode"
              class="select-overlay"
              :class="{ 'selected-overlay': selectedWorkIds.has(work.aweme_id) }"
            />
            <!-- 选择框 -->
            <div
              v-if="isSelectMode"
              class="select-checkbox"
              :class="{ checked: selectedWorkIds.has(work.aweme_id) }"
            >
              <el-icon
                v-if="selectedWorkIds.has(work.aweme_id)"
                class="check-icon"
              >
                <Check />
              </el-icon>
            </div>
            <!-- 播放按钮遮罩 -->
            <div
              v-if="!isSelectMode && (!work.video_url || hoveredWorkId !== work.aweme_id)"
              class="play-overlay"
            >
              <el-icon class="play-icon">
                <VideoPlay />
              </el-icon>
            </div>
            <!-- 统计信息 -->
            <div class="video-stats">
              <span class="stat-badge">
                <el-icon><Star /></el-icon>
                {{ work.digg_count }}
              </span>
            </div>
            <!-- 类型标识 -->
            <div class="work-type-badge" :class="work.is_video ? 'badge-video' : 'badge-image'">
              <el-icon v-if="work.is_video"><VideoPlay /></el-icon>
              <el-icon v-else><Grid /></el-icon>
              <span>{{ work.is_video ? '视频' : '图文' }}</span>
            </div>
          </div>
          <div class="video-card-info">
            <p class="video-card-desc">
              {{ work.desc }}
            </p>
          </div>
        </div>
      </div>
      <EmptyState
        v-else-if="!worksLoading"
        text="暂无作品"
      />
      <LoadingSpinner
        v-if="worksLoading"
        size="small"
      />
      </div>
    </template>

    <!-- 视频播放弹窗 -->
    <Teleport to="body">
      <Transition name="fade">
        <div
          v-if="showPlayer"
          class="player-overlay"
          @click.self="closePlayer"
        >
          <div class="player-modal">
            <!-- 关闭按钮 -->
            <button
              class="player-close"
              @click="closePlayer"
            >
              <el-icon class="close-icon">
                <Close />
              </el-icon>
            </button>

            <!-- 视频容器 -->
            <div
              v-if="currentPlayWork"
              class="player-content"
            >
              <!-- 视频播放器 -->
              <div class="player-video">
                <video
                  v-if="currentPlayWork.video_url"
                  :src="getProxyVideoUrl(currentPlayWork.video_url)"
                  :poster="currentPlayWork.cover_url"
                  controls
                  autoplay
                  class="video-element"
                />
                <img
                  v-else-if="currentPlayWork.cover_url"
                  :src="currentPlayWork.cover_url"
                  class="video-element"
                >
                <!-- 图集 -->
                <div
                  v-else-if="currentPlayWork.images && currentPlayWork.images.length > 0"
                  class="image-gallery"
                >
                  <img
                    :src="currentPlayWork.images[0]"
                    class="gallery-img"
                  >
                </div>
              </div>

              <!-- 视频信息 -->
              <div class="player-info">
                <!-- 作者信息 -->
                <div class="player-author">
                  <img
                    v-if="userInfo?.avatar"
                    :src="userInfo.avatar"
                    class="player-avatar"
                  >
                  <div>
                    <div class="player-nickname">
                      {{ userInfo?.nickname }}
                    </div>
                    <div class="player-uid">
                      @{{ userInfo?.unique_id }}
                    </div>
                  </div>
                </div>

                <!-- 描述 -->
                <p class="player-desc">
                  {{ currentPlayWork.desc }}
                </p>

                <!-- 统计数据 -->
                <div class="player-stats">
                  <div class="player-stat-item">
                    <el-icon><Star /></el-icon>
                    <span>{{ formatNumber(currentPlayWork.digg_count) }} 点赞</span>
                  </div>
                  <div class="player-stat-item">
                    <el-icon><VideoPlay /></el-icon>
                    <span>{{ formatNumber(currentPlayWork.play_count) }} 播放</span>
                  </div>
                  <div class="player-stat-item">
                    <el-icon><Grid /></el-icon>
                    <span>{{ formatNumber(currentPlayWork.comment_count) }} 评论</span>
                  </div>
                  <div class="player-stat-item">
                    <el-icon><Download /></el-icon>
                    <span>{{ formatNumber(currentPlayWork.share_count) }} 分享</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- 功能说明 -->
    <div
      v-if="!userInfo"
      class="feature-cards"
    >
      <div class="feature-card-item">
        <el-icon class="feature-icon">
          <User />
        </el-icon>
        <h3 class="feature-title">
          用户信息
        </h3>
        <p class="feature-desc">
          获取用户基本信息，粉丝数、作品数等
        </p>
      </div>
      <div class="feature-card-item">
        <el-icon class="feature-icon">
          <Grid />
        </el-icon>
        <h3 class="feature-title">
          作品列表
        </h3>
        <p class="feature-desc">
          查看用户发布的所有作品
        </p>
      </div>
      <div class="feature-card-item">
        <el-icon class="feature-icon">
          <Download />
        </el-icon>
        <h3 class="feature-title">
          批量下载
        </h3>
        <p class="feature-desc">
          一键下载用户所有作品
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.user-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 16px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 100%;
}

.back-btn {
  padding: 0 !important;
  margin-right: 8px !important;
  align-self: flex-start;
}

.search-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-top: 0;
}

.search-section.has-results {
  padding-top: 0;
}

.search-box {
  position: relative;
  z-index: 1;
  text-align: center;
  padding: 28px 36px 24px;
  background: linear-gradient(180deg, rgba(var(--app-surface-rgb) / 0.96), rgba(var(--app-surface-alt-rgb) / 0.92));
  backdrop-filter: blur(18px);
  border-radius: 24px;
  border: 1px solid rgba(var(--app-border-rgb) / 0.78);
  box-shadow: 0 18px 44px rgba(var(--app-shadow-rgb) / 0.10);
  max-width: 680px;
  width: min(100%, 680px);
  margin: 0 auto;
}

.search-header {
  margin-bottom: 22px;
}

.logo-icon {
  width: 64px;
  height: 64px;
  margin: 0 auto 14px;
  background: linear-gradient(135deg, rgb(var(--primary-color-rgb)), rgb(var(--app-accent-soft-rgb)));
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 30px;
  color: rgb(var(--utility-white-rgb));
  box-shadow: 0 14px 28px rgba(var(--primary-color-rgb) / 0.28);
}

.search-title {
  font-size: 26px;
  font-weight: 700;
  color: rgb(var(--app-text-strong-rgb));
  line-height: 1.15;
  letter-spacing: -0.02em;
  margin: 0 0 8px;
}

.search-subtitle {
  font-size: 13px;
  color: rgb(var(--app-text-muted-rgb));
  line-height: 1.6;
  max-width: 420px;
  margin: 0 auto;
}

.search-input-group {
  display: flex;
  gap: 12px;
}

.search-input-group .el-input {
  flex: 1;
}

.user-card {
  padding: 24px;
  border-radius: 16px;
  border: 1.5px solid rgba(var(--app-border-rgb) / 0.7);
  background: rgba(var(--app-surface-rgb) / 0.95);
  box-shadow: 0 8px 24px rgba(var(--app-shadow-rgb) / 0.08);
}

.user-card-content {
  display: flex;
  align-items: flex-start;
  gap: 24px;
}

.user-avatar {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  object-fit: cover;
  border: 3px solid rgba(var(--app-border-rgb) / 0.6);
  box-shadow: 0 4px 12px rgba(var(--app-shadow-rgb) / 0.1);
  flex-shrink: 0;
}

.user-details {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.user-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-nickname {
  font-size: 22px;
  font-weight: 700;
  color: rgb(var(--app-text-strong-rgb));
}

.user-ids {
  display: flex;
  align-items: center;
  gap: 16px;
}

.id-item {
  font-size: 13px;
  color: rgb(var(--app-text-muted-rgb));
  padding: 6px 14px;
  border-radius: 20px;
  background: rgba(var(--app-surface-alt-rgb) / 0.7);
  border: 1px solid rgba(var(--app-border-rgb) / 0.25);
}

.extra-info {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  background: rgba(var(--app-surface-alt-rgb) / 0.65);
  border-radius: 12px;
  border: 1px solid rgba(var(--app-border-rgb) / 0.3);
}

.info-text {
  font-size: 13px;
  color: rgb(var(--app-text-rgb));
}

.stats-row {
  display: flex;
  align-items: center;
  padding: 16px 20px;
  background: rgba(var(--app-surface-alt-rgb) / 0.65);
  border-radius: 12px;
  border: 1px solid rgba(var(--app-border-rgb) / 0.3);
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  flex: 1;
}

.stat-divider {
  width: 1px;
  height: 32px;
  background: rgba(var(--app-border-rgb) / 0.55);
}

.stat-value {
  font-size: 18px;
  font-weight: 700;
  color: rgb(var(--app-text-strong-rgb));
}

.stat-label {
  font-size: 12px;
  color: rgb(var(--app-text-muted-rgb));
}

.signature-text {
  padding: 14px 16px;
  background: rgba(var(--app-surface-alt-rgb) / 0.75);
  border-radius: 12px;
  border: 1px solid rgba(var(--app-border-rgb) / 0.5);
  color: rgb(var(--app-text-rgb));
  font-size: 14px;
  line-height: 1.7;
  margin: 0;
}

.works-section {
  padding: 20px;
  border-radius: 16px;
  border: 1px solid rgba(var(--app-border-rgb) / 0.52);
  background: rgba(var(--app-surface-rgb) / 0.92);
  box-shadow: 0 8px 24px rgba(var(--app-shadow-rgb) / 0.06);
}

.works-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
  padding-bottom: 14px;
  border-bottom: 1px solid rgba(var(--app-border-rgb) / 0.3);
}

.works-title {
  font-size: 16px;
  font-weight: 600;
  color: rgb(var(--app-text-strong-rgb));
  margin: 0;
}

.works-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.download-popover {
  padding: 8px 0;
}

.download-popover-title {
  font-size: 14px;
  color: rgb(var(--app-text-rgb));
  margin-bottom: 12px;
  padding: 0 12px;
}

.quality-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 0 8px;
}

.quality-option {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
}

.quality-option:hover:not(.disabled) {
  background: rgba(var(--app-surface-alt-rgb) / 0.8);
}

.quality-option.active {
  background: rgba(var(--primary-color-rgb) / 0.12);
}

.quality-option.disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.quality-unavailable {
  font-size: 12px;
  color: rgb(var(--app-text-subtle-rgb));
  font-weight: normal;
  margin-left: 4px;
}

.quality-radio {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 2px solid rgba(var(--app-border-rgb) / 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.quality-radio.checked {
  border-color: rgb(var(--primary-color-rgb));
}

.quality-radio-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: rgb(var(--primary-color-rgb));
}

.quality-info {
  flex: 1;
}

.quality-label {
  font-size: 14px;
  font-weight: 500;
  color: rgb(var(--app-text-strong-rgb));
}

.quality-desc {
  font-size: 12px;
  color: rgb(var(--app-text-subtle-rgb));
  margin-top: 2px;
}

.download-progress {
  margin: 12px 12px 0;
}

.download-actions {
  display: flex;
  gap: 8px;
  margin-top: 14px;
  padding: 0 12px;
}

.download-actions .flex-1 {
  flex: 1;
}

.video-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 16px;
}

.video-card {
  border-radius: 14px;
  overflow: hidden;
  background: rgba(var(--app-surface-alt-rgb) / 0.7);
  border: 2px solid transparent;
  cursor: pointer;
  transition: all 0.25s ease;
}

.video-card:hover {
  border-color: rgba(var(--primary-color-rgb) / 0.4);
  box-shadow: 0 8px 20px rgba(var(--app-shadow-rgb) / 0.12);
  transform: translateY(-2px);
}

.video-card.selected {
  border-color: rgb(var(--primary-color-rgb));
  box-shadow: 0 0 0 1px rgba(var(--primary-color-rgb) / 0.3);
}

.video-card-cover {
  position: relative;
  aspect-ratio: 9/16;
  overflow: hidden;
}

.cover-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.cover-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(var(--app-surface-alt-rgb) / 0.9);
}

.placeholder-icon {
  font-size: 40px;
  color: rgb(var(--app-text-subtle-rgb));
}

.select-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  opacity: 0;
  transition: opacity 0.2s;
}

.select-overlay.selected-overlay {
  opacity: 1;
}

.video-card:hover .select-overlay:not(.selected-overlay) {
  opacity: 0.5;
}

.select-checkbox {
  position: absolute;
  top: 8px;
  left: 8px;
  width: 24px;
  height: 24px;
  border-radius: 6px;
  border: 2px solid rgba(255, 255, 255, 0.5);
  background: rgba(0, 0, 0, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.select-checkbox.checked {
  background: rgb(var(--primary-color-rgb));
  border-color: rgb(var(--primary-color-rgb));
}

.check-icon {
  font-size: 14px;
  color: white;
}

.play-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  opacity: 0;
  transition: opacity 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}

.video-card:hover .play-overlay {
  opacity: 1;
}

.play-icon {
  font-size: 48px;
  color: white;
}

.video-stats {
  position: absolute;
  bottom: 8px;
  left: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.stat-badge {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(6px);
  border-radius: 20px;
  color: white;
  font-size: 12px;
}

.stat-badge .el-icon {
  font-size: 12px;
}

.video-card-info {
  padding: 12px;
}

.video-card-desc {
  font-size: 13px;
  color: rgb(var(--app-text-rgb));
  line-height: 1.5;
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 作品类型标识 */
.work-type-badge {
  position: absolute;
  top: 8px;
  left: 8px;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 500;
  color: white;
  backdrop-filter: blur(4px);
  pointer-events: none;
}

.work-type-badge .el-icon {
  font-size: 12px;
}

.badge-video {
  background: rgba(16, 185, 129, 0.85);
}

.badge-image {
  background: rgba(59, 130, 246, 0.85);
}

/* 播放弹窗 */
.player-overlay {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.8);
}

.player-modal {
  position: relative;
  width: 100%;
  max-width: 900px;
  max-height: 90vh;
  margin: 0 16px;
  background: rgba(var(--app-surface-rgb) / 0.98);
  border-radius: 18px;
  overflow: hidden;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.4);
  display: flex;
  flex-direction: column;
}

.player-close {
  position: absolute;
  top: 16px;
  right: 16px;
  z-index: 10;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.5);
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.2s;
}

.player-close:hover {
  background: rgba(0, 0, 0, 0.7);
}

.close-icon {
  font-size: 20px;
  color: white;
}

.player-content {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

@media (min-width: 768px) {
  .player-content {
    flex-direction: row;
  }
}

.player-video {
  flex: 0 0 auto;
  width: 100%;
  background: black;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  max-height: 50vh;
}

@media (min-width: 768px) {
  .player-video {
    flex: 1 1 auto;
    width: auto;
    max-height: 90vh;
    min-height: 0;
  }
}

.video-element {
  max-width: 100%;
  max-height: 100%;
  width: auto;
  height: auto;
  object-fit: contain;
  display: block;
}

.image-gallery {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.gallery-img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.player-info {
  flex: 1 1 auto;
  padding: 20px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 0;
}

@media (min-width: 768px) {
  .player-info {
    flex: 0 0 320px;
    max-width: 360px;
  }
}

.player-author {
  display: flex;
  align-items: center;
  gap: 12px;
}

.player-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  object-fit: cover;
}

.player-nickname {
  font-size: 15px;
  font-weight: 600;
  color: rgb(var(--app-text-strong-rgb));
}

.player-uid {
  font-size: 13px;
  color: rgb(var(--app-text-muted-rgb));
}

.player-desc {
  font-size: 14px;
  color: rgb(var(--app-text-rgb));
  line-height: 1.6;
  margin: 0;
}

.player-stats {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.player-stat-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: rgba(var(--app-surface-alt-rgb) / 0.7);
  border-radius: 10px;
  font-size: 13px;
  color: rgb(var(--app-text-muted-rgb));
}

.player-stat-item .el-icon {
  font-size: 16px;
}

/* 功能卡片 */
.feature-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

@media (max-width: 768px) {
  .feature-cards {
    grid-template-columns: 1fr;
  }
}

.feature-card-item {
  padding: 24px;
  border-radius: 16px;
  background: rgba(var(--app-surface-rgb) / 0.92);
  border: 1px solid rgba(var(--app-border-rgb) / 0.56);
  box-shadow: 0 4px 12px rgba(var(--app-shadow-rgb) / 0.05);
  transition: all 0.25s ease;
}

.feature-card-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(var(--app-shadow-rgb) / 0.1);
  border-color: rgba(var(--primary-color-rgb) / 0.3);
}

.feature-icon {
  font-size: 32px;
  color: rgb(var(--primary-color-rgb));
  margin-bottom: 16px;
}

.feature-title {
  font-size: 16px;
  font-weight: 600;
  color: rgb(var(--app-text-strong-rgb));
  margin: 0 0 8px;
}

.feature-desc {
  font-size: 13px;
  color: rgb(var(--app-text-muted-rgb));
  margin: 0;
  line-height: 1.6;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@media (max-width: 768px) {
  .user-page {
    padding: 16px;
  }

  .user-card-content {
    flex-direction: column;
    align-items: center;
    text-align: center;
  }

  .user-header,
  .user-ids,
  .extra-info {
    justify-content: center;
  }

  .stats-row {
    justify-content: center;
  }

  .video-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }

  .search-input-group {
    flex-direction: column;
  }
}
</style>
