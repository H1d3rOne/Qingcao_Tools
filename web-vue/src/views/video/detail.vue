<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Download, Refresh, ArrowRight, Star, ChatDotRound } from '@element-plus/icons-vue'
import { useVideoStore } from '@/stores'
import { useDownload } from '@/composables'
import { formatNumber, formatTime, formatDuration } from '@/utils/format'
import CommentItem from '@/components/business/CommentItem.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import EmptyState from '@/components/common/EmptyState.vue'

const route = useRoute()
const router = useRouter()
const videoStore = useVideoStore()
const { download, downloading } = useDownload()

const activeTab = ref('info')
const commentInput = ref('')

const awemeId = route.params.id as string

onMounted(async () => {
  if (awemeId) {
    await videoStore.fetchVideoInfo(awemeId)
    await videoStore.fetchComments(awemeId)
  }
})

watch(() => route.params.id, async (newId) => {
  if (newId) {
    videoStore.clearCurrentVideo()
    await videoStore.fetchVideoInfo(newId as string)
    await videoStore.fetchComments(newId as string)
  }
})

const coverUrl = ref('')
const videoUrl = ref('')
const authorAvatar = ref('')

watch(() => videoStore.currentVideo, (video) => {
  if (video) {
    coverUrl.value = video.cover?.url_list?.[0] || ''
    videoUrl.value = video.video?.play_addr?.url_list?.[0] || ''
    authorAvatar.value = video.author?.avatar || ''
  }
}, { immediate: true })

function handleDownload() {
  if (videoStore.currentVideo) {
    download(videoStore.currentVideo.aweme_id)
  }
}

async function loadMoreComments() {
  if (awemeId && videoStore.commentsHasMore) {
    await videoStore.fetchComments(awemeId, videoStore.commentsCursor, true)
  }
}

function goToUser() {
  if (videoStore.currentVideo?.author?.sec_uid) {
    router.push(`/user/${videoStore.currentVideo.author.sec_uid}`)
  }
}
</script>

<template>
  <div class="video-detail">
    <!-- 加载中 -->
    <LoadingSpinner v-if="videoStore.loading" />

    <template v-else-if="videoStore.currentVideo">
      <div class="flex flex-col lg:flex-row gap-6">
        <!-- 左侧：视频预览 -->
        <div class="lg:w-1/2">
          <div class="video-preview aspect-[9/16] rounded-xl overflow-hidden bg-dark-card relative">
            <video
              v-if="videoUrl"
              :src="videoUrl"
              :poster="coverUrl"
              controls
              class="w-full h-full object-contain"
            />
            <img
              v-else
              :src="coverUrl"
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
            <el-button
              plain
              @click="videoStore.fetchVideoInfo(awemeId)"
            >
              <el-icon class="mr-1">
                <Refresh />
              </el-icon>
              刷新
            </el-button>
          </div>
        </div>

        <!-- 右侧：信息 -->
        <div class="lg:w-1/2">
          <!-- 作者信息 -->
          <div
            class="author-info flex items-center gap-4 p-4 rounded-xl bg-dark-card cursor-pointer hover:bg-dark-lighter transition-colors"
            @click="goToUser"
          >
            <img
              v-if="authorAvatar"
              :src="authorAvatar"
              class="w-12 h-12 rounded-full object-cover"
            >
            <div class="flex-1">
              <div class="text-white font-medium">
                {{ videoStore.currentVideo.author?.nickname }}
              </div>
              <div class="text-gray-400 text-sm">
                {{ formatNumber(videoStore.currentVideo.author?.follower_count) }} 粉丝
              </div>
            </div>
            <el-icon class="text-gray-400">
              <ArrowRight />
            </el-icon>
          </div>

          <!-- 标签页 -->
          <el-tabs
            v-model="activeTab"
            class="mt-4"
          >
            <!-- 视频信息 -->
            <el-tab-pane
              label="视频信息"
              name="info"
            >
              <div class="space-y-4 p-4 rounded-xl bg-dark-card">
                <div>
                  <div class="text-gray-400 text-sm mb-1">
                    描述
                  </div>
                  <p class="text-white">
                    {{ videoStore.currentVideo.desc }}
                  </p>
                </div>
                
                <div class="grid grid-cols-2 gap-4">
                  <div>
                    <div class="text-gray-400 text-sm">
                      发布时间
                    </div>
                    <div class="text-white">
                      {{ formatTime(videoStore.currentVideo.create_time) }}
                    </div>
                  </div>
                  <div v-if="videoStore.currentVideo.video?.duration">
                    <div class="text-gray-400 text-sm">
                      时长
                    </div>
                    <div class="text-white">
                      {{ formatDuration(videoStore.currentVideo.video.duration) }}
                    </div>
                  </div>
                </div>

                <div class="grid grid-cols-4 gap-4 text-center">
                  <div class="p-3 rounded-lg bg-dark-lighter">
                    <div class="text-white font-medium">
                      {{ formatNumber(videoStore.currentVideo.statistics?.play_count) }}
                    </div>
                    <div class="text-gray-400 text-xs">
                      播放
                    </div>
                  </div>
                  <div class="p-3 rounded-lg bg-dark-lighter">
                    <div class="text-white font-medium">
                      {{ formatNumber(videoStore.currentVideo.statistics?.digg_count) }}
                    </div>
                    <div class="text-gray-400 text-xs">
                      点赞
                    </div>
                  </div>
                  <div class="p-3 rounded-lg bg-dark-lighter">
                    <div class="text-white font-medium">
                      {{ formatNumber(videoStore.currentVideo.statistics?.comment_count) }}
                    </div>
                    <div class="text-gray-400 text-xs">
                      评论
                    </div>
                  </div>
                  <div class="p-3 rounded-lg bg-dark-lighter">
                    <div class="text-white font-medium">
                      {{ formatNumber(videoStore.currentVideo.statistics?.share_count) }}
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
              :label="`评论 (${videoStore.currentVideo.statistics?.comment_count || 0})`"
              name="comments"
            >
              <div class="comments space-y-2">
                <CommentItem
                  v-for="comment in videoStore.comments"
                  :key="comment.cid"
                  :comment="comment"
                />

                <EmptyState
                  v-if="videoStore.comments.length === 0 && !videoStore.commentsLoading"
                  text="暂无评论"
                />

                <LoadingSpinner
                  v-if="videoStore.commentsLoading"
                  size="small"
                />

                <div
                  v-if="videoStore.commentsHasMore && videoStore.comments.length > 0"
                  class="text-center mt-4"
                >
                  <el-button
                    plain
                    size="small"
                    @click="loadMoreComments"
                  >
                    加载更多评论
                  </el-button>
                </div>
              </div>
            </el-tab-pane>
          </el-tabs>
        </div>
      </div>
    </template>

    <EmptyState
      v-else
      text="视频不存在或已删除"
    />
  </div>
</template>
