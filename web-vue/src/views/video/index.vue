<script setup lang="ts">
import { ref } from 'vue'
import { getWorkInfo, getWorkComments, downloadWork } from '@/api'
import type { WorkInfo, Comment } from '@/api/modules/video'
import { useNotification } from '@/composables'

const { error, success } = useNotification()

const inputUrl = ref('')
const loading = ref(false)
const workInfo = ref<WorkInfo | null>(null)
const comments = ref<Comment[]>([])
const commentsLoading = ref(false)
const downloading = ref(false)
const activeTab = ref('info')

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
    success('查询成功')
    
    // 自动加载评论
    loadComments()
  } catch (err) {
    console.error('查询失败:', err)
  } finally {
    loading.value = false
  }
}

async function loadComments() {
  if (!inputUrl.value.trim()) return
  
  commentsLoading.value = true
  try {
    const res = await getWorkComments(inputUrl.value.trim(), 50)
    comments.value = res.data || []
  } catch (err) {
    console.error('获取评论失败:', err)
  } finally {
    commentsLoading.value = false
  }
}

async function handleDownload() {
  if (!inputUrl.value.trim()) return
  
  downloading.value = true
  try {
    await downloadWork(inputUrl.value.trim(), 'media')
    success('下载成功')
  } catch (err) {
    error('下载失败')
  } finally {
    downloading.value = false
  }
}

function handlePaste() {
  navigator.clipboard.readText().then(text => {
    inputUrl.value = text
  })
}

function formatTime(timestamp: number) {
  return new Date(timestamp * 1000).toLocaleString('zh-CN')
}
</script>

<template>
  <div class="video-page max-w-6xl mx-auto">
    <div class="mb-8">
      <h2 class="text-2xl font-bold text-white mb-2">
        作品查询
      </h2>
      <p class="text-gray-400">
        输入抖音视频链接，获取视频详细信息、评论和下载
      </p>
    </div>

    <!-- 搜索框 -->
    <div class="search-box p-6 rounded-xl bg-dark-card mb-6">
      <div class="flex gap-4">
        <el-input
          v-model="inputUrl"
          placeholder="请输入抖音视频链接（如：https://v.douyin.com/xxx）"
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
    </div>

    <!-- 查询结果 -->
    <template v-if="workInfo">
      <div class="flex flex-col lg:flex-row gap-6">
        <!-- 左侧：视频预览 -->
        <div class="lg:w-1/2">
          <div class="video-preview aspect-video rounded-xl overflow-hidden bg-dark-card relative">
            <video
              v-if="workInfo.video_url"
              :src="workInfo.video_url"
              :poster="workInfo.cover"
              controls
              class="w-full h-full object-contain"
            />
            <img
              v-else
              :src="workInfo.cover"
              class="w-full h-full object-cover"
            >
          </div>

          <!-- 操作按钮 -->
          <div class="flex items-center gap-4 mt-4">
            <el-button
              type="primary"
              :loading="downloading"
              @click="handleDownload"
            >
              <el-icon class="mr-1">
                <Download />
              </el-icon>
              下载视频
            </el-button>
          </div>
        </div>

        <!-- 右侧：信息 -->
        <div class="lg:w-1/2">
          <!-- 标签页 -->
          <el-tabs v-model="activeTab">
            <!-- 视频信息 -->
            <el-tab-pane
              label="视频信息"
              name="info"
            >
              <div class="space-y-4 p-4 rounded-xl bg-dark-card">
                <div>
                  <div class="text-gray-400 text-sm mb-1">
                    标题
                  </div>
                  <p class="text-white">
                    {{ workInfo.title }}
                  </p>
                </div>
                
                <div>
                  <div class="text-gray-400 text-sm mb-1">
                    描述
                  </div>
                  <p class="text-white">
                    {{ workInfo.desc }}
                  </p>
                </div>
                
                <div>
                  <div class="text-gray-400 text-sm mb-1">
                    作者
                  </div>
                  <p class="text-white">
                    {{ workInfo.author_nickname }}
                  </p>
                </div>
                
                <div class="grid grid-cols-2 gap-4">
                  <div>
                    <div class="text-gray-400 text-sm">
                      发布时间
                    </div>
                    <div class="text-white">
                      {{ formatTime(workInfo.create_time) }}
                    </div>
                  </div>
                  <div v-if="workInfo.duration">
                    <div class="text-gray-400 text-sm">
                      时长
                    </div>
                    <div class="text-white">
                      {{ workInfo.duration }}秒
                    </div>
                  </div>
                </div>

                <div class="grid grid-cols-4 gap-4 text-center">
                  <div class="p-3 rounded-lg bg-dark-lighter">
                    <div class="text-white font-medium">
                      {{ workInfo.play_count }}
                    </div>
                    <div class="text-gray-400 text-xs">
                      播放
                    </div>
                  </div>
                  <div class="p-3 rounded-lg bg-dark-lighter">
                    <div class="text-white font-medium">
                      {{ workInfo.digg_count }}
                    </div>
                    <div class="text-gray-400 text-xs">
                      点赞
                    </div>
                  </div>
                  <div class="p-3 rounded-lg bg-dark-lighter">
                    <div class="text-white font-medium">
                      {{ workInfo.comment_count }}
                    </div>
                    <div class="text-gray-400 text-xs">
                      评论
                    </div>
                  </div>
                  <div class="p-3 rounded-lg bg-dark-lighter">
                    <div class="text-white font-medium">
                      {{ workInfo.share_count }}
                    </div>
                    <div class="text-gray-400 text-xs">
                      分享
                    </div>
                  </div>
                </div>
              </div>
            </el-tab-pane>

            <!-- 评论列表 -->
            <el-tab-pane
              :label="`评论 (${comments.length})`"
              name="comments"
            >
              <div class="comments space-y-2 max-h-[500px] overflow-auto">
                <div
                  v-for="comment in comments"
                  :key="comment.cid"
                  class="flex gap-3 p-4 rounded-lg bg-dark-card/50"
                >
                  <img
                    v-if="comment.user?.avatar"
                    :src="comment.user.avatar"
                    class="w-10 h-10 rounded-full object-cover flex-shrink-0"
                  >
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2">
                      <span class="text-white text-sm font-medium">{{ comment.user?.nickname }}</span>
                    </div>
                    <p class="text-gray-300 text-sm mt-1 leading-relaxed">
                      {{ comment.text }}
                    </p>
                    <div class="flex items-center gap-4 mt-2 text-xs text-gray-400">
                      <span class="flex items-center gap-1">
                        <el-icon><Star /></el-icon>
                        {{ comment.digg_count || 0 }}
                      </span>
                    </div>
                  </div>
                </div>

                <EmptyState
                  v-if="comments.length === 0 && !commentsLoading"
                  text="暂无评论"
                />
              </div>
            </el-tab-pane>
          </el-tabs>
        </div>
      </div>
    </template>

    <!-- 功能说明 -->
    <div
      v-if="!workInfo"
      class="mt-8 grid grid-cols-1 md:grid-cols-3 gap-6"
    >
      <div class="feature-card p-6 rounded-xl bg-dark-card">
        <el-icon class="text-primary text-3xl mb-4">
          <VideoPlay />
        </el-icon>
        <h3 class="text-white font-medium mb-2">
          视频信息
        </h3>
        <p class="text-gray-400 text-sm">
          获取视频详细信息，包括播放量、点赞数、评论等
        </p>
      </div>
      <div class="feature-card p-6 rounded-xl bg-dark-card">
        <el-icon class="text-primary text-3xl mb-4">
          <ChatDotRound />
        </el-icon>
        <h3 class="text-white font-medium mb-2">
          评论分析
        </h3>
        <p class="text-gray-400 text-sm">
          查看视频评论，了解用户互动情况
        </p>
      </div>
      <div class="feature-card p-6 rounded-xl bg-dark-card">
        <el-icon class="text-primary text-3xl mb-4">
          <Download />
        </el-icon>
        <h3 class="text-white font-medium mb-2">
          视频下载
        </h3>
        <p class="text-gray-400 text-sm">
          无水印下载视频，保存精彩内容
        </p>
      </div>
    </div>
  </div>
</template>
