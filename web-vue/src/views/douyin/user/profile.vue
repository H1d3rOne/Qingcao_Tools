<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowRight } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores'
import { usePagination } from '@/composables'
import { useDownload } from '@/composables'
import { formatNumber } from '@/utils/format'
import VideoCard from '@/components/business/VideoCard.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import type { Video } from '@/types/api'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const { download } = useDownload()

const activeTab = ref('videos')

const { 
  list: videos, 
  loading: videosLoading, 
  hasMore: videosHasMore,
  isEmpty: videosEmpty,
  loadMore: loadVideos, 
  reset: resetVideos 
} = usePagination<Video, { sec_uid: string; cursor?: number; count?: number }>({
  fetchFn: async (params) => ({
    data: await userStore.fetchUserVideos(params.sec_uid, params.cursor) || { data: [], has_more: false, cursor: 0 }
  })
})

const secUid = computed(() => route.params.id as string)
const avatarUrl = computed(() => userStore.currentUser?.avatar)

onMounted(async () => {
  // console.log('[Profile] onMounted, secUid:', secUid.value)
  if (secUid.value) {
    await userStore.fetchUserInfo(secUid.value)
    // console.log('[Profile] currentUser after fetch:', userStore.currentUser)
    await loadVideos({ sec_uid: secUid.value })
  }
})

watch(secUid, async (newSecUid) => {
  if (newSecUid) {
    userStore.clearCurrentUser()
    resetVideos()
    await userStore.fetchUserInfo(newSecUid)
    await loadVideos({ sec_uid: newSecUid })
  }
})

async function handleLoadMore() {
  if (secUid.value) {
    await loadVideos({ sec_uid: secUid.value })
  }
}

function handleVideoClick(video: Video) {
  router.push(`/video/${video.aweme_id}`)
}

function handleVideoDownload(video: Video) {
  return download(video.aweme_id)
}
</script>

<template>
  <div class="user-profile-page">
    <!-- 加载中 -->
    <LoadingSpinner v-if="userStore.loading" />

    <template v-else-if="userStore.currentUser">
      <!-- 用户信息卡片 -->
      <div class="user-card">
        <div class="user-card-content">
          <!-- 头像 -->
          <img
            v-if="avatarUrl"
            :src="avatarUrl"
            class="user-avatar"
          >

          <!-- 基本信息 -->
          <div class="user-details">
            <div class="user-header">
              <span class="user-nickname">{{ userStore.currentUser.nickname }}</span>
              <el-tag
                v-if="userStore.currentUser.is_verify"
                type="success"
                size="small"
              >
                已认证
              </el-tag>
            </div>

            <div class="user-ids">
              <span
                v-if="userStore.currentUser.unique_id"
                class="id-item"
              >
                抖音号：{{ userStore.currentUser.unique_id }}
              </span>
              <span
                v-if="userStore.currentUser.short_id"
                class="id-item"
              >
                ID：{{ userStore.currentUser.short_id }}
              </span>
            </div>

            <!-- 额外信息 -->
            <div class="extra-info">
              <div
                v-if="userStore.currentUser.gender"
                class="info-item"
              >
                <span class="info-label">性别：</span>
                <el-tag
                  :type="userStore.currentUser.gender === 1 ? 'success' : 'danger'"
                  size="small"
                >
                  {{ userStore.currentUser.gender === 1 ? '男' : '女' }}
                </el-tag>
              </div>
              <div
                v-if="userStore.currentUser.user_age"
                class="info-item"
              >
                <span class="info-label">年龄：</span>
                <span class="info-value">{{ userStore.currentUser.user_age }}岁</span>
              </div>
              <div
                v-if="userStore.currentUser.ip_location"
                class="info-item"
              >
                <span class="info-label">IP位置：</span>
                <span class="info-value">{{ userStore.currentUser.ip_location }}</span>
              </div>
              <div
                v-if="userStore.currentUser.country"
                class="info-item"
              >
                <span class="info-label">国家/地区：</span>
                <span class="info-value">{{ userStore.currentUser.country }}</span>
              </div>
            </div>

            <!-- 统计数据 -->
            <div class="stats-row">
              <div class="stat-item">
                <span class="stat-value">{{ formatNumber(userStore.currentUser.follower_count) }}</span>
                <span class="stat-label">粉丝</span>
              </div>
              <div class="stat-divider" />
              <div class="stat-item">
                <span class="stat-value">{{ formatNumber(userStore.currentUser.following_count) }}</span>
                <span class="stat-label">关注</span>
              </div>
              <div class="stat-divider" />
              <div class="stat-item">
                <span class="stat-value">{{ formatNumber(userStore.currentUser.aweme_count) }}</span>
                <span class="stat-label">作品</span>
              </div>
              <div class="stat-divider" />
              <div class="stat-item">
                <span class="stat-value">{{ formatNumber(userStore.currentUser.favoriting_count) }}</span>
                <span class="stat-label">获赞</span>
              </div>
            </div>

            <!-- 签名 -->
            <p
              v-if="userStore.currentUser.signature"
              class="signature-text"
            >
              {{ userStore.currentUser.signature }}
            </p>
          </div>
        </div>
      </div>

      <!-- 标签页 -->
      <div class="tabs-section">
        <el-tabs v-model="activeTab">
          <el-tab-pane
            label="作品"
            name="videos"
          >
            <div
              v-if="!videosEmpty"
              class="video-grid"
            >
              <VideoCard
                v-for="video in videos"
                :key="video.aweme_id"
                :video="video"
                @click="handleVideoClick"
                @download="handleVideoDownload"
              />
            </div>

            <EmptyState
              v-else-if="!videosLoading"
              text="暂无作品"
            />

            <LoadingSpinner
              v-if="videosLoading"
              size="small"
            />

            <div
              v-if="videosHasMore && videos.length > 0"
              class="load-more"
            >
              <el-button
                type="primary"
                plain
                @click="handleLoadMore"
              >
                加载更多
              </el-button>
            </div>
          </el-tab-pane>

          <el-tab-pane
            label="喜欢"
            name="likes"
          >
            <EmptyState text="暂不支持查看喜欢列表" />
          </el-tab-pane>
        </el-tabs>
      </div>
    </template>

    <EmptyState
      v-else
      text="用户不存在或已封禁"
    />
  </div>
</template>

<style scoped>
.user-profile-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.user-card {
  padding: 28px;
  border-radius: 16px;
  background: rgba(var(--app-surface-rgb) / 0.95);
  border: 1.5px solid rgba(var(--app-border-rgb) / 0.7);
  box-shadow: 0 8px 24px rgba(var(--app-shadow-rgb) / 0.08);
}

.user-card-content {
  display: flex;
  align-items: flex-start;
  gap: 28px;
}

.user-avatar {
  width: 96px;
  height: 96px;
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
  font-size: 24px;
  font-weight: 700;
  color: rgb(var(--app-text-strong-rgb));
}

.user-ids {
  display: flex;
  align-items: center;
  gap: 20px;
}

.id-item {
  font-size: 13px;
  color: rgb(var(--app-text-muted-rgb));
  padding: 6px 14px;
  border-radius: 20px;
  background: rgba(var(--app-surface-alt-rgb) / 0.8);
  border: 1px solid rgba(var(--app-border-rgb) / 0.5);
}

.extra-info {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  padding: 14px 16px;
  background: rgba(var(--app-surface-alt-rgb) / 0.92);
  border-radius: 12px;
  border: 1px solid rgba(var(--app-border-rgb) / 0.5);
}

.info-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.info-label {
  font-size: 13px;
  color: rgb(var(--app-text-muted-rgb));
}

.info-value {
  font-size: 14px;
  color: rgb(var(--app-text-strong-rgb));
  font-weight: 500;
}

.stats-row {
  display: flex;
  align-items: center;
  gap: 0;
  padding: 16px 20px;
  background: rgba(var(--app-surface-alt-rgb) / 0.7);
  border-radius: 12px;
  border: 1px solid rgba(var(--app-border-rgb) / 0.35);
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
  height: 36px;
  background: rgba(var(--app-border-rgb) / 0.4);
}

.stat-value {
  font-size: 20px;
  font-weight: 700;
  color: rgb(var(--app-text-strong-rgb));
}

.stat-label {
  font-size: 12px;
  color: rgb(var(--app-text-muted-rgb));
}

.signature-text {
  padding: 14px 16px;
  background: rgba(var(--app-surface-alt-rgb) / 0.92);
  border-radius: 12px;
  border: 1px solid rgba(var(--app-border-rgb) / 0.5);
  color: rgb(var(--app-text-rgb));
  font-size: 14px;
  line-height: 1.7;
}

.tabs-section {
  padding: 20px;
  border-radius: 16px;
  border: 1px solid rgba(var(--app-border-rgb) / 0.52);
  background: rgba(var(--app-surface-rgb) / 0.92);
  box-shadow: 0 8px 24px rgba(var(--app-shadow-rgb) / 0.06);
}

.video-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
  padding-top: 16px;
}

.load-more {
  margin-top: 20px;
  text-align: center;
}
</style>
