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
} = usePagination<Video, { sec_uid: string }>({
  fetchFn: (params) => userStore.fetchUserVideos(params.sec_uid, params.cursor, params.count)
})

const secUid = computed(() => route.params.id as string)
const avatarUrl = computed(() => userStore.currentUser?.avatar)

onMounted(async () => {
  if (secUid.value) {
    await userStore.fetchUserInfo(secUid.value)
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
</script>

<template>
  <div class="user-profile">
    <!-- 加载中 -->
    <LoadingSpinner v-if="userStore.loading" />

    <template v-else-if="userStore.currentUser">
      <!-- 用户信息卡片 -->
      <div class="user-card p-6 rounded-xl bg-dark-card mb-6">
        <div class="flex items-start gap-6">
          <!-- 头像 -->
          <img
            v-if="avatarUrl"
            :src="avatarUrl"
            class="w-24 h-24 rounded-full object-cover"
          >
          
          <!-- 信息 -->
          <div class="flex-1">
            <div class="flex items-center gap-3 mb-2">
              <span class="text-2xl font-bold text-white">{{ userStore.currentUser.nickname }}</span>
              <el-tag
                v-if="userStore.currentUser.is_verify"
                type="success"
                size="small"
              >
                已认证
              </el-tag>
            </div>
            
            <div class="text-gray-400 text-sm mb-4">
              <span
                v-if="userStore.currentUser.unique_id"
                class="mr-4"
              >
                抖音号：{{ userStore.currentUser.unique_id }}
              </span>
              <span v-if="userStore.currentUser.short_id">
                ID：{{ userStore.currentUser.short_id }}
              </span>
            </div>
            
            <!-- 性别、年龄、IP位置、国家 -->
            <div class="flex items-center gap-4 text-sm text-gray-400 mb-4">
              <span
                v-if="userStore.currentUser.gender !== undefined"
                class="flex items-center gap-1"
              >
                <span v-if="userStore.currentUser.gender === 1">👨 男</span>
                <span v-else-if="userStore.currentUser.gender === 2">👩 女</span>
                <span v-else> gender: {{ userStore.currentUser.gender }}</span>
              </span>
              <span v-if="userStore.currentUser.user_age">🎂 {{ userStore.currentUser.user_age }}岁</span>
              <span v-if="userStore.currentUser.ip_location">📍 {{ userStore.currentUser.ip_location }}</span>
              <span v-if="userStore.currentUser.country">🌍 {{ userStore.currentUser.country }}</span>
            </div>
            
            <p
              v-if="userStore.currentUser.signature"
              class="text-gray-300 mb-4"
            >
              {{ userStore.currentUser.signature }}
            </p>
            
            <div class="flex items-center gap-8">
              <div>
                <span class="text-white font-medium">{{ formatNumber(userStore.currentUser.follower_count) }}</span>
                <span class="text-gray-400 ml-1">粉丝</span>
              </div>
              <div>
                <span class="text-white font-medium">{{ formatNumber(userStore.currentUser.following_count) }}</span>
                <span class="text-gray-400 ml-1">关注</span>
              </div>
              <div>
                <span class="text-white font-medium">{{ formatNumber(userStore.currentUser.aweme_count) }}</span>
                <span class="text-gray-400 ml-1">作品</span>
              </div>
              <div>
                <span class="text-white font-medium">{{ formatNumber(userStore.currentUser.favoriting_count) }}</span>
                <span class="text-gray-400 ml-1">获赞</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 标签页 -->
      <el-tabs v-model="activeTab">
        <el-tab-pane
          label="作品"
          name="videos"
        >
          <div
            v-if="!videosEmpty"
            class="video-grid grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4"
          >
            <VideoCard
              v-for="video in videos"
              :key="video.aweme_id"
              :video="video"
              @click="handleVideoClick"
              @download="download"
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
            class="mt-6 text-center"
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
    </template>

    <EmptyState
      v-else
      text="用户不存在或已封禁"
    />
  </div>
</template>
