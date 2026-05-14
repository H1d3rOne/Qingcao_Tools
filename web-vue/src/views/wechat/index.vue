<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Cellphone, Download, Search, VideoPlay } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  cancelWechatDownloadTask,
  clearWechatVideos,
  deleteWechatDownloadTask,
  getWechatDownloadTasks,
  getWechatDownloadTaskPreviewUrl,
  getWechatListenerStatus,
  getWechatVideos,
  openWechatDownloadTaskDir,
  queueWechatVideoDownload,
  retryWechatDownloadTask,
  selectWechatDownloadDir,
  startWechatListener,
  stopWechatListener,
  type WechatDownloadTaskItem,
  type WechatListenerStatus,
  type WechatVideoItem
} from '@/api/modules/wechat'

type TopTab = 'wechat' | 'tasks'
type TaskStatus = 'pending' | 'downloading' | 'completed' | 'failed'

const loading = ref(false)
const refreshing = ref(false)
const selectingDownloadDir = ref(false)
const videoSelectionMode = ref(false)
const taskSelectionMode = ref(false)
const activeTab = ref<TopTab>('wechat')
const activeTaskStatusTab = ref<TaskStatus>('pending')
const videoSearchKeyword = ref('')
const taskSearchKeyword = ref('')
const downloadingId = ref('')
const batchDownloading = ref(false)
const retryingTaskId = ref('')
const cancellingTaskId = ref('')
const openingTaskId = ref('')
const deletingTaskId = ref('')
const batchDeletingTask = ref(false)
const clearingVideos = ref(false)
const videoPage = ref(1)
const videoPageSize = ref(6)
const taskPage = ref(1)
const taskPageSize = ref(6)
const selectedVideoIds = ref<string[]>([])
const selectedTaskIds = ref<string[]>([])
const videos = ref<WechatVideoItem[]>([])
const tasks = ref<WechatDownloadTaskItem[]>([])
const status = ref<WechatListenerStatus>({
  listening: false,
  proxy_running: false,
  local_server_running: false,
  system_proxy_enabled: false,
  proxy_host: '127.0.0.1',
  proxy_port: 8090,
  local_server_port: 8000,
  video_count: 0,
  download_dir: '',
  last_error: null
})

let pollTimer: number | undefined
let pollingActive = false

const pageSizeOptions = [6, 10, 20, 40]
const taskStatusTabs: Array<{ name: TaskStatus; label: string }> = [
  { name: 'pending', label: '待下载' },
  { name: 'downloading', label: '下载中' },
  { name: 'completed', label: '已完成' },
  { name: 'failed', label: '失败' }
]

const filteredVideos = computed(() => {
  const keyword = videoSearchKeyword.value.trim().toLowerCase()
  if (!keyword) {
    return videos.value
  }
  return videos.value.filter(item => item.description.toLowerCase().includes(keyword))
})

const taskCounts = computed<Record<TaskStatus, number>>(() => ({
  pending: tasks.value.filter(item => item.status === 'pending').length,
  downloading: tasks.value.filter(item => item.status === 'downloading').length,
  completed: tasks.value.filter(item => item.status === 'completed').length,
  failed: tasks.value.filter(item => item.status === 'failed').length
}))

const filteredTasks = computed(() => {
  const keyword = taskSearchKeyword.value.trim().toLowerCase()
  return tasks.value.filter(item => {
    if (item.status !== activeTaskStatusTab.value) {
      return false
    }
    if (!keyword) {
      return true
    }
    return item.description.toLowerCase().includes(keyword)
  })
})

const pendingTaskCount = computed(() => {
  return taskCounts.value.pending + taskCounts.value.downloading
})

const videoTabCount = computed(() => {
  return status.value.video_count || videos.value.length
})

const taskTabCount = computed(() => {
  return tasks.value.length
})

const paginatedVideos = computed(() => {
  const start = (videoPage.value - 1) * videoPageSize.value
  return filteredVideos.value.slice(start, start + videoPageSize.value)
})

const paginatedTasks = computed(() => {
  const start = (taskPage.value - 1) * taskPageSize.value
  return filteredTasks.value.slice(start, start + taskPageSize.value)
})

const currentVideoPageIds = computed(() => paginatedVideos.value.map(item => item.id))
const currentTaskPageSelectableIds = computed(() =>
  paginatedTasks.value.filter(item => item.status !== 'downloading').map(item => item.id)
)

const selectedVideoCount = computed(() => selectedVideoIds.value.length)
const selectedTaskCount = computed(() => selectedTaskIds.value.length)

const videoPageAllSelected = computed(() => {
  const ids = currentVideoPageIds.value
  return ids.length > 0 && ids.every(id => selectedVideoIds.value.includes(id))
})

const videoPageIndeterminate = computed(() => {
  const ids = currentVideoPageIds.value
  if (ids.length === 0) return false
  const count = ids.filter(id => selectedVideoIds.value.includes(id)).length
  return count > 0 && count < ids.length
})

const taskPageAllSelected = computed(() => {
  const ids = currentTaskPageSelectableIds.value
  return ids.length > 0 && ids.every(id => selectedTaskIds.value.includes(id))
})

const taskPageIndeterminate = computed(() => {
  const ids = currentTaskPageSelectableIds.value
  if (ids.length === 0) return false
  const count = ids.filter(id => selectedTaskIds.value.includes(id)).length
  return count > 0 && count < ids.length
})

function formatDuration(duration: number) {
  if (!duration) {
    return '0s'
  }
  const minutes = Math.floor(duration / 60)
  const seconds = duration % 60
  if (minutes <= 0) {
    return `${seconds}s`
  }
  return `${minutes}m ${seconds}s`
}

function taskStatusLabel(taskStatus: TaskStatus) {
  switch (taskStatus) {
    case 'pending':
      return '待下载'
    case 'downloading':
      return '下载中'
    case 'completed':
      return '已完成'
    case 'failed':
      return '失败'
  }
}

function taskStatusType(taskStatus: string) {
  switch (taskStatus) {
    case 'pending':
      return 'warning'
    case 'downloading':
      return 'primary'
    case 'completed':
      return 'success'
    case 'failed':
      return 'danger'
    default:
      return 'info'
  }
}

function taskProgressStatus(task: WechatDownloadTaskItem) {
  if (task.status === 'completed') {
    return 'success'
  }
  if (task.status === 'failed') {
    return 'exception'
  }
  return undefined
}

function taskProgressDetail(task: WechatDownloadTaskItem) {
  if (task.status === 'pending') {
    return '等待下载'
  }

  const downloadedSize = task.downloaded_size_text || '0B'
  const totalSize = task.file_size_text || '-'

  if (task.status === 'completed') {
    return `已完成 ${totalSize}`
  }

  return `已下载 ${downloadedSize} / ${totalSize}`
}

function shouldKeepPolling() {
  return status.value.listening || pendingTaskCount.value > 0
}

function getPollingInterval() {
  if (tasks.value.some(item => item.status === 'downloading')) {
    return 1000
  }
  if (pendingTaskCount.value > 0) {
    return 1500
  }
  if (status.value.listening) {
    return 2000
  }
  return 3000
}

function getErrorMessage(error: unknown, fallback: string) {
  if (error instanceof Error && error.message) {
    return error.message
  }
  return fallback
}

function getTaskPreviewUrl(task: WechatDownloadTaskItem) {
  if (task.decoded_file || task.raw_file) {
    return getWechatDownloadTaskPreviewUrl(task.id, task.updated_at)
  }
  return task.url
}

function toggleVideoSelection(videoId: string, checked: boolean) {
  if (checked) {
    if (!selectedVideoIds.value.includes(videoId)) {
      selectedVideoIds.value = [...selectedVideoIds.value, videoId]
    }
    return
  }
  selectedVideoIds.value = selectedVideoIds.value.filter(id => id !== videoId)
}

function toggleTaskSelection(taskId: string, checked: boolean) {
  if (checked) {
    if (!selectedTaskIds.value.includes(taskId)) {
      selectedTaskIds.value = [...selectedTaskIds.value, taskId]
    }
    return
  }
  selectedTaskIds.value = selectedTaskIds.value.filter(id => id !== taskId)
}

function toggleVideoPageSelection(checked: boolean) {
  const pageIds = currentVideoPageIds.value
  if (checked) {
    selectedVideoIds.value = Array.from(new Set([...selectedVideoIds.value, ...pageIds]))
    return
  }
  selectedVideoIds.value = selectedVideoIds.value.filter(id => !pageIds.includes(id))
}

function toggleTaskPageSelection(checked: boolean) {
  const pageIds = currentTaskPageSelectableIds.value
  if (checked) {
    selectedTaskIds.value = Array.from(new Set([...selectedTaskIds.value, ...pageIds]))
    return
  }
  selectedTaskIds.value = selectedTaskIds.value.filter(id => !pageIds.includes(id))
}

function toggleVideoSelectionMode() {
  videoSelectionMode.value = !videoSelectionMode.value
  if (!videoSelectionMode.value) {
    selectedVideoIds.value = []
  }
}

function toggleTaskSelectionMode() {
  taskSelectionMode.value = !taskSelectionMode.value
  if (!taskSelectionMode.value) {
    selectedTaskIds.value = []
  }
}

async function handlePreviewEnter(event: Event) {
  const video = event.currentTarget as HTMLVideoElement | null
  if (!video || !video.dataset.previewUrl) {
    return
  }

  if (video.src !== video.dataset.previewUrl) {
    video.src = video.dataset.previewUrl
    video.load()
  }

  try {
    video.muted = true
    await video.play()
  } catch (error) {
    console.debug('任务封面预览播放失败:', error)
  }
}

function handlePreviewLeave(event: Event) {
  const video = event.currentTarget as HTMLVideoElement | null
  if (!video) {
    return
  }

  video.pause()
  video.currentTime = 0
}

async function loadStatus() {
  const response = await getWechatListenerStatus()
  status.value = response.data
}

async function loadVideos() {
  const response = await getWechatVideos()
  videos.value = response.data.items
  status.value.video_count = response.data.total
}

async function loadTasks() {
  const response = await getWechatDownloadTasks()
  tasks.value = response.data.items
}

async function refreshPage(showLoading = false) {
  if (showLoading) {
    refreshing.value = true
  }
  try {
    await Promise.all([loadStatus(), loadVideos(), loadTasks()])
  } finally {
    if (showLoading) {
      refreshing.value = false
    }
  }
}

function scheduleNextPolling() {
  if (!pollingActive) {
    return
  }
  pollTimer = window.setTimeout(runPolling, getPollingInterval())
}

async function runPolling() {
  if (!pollingActive) {
    return
  }
  try {
    await refreshPage()
  } catch (error) {
    console.error('轮询视频号状态失败:', error)
  }

  if (!pollingActive) {
    return
  }

  if (!shouldKeepPolling()) {
    stopPolling()
    return
  }

  scheduleNextPolling()
}

function startPolling() {
  stopPolling()
  pollingActive = true
  scheduleNextPolling()
}

function stopPolling() {
  pollingActive = false
  if (pollTimer) {
    window.clearTimeout(pollTimer)
    pollTimer = undefined
  }
}

async function toggleListener() {
  loading.value = true
  try {
    const response = status.value.listening ? await stopWechatListener() : await startWechatListener()
    status.value = response.data
    await refreshPage(true)
    if (shouldKeepPolling()) {
      startPolling()
    } else {
      stopPolling()
    }
    ElMessage.success(
      status.value.listening
        ? '监听已开启'
        : pendingTaskCount.value > 0
          ? '监听已关闭，下载任务已开始执行'
          : '监听已关闭'
    )
  } catch (error: unknown) {
    console.error(error)
    ElMessage.error(getErrorMessage(error, '操作失败'))
  } finally {
    loading.value = false
  }
}

async function handleSelectDownloadDir() {
  selectingDownloadDir.value = true
  try {
    const response = await selectWechatDownloadDir()
    status.value = response.data
    if (response.message === '已取消选择') {
      ElMessage.info(response.message)
    } else {
      ElMessage.success(response.message || '下载目录已更新')
    }
  } catch (error: unknown) {
    console.error(error)
    ElMessage.error(getErrorMessage(error, '选择下载目录失败'))
  } finally {
    selectingDownloadDir.value = false
  }
}

async function handleDownload(video: WechatVideoItem) {
  downloadingId.value = video.id
  try {
    const response = await queueWechatVideoDownload(video.id)
    ElMessage.success(response.message || '已加入下载任务列表')
    await loadTasks()
    if (shouldKeepPolling()) {
      startPolling()
    }
  } catch (error: unknown) {
    console.error(error)
    ElMessage.error(getErrorMessage(error, '提交下载任务失败'))
  } finally {
    downloadingId.value = ''
  }
}

async function handleBatchDownload() {
  const targetIds = selectedVideoIds.value.filter(id => videos.value.some(item => item.id === id))
  if (!targetIds.length) {
    ElMessage.warning('请先选择要下载的视频')
    return
  }

  batchDownloading.value = true
  let successCount = 0
  let failedCount = 0

  try {
    for (const videoId of targetIds) {
      try {
        await queueWechatVideoDownload(videoId)
        successCount += 1
      } catch (error) {
        console.error('批量下载任务提交失败:', error)
        failedCount += 1
      }
    }

    await loadTasks()
    if (shouldKeepPolling()) {
      startPolling()
    }

    if (successCount > 0) {
      ElMessage.success(
        failedCount > 0
          ? `已提交 ${successCount} 个视频，失败 ${failedCount} 个`
          : `已提交 ${successCount} 个视频到下载任务`
      )
      selectedVideoIds.value = selectedVideoIds.value.filter(id => !targetIds.includes(id))
    } else {
      ElMessage.error('批量提交下载任务失败')
    }
  } finally {
    batchDownloading.value = false
  }
}

async function handleRetryTask(task: WechatDownloadTaskItem) {
  retryingTaskId.value = task.id
  try {
    const response = await retryWechatDownloadTask(task.id)
    ElMessage.success(response.message || '任务已重新加入队列')
    await loadTasks()
    if (shouldKeepPolling()) {
      startPolling()
    }
  } catch (error: unknown) {
    console.error(error)
    ElMessage.error(getErrorMessage(error, '任务重试失败'))
  } finally {
    retryingTaskId.value = ''
  }
}

async function handleCancelTask(task: WechatDownloadTaskItem) {
  try {
    await ElMessageBox.confirm(`确定取消任务“${task.description || task.id}”吗？`, '取消下载', {
      type: 'warning',
      confirmButtonText: '取消任务',
      cancelButtonText: '返回'
    })
  } catch {
    return
  }

  cancellingTaskId.value = task.id
  try {
    const response = await cancelWechatDownloadTask(task.id)
    ElMessage.success(response.message || '已发送取消请求')
    await loadTasks()
    if (shouldKeepPolling()) {
      startPolling()
    } else {
      stopPolling()
    }
  } catch (error: unknown) {
    console.error(error)
    ElMessage.error(getErrorMessage(error, '取消任务失败'))
  } finally {
    cancellingTaskId.value = ''
  }
}

async function handleOpenTaskDir(task: WechatDownloadTaskItem) {
  openingTaskId.value = task.id
  try {
    const response = await openWechatDownloadTaskDir(task.id)
    ElMessage.success(response.message || '已打开下载目录')
  } catch (error: unknown) {
    console.error(error)
    ElMessage.error(getErrorMessage(error, '打开目录失败'))
  } finally {
    openingTaskId.value = ''
  }
}

async function handleDeleteTask(task: WechatDownloadTaskItem) {
  try {
    await ElMessageBox.confirm(`确定删除任务“${task.description || task.id}”吗？`, '删除任务', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }

  deletingTaskId.value = task.id
  try {
    const response = await deleteWechatDownloadTask(task.id)
    ElMessage.success(response.message || '任务已删除')
    await loadTasks()
    if (shouldKeepPolling()) {
      startPolling()
    }
  } catch (error: unknown) {
    console.error(error)
    ElMessage.error(getErrorMessage(error, '删除任务失败'))
  } finally {
    deletingTaskId.value = ''
  }
}

async function handleBatchDeleteTasks() {
  const targetIds = selectedTaskIds.value.filter(id =>
    tasks.value.some(item => item.id === id && item.status !== 'downloading')
  )

  if (!targetIds.length) {
    ElMessage.warning('请先选择可删除的任务')
    return
  }

  try {
    await ElMessageBox.confirm(`确定删除选中的 ${targetIds.length} 个任务吗？`, '批量删除任务', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }

  batchDeletingTask.value = true
  let successCount = 0
  let failedCount = 0

  try {
    for (const taskId of targetIds) {
      try {
        await deleteWechatDownloadTask(taskId)
        successCount += 1
      } catch (error) {
        console.error('批量删除任务失败:', error)
        failedCount += 1
      }
    }

    await loadTasks()
    if (shouldKeepPolling()) {
      startPolling()
    }

    if (successCount > 0) {
      ElMessage.success(
        failedCount > 0
          ? `已删除 ${successCount} 个任务，失败 ${failedCount} 个`
          : `已删除 ${successCount} 个任务`
      )
      selectedTaskIds.value = selectedTaskIds.value.filter(id => !targetIds.includes(id))
    } else {
      ElMessage.error('批量删除任务失败')
    }
  } finally {
    batchDeletingTask.value = false
  }
}

async function handleClearVideos() {
  if (!filteredVideos.value.length) {
    ElMessage.warning('当前没有可清空的视频记录')
    return
  }

  try {
    await ElMessageBox.confirm('确定清空当前视频列表中的所有记录吗？', '清空视频列表', {
      type: 'warning',
      confirmButtonText: '清空',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }

  clearingVideos.value = true
  try {
    const response = await clearWechatVideos()
    selectedVideoIds.value = []
    videoSelectionMode.value = false
    await loadVideos()
    ElMessage.success(response.message || '视频列表已清空')
  } catch (error: unknown) {
    console.error(error)
    ElMessage.error(getErrorMessage(error, '清空视频列表失败'))
  } finally {
    clearingVideos.value = false
  }
}

function handleVideoPageChange(page: number) {
  videoPage.value = page
}

function handleVideoPageSizeChange(size: number) {
  videoPageSize.value = size
  videoPage.value = 1
}

function handleTaskPageChange(page: number) {
  taskPage.value = page
}

function handleTaskPageSizeChange(size: number) {
  taskPageSize.value = size
  taskPage.value = 1
}

watch(videoSearchKeyword, () => {
  videoPage.value = 1
})

watch(taskSearchKeyword, () => {
  taskPage.value = 1
})

watch(activeTaskStatusTab, () => {
  taskPage.value = 1
  selectedTaskIds.value = []
})

watch(filteredVideos, items => {
  const maxPage = Math.max(1, Math.ceil(items.length / videoPageSize.value))
  if (videoPage.value > maxPage) {
    videoPage.value = maxPage
  }
})

watch(filteredTasks, items => {
  const maxPage = Math.max(1, Math.ceil(items.length / taskPageSize.value))
  if (taskPage.value > maxPage) {
    taskPage.value = maxPage
  }
  const ids = new Set(tasks.value.map(item => item.id))
  selectedTaskIds.value = selectedTaskIds.value.filter(id => ids.has(id))
})

watch(videos, items => {
  const ids = new Set(items.map(item => item.id))
  selectedVideoIds.value = selectedVideoIds.value.filter(id => ids.has(id))
  if (!items.length) {
    videoSelectionMode.value = false
  }
})

watch(tasks, items => {
  const ids = new Set(items.map(item => item.id))
  selectedTaskIds.value = selectedTaskIds.value.filter(id => ids.has(id))
  if (!items.length) {
    taskSelectionMode.value = false
  }
})

onMounted(async () => {
  try {
    await refreshPage(true)
    if (shouldKeepPolling()) {
      startPolling()
    }
  } catch (error: unknown) {
    console.error(error)
    ElMessage.error(getErrorMessage(error, '初始化失败'))
  }
})

onBeforeUnmount(() => {
  stopPolling()
})
</script>

<template>
  <div class="wechat-page max-w-6xl mx-auto space-y-2">
    <el-tabs
      v-model="activeTab"
      class="page-tabs"
    >
      <el-tab-pane name="wechat">
        <template #label>
          <div class="top-tab-label">
            <el-icon size="20">
              <Cellphone />
            </el-icon>
            <span>视频号</span>
            <span class="tab-count">
              {{ videoTabCount }}
            </span>
          </div>
        </template>

        <div class="wechat-panel">
          <div class="toolbar-panel">
            <el-button
              class="listener-btn toolbar-listener-btn"
              :type="status.listening ? 'danger' : 'primary'"
              size="large"
              :loading="loading"
              @click="toggleListener"
            >
              {{ status.listening ? '关闭监听' : '开启监听' }}
            </el-button>

            <el-input
              v-model="videoSearchKeyword"
              class="toolbar-search"
              placeholder="搜索视频描述..."
              size="large"
              clearable
            >
              <template #prefix>
                <el-icon>
                  <Search />
                </el-icon>
              </template>
            </el-input>

            <el-tooltip
              effect="dark"
              placement="top"
              :show-after="120"
              :content="status.download_dir || '未设置下载目录'"
            >
              <el-button
                class="dir-select-btn"
                type="success"
                :loading="selectingDownloadDir"
                @click="handleSelectDownloadDir"
              >
                设置目录
              </el-button>
            </el-tooltip>

            <div class="toolbar-status-pill">
              <span
                class="toolbar-status-dot"
                :class="{ 'is-active': status.listening }"
              />
              <span>{{ status.listening ? '监听进行中' : '监听未开启' }}</span>
            </div>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-4 gap-3">
            <div class="status-card">
              <span class="status-label">代理服务</span>
              <strong :class="status.proxy_running ? 'status-active' : 'status-inactive'">
                {{ status.proxy_running ? '运行中' : '未运行' }}
              </strong>
            </div>
            <div class="status-card">
              <span class="status-label">系统代理</span>
              <strong :class="status.system_proxy_enabled ? 'status-active' : 'status-inactive'">
                {{ status.system_proxy_enabled ? '已开启' : '未开启' }}
              </strong>
            </div>
            <div class="status-card">
              <span class="status-label">本地服务</span>
              <strong :class="status.local_server_running ? 'status-active' : 'status-inactive'">
                {{ status.local_server_running ? '运行中' : '未运行' }}
              </strong>
            </div>
            <div class="status-card">
              <span class="status-label">已捕获视频</span>
              <strong class="status-value">
                {{ videoTabCount }}
              </strong>
            </div>
          </div>

          <div class="panel-header">
            <div class="text-sm text-app-text-muted">
              共 {{ filteredVideos.length }} / {{ videoTabCount }} 个视频
            </div>

            <div class="panel-actions">
              <div
                v-if="videoSelectionMode"
                class="selection-toolbar"
              >
                <el-checkbox
                  :model-value="videoPageAllSelected"
                  :indeterminate="videoPageIndeterminate"
                  @change="value => toggleVideoPageSelection(Boolean(value))"
                >
                  本页全选
                </el-checkbox>

                <el-button
                  type="primary"
                  plain
                  :disabled="selectedVideoCount === 0"
                  :loading="batchDownloading"
                  @click="handleBatchDownload"
                >
                  批量下载 {{ selectedVideoCount > 0 ? `(${selectedVideoCount})` : '' }}
                </el-button>
              </div>

              <el-button
                plain
                type="primary"
                :disabled="filteredVideos.length === 0"
                @click="toggleVideoSelectionMode"
              >
                {{ videoSelectionMode ? '取消选择' : '选择列表' }}
              </el-button>

              <el-button
                v-if="filteredVideos.length > 0"
                text
                :loading="clearingVideos"
                @click="handleClearVideos"
              >
                清空列表
              </el-button>

              <div class="filter-controls">
                <span class="control-label">每页</span>
                <el-select
                  :model-value="videoPageSize"
                  class="size-select"
                  size="small"
                  @change="handleVideoPageSizeChange"
                >
                  <el-option
                    v-for="size in pageSizeOptions"
                    :key="`video-size-${size}`"
                    :label="`${size} 条`"
                    :value="size"
                  />
                </el-select>
              </div>

              <el-button
                text
                :loading="refreshing"
                @click="refreshPage(true)"
              >
                刷新列表
              </el-button>
            </div>
          </div>

          <div
            v-if="filteredVideos.length"
            class="space-y-5"
          >
            <div class="video-list grid grid-cols-1 xl:grid-cols-2 gap-4">
              <div
                v-for="video in paginatedVideos"
                :key="video.id"
                class="video-item"
              >
                <div
                  v-if="videoSelectionMode"
                  class="item-select"
                >
                  <el-checkbox
                    :model-value="selectedVideoIds.includes(video.id)"
                    @change="value => toggleVideoSelection(video.id, Boolean(value))"
                  />
                </div>

                <div class="cover-wrap">
                  <video
                    v-if="video.url"
                    class="cover-image preview-video"
                    :poster="video.cover_url"
                    :data-preview-url="video.url"
                    muted
                    loop
                    playsinline
                    preload="none"
                    @mouseenter="handlePreviewEnter"
                    @mouseleave="handlePreviewLeave"
                  />
                  <img
                    v-else
                    :src="video.cover_url"
                    :alt="video.description || '微信视频封面'"
                    class="cover-image"
                  >
                </div>

                <div class="video-content">
                  <div class="video-desc">
                    {{ video.description || '未命名视频' }}
                  </div>

                  <div class="video-meta">
                    <span>大小：{{ video.file_size_text }}</span>
                    <span>时长：{{ formatDuration(video.duration) }}</span>
                  </div>

                  <div class="video-actions">
                    <el-button
                      class="action-btn"
                      type="primary"
                      :loading="downloadingId === video.id"
                      @click="handleDownload(video)"
                    >
                      下载
                    </el-button>
                  </div>
                </div>
              </div>
            </div>

            <div class="pagination-wrap">
              <el-pagination
                background
                layout="total, sizes, prev, pager, next"
                :total="filteredVideos.length"
                :page-size="videoPageSize"
                :page-sizes="pageSizeOptions"
                :current-page="videoPage"
                @current-change="handleVideoPageChange"
                @size-change="handleVideoPageSizeChange"
              />
            </div>
          </div>

          <el-empty
            v-else
            description="暂无捕获到的视频"
          >
            <template #image>
              <el-icon
                size="64"
                class="text-app-text-subtle"
              >
                <VideoPlay />
              </el-icon>
            </template>

            <template #description>
              <div class="text-app-text-muted text-sm leading-6">
                <div>1. 点击左侧按钮开启监听</div>
                <div>2. 在微信中打开视频号页面并播放目标视频</div>
                <div>3. 列表会自动出现可下载的视频记录</div>
              </div>
            </template>
          </el-empty>
        </div>
      </el-tab-pane>

      <el-tab-pane name="tasks">
        <template #label>
          <div class="top-tab-label">
            <el-icon size="20">
              <Download />
            </el-icon>
            <span>下载任务</span>
            <span
              class="tab-count"
              :class="{ 'tab-count-active': pendingTaskCount > 0 }"
            >
              {{ taskTabCount }}
            </span>
          </div>
        </template>

        <div class="wechat-panel">
          <div class="flex flex-col xl:flex-row gap-3">
            <el-input
              v-model="taskSearchKeyword"
              placeholder="搜索任务描述..."
              size="large"
              clearable
            >
              <template #prefix>
                <el-icon>
                  <Search />
                </el-icon>
              </template>
            </el-input>
          </div>

          <el-tabs
            v-model="activeTaskStatusTab"
            class="task-status-tabs"
          >
            <el-tab-pane
              v-for="tab in taskStatusTabs"
              :key="tab.name"
              :name="tab.name"
            >
              <template #label>
                <div class="tab-label">
                  <span>{{ tab.label }}</span>
                  <span
                    class="tab-count"
                    :class="{
                      'tab-count-active':
                        (tab.name === 'pending' || tab.name === 'downloading') &&
                        taskCounts[tab.name] > 0
                    }"
                  >
                    {{ taskCounts[tab.name] }}
                  </span>
                </div>
              </template>
            </el-tab-pane>
          </el-tabs>

          <div class="panel-header">
            <div class="space-y-1">
              <div class="text-sm text-app-text-rgb">
                {{ taskStatusLabel(activeTaskStatusTab) }} {{ filteredTasks.length }} / {{ taskTabCount }}
              </div>
              <div class="text-xs text-app-text-subtle">
                任务提交后会立即在后台下载，监听状态不会阻塞下载队列
              </div>
            </div>

            <div class="panel-actions">
              <div
                v-if="taskSelectionMode"
                class="selection-toolbar"
              >
                <el-checkbox
                  :disabled="currentTaskPageSelectableIds.length === 0"
                  :model-value="taskPageAllSelected"
                  :indeterminate="taskPageIndeterminate"
                  @change="value => toggleTaskPageSelection(Boolean(value))"
                >
                  本页全选
                </el-checkbox>

                <el-button
                  type="danger"
                  plain
                  :disabled="selectedTaskCount === 0"
                  :loading="batchDeletingTask"
                  @click="handleBatchDeleteTasks"
                >
                  批量删除 {{ selectedTaskCount > 0 ? `(${selectedTaskCount})` : '' }}
                </el-button>
              </div>

              <el-button
                plain
                type="primary"
                :disabled="filteredTasks.length === 0"
                @click="toggleTaskSelectionMode"
              >
                {{ taskSelectionMode ? '取消选择' : '选择列表' }}
              </el-button>

              <div class="filter-controls">
                <span class="control-label">每页</span>
                <el-select
                  :model-value="taskPageSize"
                  class="size-select"
                  size="small"
                  @change="handleTaskPageSizeChange"
                >
                  <el-option
                    v-for="size in pageSizeOptions"
                    :key="`task-size-${size}`"
                    :label="`${size} 条`"
                    :value="size"
                  />
                </el-select>
              </div>

              <el-button
                text
                :loading="refreshing"
                @click="refreshPage(true)"
              >
                刷新列表
              </el-button>
            </div>
          </div>

          <div
            v-if="filteredTasks.length"
            class="space-y-5"
          >
            <div class="task-list space-y-3">
              <div
                v-for="task in paginatedTasks"
                :key="task.id"
                class="task-item"
              >
                <div
                  v-if="taskSelectionMode"
                  class="item-select"
                >
                  <el-checkbox
                    :disabled="task.status === 'downloading'"
                    :model-value="selectedTaskIds.includes(task.id)"
                    @change="value => toggleTaskSelection(task.id, Boolean(value))"
                  />
                </div>

                <div class="task-cover-wrap">
                  <video
                    v-if="getTaskPreviewUrl(task)"
                    class="cover-image task-cover-video"
                    :poster="task.cover_url"
                    :data-preview-url="getTaskPreviewUrl(task)"
                    muted
                    loop
                    playsinline
                    preload="none"
                    @mouseenter="handlePreviewEnter"
                    @mouseleave="handlePreviewLeave"
                  />
                  <img
                    v-else-if="task.cover_url"
                    :src="task.cover_url"
                    :alt="task.description || '任务封面'"
                    class="cover-image"
                  >
                  <div
                    v-else
                    class="task-cover-placeholder"
                  >
                    <el-icon size="28">
                      <VideoPlay />
                    </el-icon>
                  </div>
                </div>

                <div class="task-content">
                  <div class="task-header">
                    <div class="video-desc">
                      {{ task.description || '未命名视频' }}
                    </div>

                    <el-tag
                      size="small"
                      effect="dark"
                      :type="taskStatusType(task.status)"
                    >
                      {{ taskStatusLabel(task.status as TaskStatus) }}
                    </el-tag>
                  </div>

                  <div class="video-meta">
                    <span>大小：{{ task.file_size_text }}</span>
                    <span>时长：{{ formatDuration(task.duration) }}</span>
                  </div>

                  <div class="task-progress">
                    <div class="task-progress-head">
                      <span>{{ taskProgressDetail(task) }}</span>
                      <span>{{ task.progress }}%</span>
                    </div>

                    <el-progress
                      :percentage="task.progress"
                      :status="taskProgressStatus(task)"
                      :stroke-width="10"
                      :show-text="false"
                    />
                  </div>

                  <div class="task-footnote">
                    <div
                      v-if="task.error"
                      class="task-error"
                    >
                      {{ task.error }}
                    </div>
                    <div
                      v-else-if="task.decoded_file"
                      class="task-path"
                      :title="task.decoded_file"
                    >
                      解密文件：{{ task.decoded_file }}
                    </div>
                    <div
                      v-else-if="task.raw_file"
                      class="task-path"
                      :title="task.raw_file"
                    >
                      原始文件：{{ task.raw_file }}
                    </div>
                  </div>

                  <div class="task-actions">
                    <el-button
                      v-if="task.status === 'downloading'"
                      plain
                      type="warning"
                      :loading="cancellingTaskId === task.id"
                      @click="handleCancelTask(task)"
                    >
                      取消下载
                    </el-button>

                    <el-button
                      v-if="task.status === 'completed'"
                      plain
                      type="primary"
                      :loading="openingTaskId === task.id"
                      @click="handleOpenTaskDir(task)"
                    >
                      打开目录
                    </el-button>

                    <el-button
                      v-if="task.status === 'failed'"
                      plain
                      type="warning"
                      :loading="retryingTaskId === task.id"
                      @click="handleRetryTask(task)"
                    >
                      重试
                    </el-button>

                    <el-button
                      v-if="task.status !== 'downloading'"
                      plain
                      type="danger"
                      :loading="deletingTaskId === task.id"
                      @click="handleDeleteTask(task)"
                    >
                      删除
                    </el-button>
                  </div>
                </div>
              </div>
            </div>

            <div class="pagination-wrap">
              <el-pagination
                background
                layout="total, sizes, prev, pager, next"
                :total="filteredTasks.length"
                :page-size="taskPageSize"
                :page-sizes="pageSizeOptions"
                :current-page="taskPage"
                @current-change="handleTaskPageChange"
                @size-change="handleTaskPageSizeChange"
              />
            </div>
          </div>

          <el-empty :description="`暂无${taskStatusLabel(activeTaskStatusTab)}任务`" />
        </div>
      </el-tab-pane>
    </el-tabs>

    <div
      v-if="status.last_error"
      class="error-banner"
    >
      {{ status.last_error }}
    </div>
  </div>
</template>

<style scoped>
.listener-btn {
  min-width: 140px;
}

.toolbar-panel {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto auto;
  gap: 12px;
  align-items: center;
  padding: 14px;
  border-radius: 18px;
  border: 1px solid rgba(var(--app-border-rgb) / 0.5);
  background:
    linear-gradient(135deg, rgba(var(--primary-color-rgb) / 0.06), rgba(var(--app-accent-alt-rgb) / 0.03)),
    rgba(var(--app-surface-rgb) / 0.95);
  box-shadow:
    0 1px 2px rgba(var(--app-shadow-rgb) / 0.04),
    0 4px 12px rgba(var(--app-shadow-rgb) / 0.06);
}

.toolbar-listener-btn {
  min-width: 156px;
  font-weight: 700;
  box-shadow: 0 12px 28px rgba(var(--primary-color-rgb) / 0.16);
}

.toolbar-search :deep(.el-input__wrapper) {
  min-height: 44px;
  border-radius: 14px;
  background: rgba(var(--app-surface-rgb) / 0.9);
  box-shadow: inset 0 0 0 1px rgba(var(--app-border-rgb) / 0.5);
}

.toolbar-search :deep(.el-input__wrapper.is-focus) {
  box-shadow:
    inset 0 0 0 1px rgba(var(--primary-color-rgb) / 0.45),
    0 0 0 3px rgba(var(--primary-color-rgb) / 0.08);
}

.toolbar-status-pill {
  min-width: 118px;
  height: 44px;
  padding: 0 14px;
  border-radius: 14px;
  border: 1px solid rgba(var(--app-border-rgb) / 0.5);
  background: rgba(var(--app-surface-rgb) / 0.85);
  color: rgb(var(--app-text-rgb));
  font-size: 13px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  white-space: nowrap;
}

.toolbar-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: rgb(var(--app-text-subtle-rgb));
  box-shadow: 0 0 0 4px rgba(var(--app-text-subtle-rgb) / 0.15);
}

.toolbar-status-dot.is-active {
  background: rgb(var(--primary-color-rgb));
  box-shadow: 0 0 0 4px rgba(var(--primary-color-rgb) / 0.16);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.panel-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  flex-wrap: wrap;
}

.selection-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.filter-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.control-label {
  font-size: 12px;
  color: rgb(var(--app-text-muted-rgb));
}

.size-select {
  width: 104px;
}

.dir-select-btn {
  min-width: 120px;
}

.tab-label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.top-tab-label {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: -0.01em;
}

.tab-count {
  min-width: 26px;
  height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  background: rgba(var(--app-surface-alt-rgb) / 0.9);
  border: 1px solid rgba(var(--app-border-rgb) / 0.3);
  color: rgb(var(--app-text-muted-rgb));
  font-size: 12px;
  font-weight: 600;
  line-height: 20px;
  text-align: center;
}

.tab-count-active {
  background: rgba(var(--primary-color-rgb) / 0.25);
  color: rgb(var(--primary-color-rgb));
}

.status-card {
  padding: 16px;
  border-radius: 14px;
  background: rgba(var(--app-surface-alt-rgb) / 0.8);
  border: 1px solid rgba(var(--app-border-rgb) / 0.5);
  display: flex;
  flex-direction: column;
  gap: 8px;
  box-shadow: 0 2px 6px rgba(var(--app-shadow-rgb) / 0.04);
}

.status-label {
  font-size: 12px;
  color: rgb(var(--app-text-muted-rgb));
}

.video-item,
.task-item {
  display: flex;
  gap: 16px;
  padding: 16px;
  border-radius: 16px;
  border: 1px solid rgba(var(--app-border-rgb) / 0.5);
  position: relative;
}

.video-item {
  background: rgba(var(--app-surface-rgb) / 0.85);
  min-height: 184px;
  box-shadow:
    0 1px 2px rgba(var(--app-shadow-rgb) / 0.04),
    0 4px 12px rgba(var(--app-shadow-rgb) / 0.06);
}

.task-item {
  background: rgba(var(--app-surface-alt-rgb) / 0.7);
  min-height: 188px;
  box-shadow:
    0 1px 2px rgba(var(--app-shadow-rgb) / 0.04),
    0 4px 12px rgba(var(--app-shadow-rgb) / 0.06);
}

.cover-wrap {
  width: 180px;
  min-height: 152px;
  border-radius: 12px;
  overflow: hidden;
  background: rgba(var(--app-surface-alt-rgb) / 0.9);
  flex-shrink: 0;
  align-self: stretch;
}

.item-select {
  position: absolute;
  top: 14px;
  left: 14px;
  z-index: 2;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 999px;
  background: rgba(var(--app-surface-rgb) / 0.9);
  border: 1px solid rgba(var(--app-border-rgb) / 0.5);
  backdrop-filter: blur(8px);
}

.item-select :deep(.el-checkbox) {
  margin-right: 0;
}

.item-select :deep(.el-checkbox__input) {
  display: inline-flex;
}

.task-cover-wrap {
  width: 156px;
  min-height: 124px;
  border-radius: 12px;
  overflow: hidden;
  background: rgba(var(--app-surface-alt-rgb) / 0.9);
  flex-shrink: 0;
  align-self: stretch;
}

.cover-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.preview-video,
.task-cover-video {
  display: block;
  cursor: pointer;
}

.task-cover-placeholder {
  width: 100%;
  height: 100%;
  color: rgb(var(--app-text-subtle-rgb));
  display: flex;
  align-items: center;
  justify-content: center;
}

.video-content,
.task-content {
  min-width: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.video-content {
  gap: 12px;
  min-height: 152px;
}

.task-content {
  gap: 10px;
  min-height: 156px;
}

.video-desc {
  color: rgb(var(--app-text-strong-rgb));
  font-size: 15px;
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.task-content .video-desc {
  -webkit-line-clamp: 2;
  min-height: 48px;
  max-height: 48px;
}

.video-content .video-desc {
  min-height: 72px;
}

.video-meta {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  color: rgb(var(--app-text-muted-rgb));
  font-size: 13px;
}

.video-actions {
  margin-top: auto;
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.action-btn {
  min-width: 128px;
  font-weight: 600;
}

.task-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.task-progress {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 40px;
}

.task-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  padding-top: 4px;
  min-height: 40px;
  align-items: center;
}

:deep(.task-actions .el-button) {
  min-height: 36px;
  padding: 0 14px;
}

.task-progress-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: rgb(var(--app-text-rgb));
  font-size: 12px;
}

.task-error {
  color: rgb(252 165 165);
  font-size: 13px;
  line-height: 1.6;
  width: 100%;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.task-footnote {
  min-height: 40px;
  max-height: 40px;
  display: flex;
  align-items: flex-start;
  overflow: hidden;
}

.task-path {
  color: rgb(var(--app-text-muted-rgb));
  font-size: 12px;
  line-height: 1.6;
  width: 100%;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.pagination-wrap {
  display: flex;
  justify-content: center;
}

:deep(.page-tabs > .el-tabs__content) {
  padding: 0;
}

:deep(.page-tabs > .el-tabs__header) {
  margin: 0;
  padding: 10px 16px 0;
  border-radius: 16px;
  border: 1px solid rgba(var(--app-border-rgb) / 0.4);
  background: rgba(var(--app-surface-rgb) / 0.96);
  box-shadow:
    0 1px 2px rgba(var(--app-shadow-rgb) / 0.04),
    0 4px 12px rgba(var(--app-shadow-rgb) / 0.06);
  position: sticky;
  top: 0;
  z-index: 30;
}

:deep(.page-tabs > .el-tabs__header .el-tabs__nav-wrap) {
  padding: 0;
}

:deep(.page-tabs > .el-tabs__header .el-tabs__nav-wrap::after) {
  display: none;
}

:deep(.page-tabs > .el-tabs__header .el-tabs__nav) {
  display: flex;
  gap: 6px;
  width: 100%;
}

:deep(.page-tabs .el-tabs__nav-wrap::after),
:deep(.task-status-tabs .el-tabs__nav-wrap::after) {
  background-color: rgba(var(--app-border-rgb) / 0.5);
}

:deep(.page-tabs .el-tabs__item),
:deep(.task-status-tabs .el-tabs__item) {
  color: rgb(var(--app-text-muted-rgb));
}

:deep(.page-tabs .el-tabs__item) {
  height: auto;
  padding: 14px 24px 12px;
  border-radius: 12px 12px 0 0;
  transition: all 0.25s ease;
  background: transparent;
  border: 1px solid transparent;
  border-bottom: none;
  justify-content: center;
  margin-bottom: -1px;
}

:deep(.page-tabs .el-tabs__item:hover) {
  color: rgb(var(--app-text-strong-rgb));
  background: rgba(var(--app-surface-alt-rgb) / 0.7);
}

:deep(.page-tabs .el-tabs__item.is-active),
:deep(.task-status-tabs .el-tabs__item.is-active) {
  color: rgb(var(--app-text-strong-rgb));
}

:deep(.page-tabs .el-tabs__item.is-active) {
  background: rgba(var(--app-surface-alt-rgb) / 0.9);
  border-color: rgba(var(--app-border-rgb) / 0.4);
  box-shadow:
    0 -2px 8px rgba(var(--app-shadow-rgb) / 0.04),
    inset 0 2px 0 rgb(var(--primary-color-rgb));
}

:deep(.page-tabs .el-tabs__active-bar),
:deep(.task-status-tabs .el-tabs__active-bar) {
  background-color: rgb(var(--primary-color-rgb));
}

:deep(.page-tabs .el-tabs__active-bar) {
  display: none;
}

:deep(.page-tabs .el-tabs__item.is-active .tab-count) {
  background: rgba(var(--primary-color-rgb) / 0.2);
  color: rgb(var(--primary-color-rgb));
}

:deep(.page-tabs .el-tabs__item.is-active .top-tab-label .el-icon) {
  color: rgb(var(--primary-color-rgb));
}

:deep(.task-status-tabs .el-tabs__header) {
  margin-bottom: 4px;
}

:deep(.task-status-tabs .el-tabs__content) {
  display: none;
}

@media (max-width: 1024px) {
  .toolbar-panel {
    grid-template-columns: 1fr 1fr;
  }

  .toolbar-search {
    grid-column: 1 / -1;
  }

  .dir-select-btn {
    width: 100%;
  }

  .selection-toolbar {
    width: 100%;
  }
}

@media (max-width: 768px) {
  .toolbar-panel {
    grid-template-columns: 1fr;
  }

  .panel-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .panel-actions {
    width: 100%;
    justify-content: flex-start;
  }

  .selection-toolbar {
    width: 100%;
    justify-content: space-between;
  }

  .filter-controls {
    width: 100%;
  }

  .size-select {
    flex: 1;
  }

  .video-item,
  .task-item {
    flex-direction: column;
  }

  .cover-wrap,
  .task-cover-wrap {
    width: 100%;
  }

  .cover-wrap {
    height: 180px;
  }

  .task-cover-wrap {
    min-height: 160px;
  }

  .task-header,
  .task-progress-head {
    flex-direction: column;
    align-items: flex-start;
  }

  .top-tab-label {
    font-size: 16px;
  }
}

.wechat-panel {
  padding: 16px 20px;
  border-radius: 14px;
  background: rgba(var(--app-surface-rgb) / 0.92);
  border: 1px solid rgba(var(--app-border-rgb) / 0.7);
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.status-active {
  color: rgb(var(--primary-color-rgb));
}

.status-inactive {
  color: rgb(var(--app-text-muted-rgb));
}

.status-value {
  color: rgb(var(--app-text-strong-rgb));
}

.error-banner {
  border-radius: 10px;
  background: rgba(239 68 68, 0.08);
  border: 1px solid rgba(239 68 68, 0.2);
  color: rgb(252 165 165);
  font-size: 14px;
  padding: 12px 16px;
}
</style>
