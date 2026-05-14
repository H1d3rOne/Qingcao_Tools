<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { VideoPlay, User, Search, Star, Warning } from '@element-plus/icons-vue'
import { getStatus, getFeed } from '@/api'
import type { FeedVideo } from '@/api/modules/home'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'

const router = useRouter()

const videos = ref<FeedVideo[]>([])
const loading = ref(false)
const feedError = ref('')
const status = ref<{ cookie_configured: boolean }>({
  cookie_configured: false
})

onMounted(async () => {
  await loadStatus()
  // feed 接口有问题，暂不加载
  // await loadVideos()
})

async function loadStatus() {
  try {
    const res = await getStatus()
    if (res && res.data) {
      status.value = res.data
    }
  } catch (err) {
    console.error('获取状态失败:', err)
  }
}

async function loadVideos() {
  loading.value = true
  feedError.value = ''
  try {
    const res = await getFeed()
    videos.value = res?.data || []
  } catch (err: any) {
    console.error('加载视频失败:', err)
    feedError.value = err.message || '加载失败'
  } finally {
    loading.value = false
  }
}

function goToSearch() {
  router.push('/search')
}

function goToVideo() {
  router.push('/video')
}

function goToUser() {
  router.push('/user')
}
</script>

<template>
  <div class="home-page">
    <!-- 状态栏 -->
    <div class="status-bar mb-6 p-4 rounded-xl bg-dark-card flex items-center justify-between">
      <div class="flex items-center gap-4">
        <span class="text-gray-400">服务状态：</span>
        <el-tag :type="status?.cookie_configured ? 'success' : 'danger'">
          {{ status?.cookie_configured ? '正常' : 'Cookies 未配置' }}
        </el-tag>
      </div>
    </div>

    <!-- 快捷入口 -->
    <div class="quick-entry grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
      <div
        class="entry-card p-6 rounded-xl bg-dark-card cursor-pointer hover:bg-dark-lighter transition-colors"
        @click="goToVideo"
      >
        <el-icon class="text-primary text-4xl mb-4">
          <VideoPlay />
        </el-icon>
        <h3 class="text-white text-lg font-medium mb-2">
          作品查询
        </h3>
        <p class="text-gray-400 text-sm">
          输入视频链接获取详情、评论、下载
        </p>
      </div>
      <div
        class="entry-card p-6 rounded-xl bg-dark-card cursor-pointer hover:bg-dark-lighter transition-colors"
        @click="goToUser"
      >
        <el-icon class="text-primary text-4xl mb-4">
          <User />
        </el-icon>
        <h3 class="text-white text-lg font-medium mb-2">
          用户查询
        </h3>
        <p class="text-gray-400 text-sm">
          查看用户信息和作品列表
        </p>
      </div>
      <div
        class="entry-card p-6 rounded-xl bg-dark-card cursor-pointer hover:bg-dark-lighter transition-colors"
        @click="goToSearch"
      >
        <el-icon class="text-primary text-4xl mb-4">
          <Search />
        </el-icon>
        <h3 class="text-white text-lg font-medium mb-2">
          搜索
        </h3>
        <p class="text-gray-400 text-sm">
          搜索视频、用户、直播
        </p>
      </div>
    </div>

    <!-- 功能说明 -->
    <div class="info-section p-6 rounded-xl bg-dark-card">
      <h2 class="text-xl font-bold text-white mb-4">
        使用说明
      </h2>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-gray-400">
        <div class="flex items-start gap-3">
          <el-icon class="text-primary text-xl mt-1">
            <VideoPlay />
          </el-icon>
          <div>
            <h3 class="text-white font-medium mb-1">
              作品查询
            </h3>
            <p class="text-sm">
              粘贴抖音视频分享链接，获取视频详情、评论列表，支持无水印下载
            </p>
          </div>
        </div>
        <div class="flex items-start gap-3">
          <el-icon class="text-primary text-xl mt-1">
            <User />
          </el-icon>
          <div>
            <h3 class="text-white font-medium mb-1">
              用户查询
            </h3>
            <p class="text-sm">
              输入用户主页链接，查看用户资料和作品列表
            </p>
          </div>
        </div>
        <div class="flex items-start gap-3">
          <el-icon class="text-primary text-xl mt-1">
            <Search />
          </el-icon>
          <div>
            <h3 class="text-white font-medium mb-1">
              搜索功能
            </h3>
            <p class="text-sm">
              搜索抖音视频、用户、直播内容
            </p>
          </div>
        </div>
        <div class="flex items-start gap-3">
          <el-icon class="text-primary text-xl mt-1">
            <VideoPlay />
          </el-icon>
          <div>
            <h3 class="text-white font-medium mb-1">
              直播查询
            </h3>
            <p class="text-sm">
              获取直播间信息和实时数据
            </p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.status-bar {
  border: 1px solid rgba(var(--app-border-rgb) / 0.5);
  box-shadow:
    0 1px 2px rgba(var(--app-shadow-rgb) / 0.04),
    0 4px 12px rgba(var(--app-shadow-rgb) / 0.06);
}

.entry-card {
  border: 1px solid rgba(var(--app-border-rgb) / 0.5);
  box-shadow:
    0 1px 2px rgba(var(--app-shadow-rgb) / 0.04),
    0 4px 12px rgba(var(--app-shadow-rgb) / 0.06);
  transition: all 0.25s ease;
}

.entry-card:hover {
  transform: translateY(-2px);
  box-shadow:
    0 4px 12px rgba(var(--app-shadow-rgb) / 0.08),
    0 12px 28px rgba(var(--app-shadow-rgb) / 0.08);
}

.info-section {
  border: 1px solid rgba(var(--app-border-rgb) / 0.5);
  box-shadow:
    0 1px 2px rgba(var(--app-shadow-rgb) / 0.04),
    0 4px 12px rgba(var(--app-shadow-rgb) / 0.06);
}
</style>
