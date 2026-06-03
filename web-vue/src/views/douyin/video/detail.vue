<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Download, Refresh, ArrowRight, Star, ChatDotRound, ArrowLeft } from '@element-plus/icons-vue'
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

function goBack() {
  // 使用 router.back() 返回上一页，不会刷新
  router.back()
}

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

// 计算属性 - 使用代理URL
const coverUrl = computed(() => {
  const video = videoStore.currentVideo
  if (!video) return ''
  return video.cover_url || (typeof video.cover === 'string' ? video.cover : video.cover?.url_list?.[0]) || ''
})

const videoUrl = computed(() => {
  const video = videoStore.currentVideo
  if (!video || !video.video_url) return ''
  return getProxyVideoUrl(video.video_url)
})

const authorAvatar = computed(() => {
  const video = videoStore.currentVideo
  if (!video) return ''
  return video.author_avatar || video.author?.avatar || ''
})

function getProxyVideoUrl(url: string | undefined): string {
  if (!url) return ''
  return `/api/v1/douyin/work/proxy?url=${encodeURIComponent(url)}`
}

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
  if (videoStore.currentVideo?.author_sec_uid || videoStore.currentVideo?.author?.sec_uid) {
    const secUid = videoStore.currentVideo.author_sec_uid || videoStore.currentVideo.author?.sec_uid
    router.push(`/douyin/user/${secUid}`)
  }
}
</script>

<template>
  <div class="video-detail">
    <div class="mb-4">
      <el-button plain @click="goBack">
        <el-icon class="mr-1"><ArrowLeft /></el-icon>
        返回
      </el-button>
    </div>

    <LoadingSpinner v-if="videoStore.loading" />

    <template v-else-if="videoStore.currentVideo">
      <div class="detail-layout">
        <div class="detail-left">
          <div class="video-preview">
            <video v-if="videoUrl" :src="videoUrl" :poster="coverUrl" controls class="preview-media" />
            <img v-else :src="coverUrl" class="preview-media preview-cover" />
          </div>
          <div class="detail-actions">
            <el-button type="primary" :loading="downloading" @click="handleDownload">
              <el-icon class="mr-1"><Download /></el-icon>
              下载视频
            </el-button>
            <el-button plain @click="videoStore.fetchVideoInfo(awemeId)">
              <el-icon class="mr-1"><Refresh /></el-icon>
              刷新
            </el-button>
          </div>
        </div>

        <div class="detail-right">
          <div class="author-card" @click="goToUser">
            <img v-if="authorAvatar" :src="authorAvatar" class="author-avatar" />
            <div class="author-meta">
              <div class="author-name">{{ videoStore.currentVideo.author?.nickname }}</div>
              <div class="author-fans">{{ formatNumber(videoStore.currentVideo.author?.follower_count) }} 粉丝</div>
            </div>
            <el-icon class="author-arrow"><ArrowRight /></el-icon>
          </div>

          <el-tabs v-model="activeTab" class="detail-tabs">
            <el-tab-pane label="视频信息" name="info">
              <div class="info-panel">
                <div class="info-section">
                  <div class="info-label">描述</div>
                  <p class="info-desc">{{ videoStore.currentVideo.desc }}</p>
                </div>

                <div class="info-grid-2">
                  <div>
                    <div class="info-label">发布时间</div>
                    <div class="info-value">{{ formatTime(videoStore.currentVideo.create_time) }}</div>
                  </div>
                  <div v-if="videoStore.currentVideo.video?.duration">
                    <div class="info-label">时长</div>
                    <div class="info-value">{{ formatDuration(videoStore.currentVideo.video.duration) }}</div>
                  </div>
                </div>

                <div class="stats-grid">
                  <div class="stat-cell">
                    <div class="stat-num">{{ formatNumber(videoStore.currentVideo.statistics?.play_count) }}</div>
                    <div class="stat-label">播放</div>
                  </div>
                  <div class="stat-cell">
                    <div class="stat-num">{{ formatNumber(videoStore.currentVideo.statistics?.digg_count) }}</div>
                    <div class="stat-label">点赞</div>
                  </div>
                  <div class="stat-cell">
                    <div class="stat-num">{{ formatNumber(videoStore.currentVideo.statistics?.comment_count) }}</div>
                    <div class="stat-label">评论</div>
                  </div>
                  <div class="stat-cell">
                    <div class="stat-num">{{ formatNumber(videoStore.currentVideo.statistics?.share_count) }}</div>
                    <div class="stat-label">分享</div>
                  </div>
                </div>
              </div>
            </el-tab-pane>

            <el-tab-pane :label="`评论 (${videoStore.currentVideo.statistics?.comment_count || 0})`" name="comments">
              <div class="comments space-y-2">
                <CommentItem v-for="comment in videoStore.comments" :key="comment.cid" :comment="comment" />
                <EmptyState v-if="videoStore.comments.length === 0 && !videoStore.commentsLoading" text="暂无评论" />
                <LoadingSpinner v-if="videoStore.commentsLoading" size="small" />
                <div v-if="videoStore.commentsHasMore && videoStore.comments.length > 0" class="text-center mt-4">
                  <el-button plain size="small" @click="loadMoreComments">加载更多评论</el-button>
                </div>
              </div>
            </el-tab-pane>
          </el-tabs>
        </div>
      </div>
    </template>

    <EmptyState v-else text="视频不存在或已删除" />
  </div>
</template>

<style scoped>
.detail-layout {
  display: flex;
  gap: 24px;
}

.detail-left {
  width: 50%;
  flex-shrink: 0;
}

.video-preview {
  aspect-ratio: 9 / 16;
  border-radius: 14px;
  overflow: hidden;
  background: rgb(var(--app-surface-rgb));
  border: 1px solid rgba(var(--app-border-rgb) / 0.7);
}

.preview-media {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.preview-cover {
  object-fit: cover;
}

.detail-actions {
  display: flex;
  gap: 12px;
  margin-top: 14px;
}

.detail-right {
  flex: 1;
  min-width: 0;
}

.author-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
  border-radius: 12px;
  background: rgba(var(--app-surface-rgb) / 0.92);
  border: 1px solid rgba(var(--app-border-rgb) / 0.7);
  cursor: pointer;
  transition: all 0.2s ease;
}

.author-card:hover {
  border-color: rgba(var(--primary-color-rgb) / 0.3);
  background: rgba(var(--app-surface-alt-rgb) / 0.92);
}

.author-avatar {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  object-fit: cover;
}

.author-name {
  font-size: 15px;
  font-weight: 600;
  color: rgb(var(--app-text-strong-rgb));
}

.author-fans {
  font-size: 12px;
  color: rgb(var(--app-text-muted-rgb));
  margin-top: 2px;
}

.author-arrow {
  margin-left: auto;
  color: rgb(var(--app-text-subtle-rgb));
}

.info-panel {
  padding: 16px;
  border-radius: 12px;
  background: rgba(var(--app-surface-rgb) / 0.92);
  border: 1px solid rgba(var(--app-border-rgb) / 0.7);
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.info-label {
  font-size: 12px;
  color: rgb(var(--app-text-muted-rgb));
  margin-bottom: 4px;
}

.info-desc {
  font-size: 14px;
  color: rgb(var(--app-text-strong-rgb));
  line-height: 1.6;
  margin: 0;
}

.info-value {
  font-size: 14px;
  color: rgb(var(--app-text-strong-rgb));
}

.info-grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
}

.stat-cell {
  padding: 12px 8px;
  border-radius: 10px;
  background: rgba(var(--app-surface-alt-rgb) / 0.92);
  text-align: center;
}

.stat-num {
  font-size: 15px;
  font-weight: 600;
  color: rgb(var(--app-text-strong-rgb));
}

.stat-label {
  font-size: 11px;
  color: rgb(var(--app-text-muted-rgb));
  margin-top: 2px;
}

@media (max-width: 1024px) {
  .detail-layout {
    flex-direction: column;
  }

  .detail-left {
    width: 100%;
  }
}
</style>
