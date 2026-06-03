<script setup lang="ts">
import { ref } from 'vue'
import { Search, Star } from '@element-plus/icons-vue'
import { searchVideos, searchUsers, searchLive } from '@/api'
import type { SearchVideo, SearchUser, SearchLive } from '@/api/modules/search'
import { useNotification } from '@/composables'
import { useSearchStore } from '@/stores'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import EmptyState from '@/components/common/EmptyState.vue'

const { error } = useNotification()
const searchStore = useSearchStore()

const keyword = ref('')
const activeType = ref('video')
const loading = ref(false)

const videoResults = ref<SearchVideo[]>([])
const userResults = ref<SearchUser[]>([])
const liveResults = ref<SearchLive[]>([])

async function handleSearch() {
  if (!keyword.value.trim()) {
    error('请输入搜索关键词')
    return
  }

  searchStore.addHistory(keyword.value)
  loading.value = true
  
  try {
    if (activeType.value === 'video') {
      const res = await searchVideos({ keyword: keyword.value, count: 50 })
      videoResults.value = res.data.items || res.data.data || []
    } else if (activeType.value === 'user') {
      const res = await searchUsers({ keyword: keyword.value, count: 30 })
      userResults.value = res.data.items || res.data.data || []
    } else if (activeType.value === 'live') {
      const res = await searchLive({ keyword: keyword.value, count: 20 })
      liveResults.value = res.data.items || res.data.data || []
    }
  } catch (err: any) {
    console.error('搜索失败:', err)
    const errorMsg = err?.message || err?.toString() || '搜索失败，请稍后重试'
    error(errorMsg)
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
</script>

<template>
  <div class="search-page">
    <!-- 搜索框 -->
    <div class="search-box mb-6">
      <div class="flex gap-4 mb-4">
        <el-radio-group
          v-model="activeType"
          size="large"
        >
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
      <div class="flex gap-4">
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

    <!-- 搜索结果 -->
    <template v-if="keyword">
      <!-- 视频结果 -->
      <div
        v-if="activeType === 'video'"
        class="video-results"
      >
        <div
          v-if="videoResults.length > 0"
          class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4"
        >
          <div
            v-for="video in videoResults"
            :key="video.aweme_id"
            class="video-card group relative rounded-xl overflow-hidden bg-dark-card cursor-pointer hover:scale-[1.02] transition-all"
          >
            <div class="aspect-[9/16] relative">
              <img
                :src="video.cover"
                :alt="video.desc"
                class="w-full h-full object-cover"
                loading="lazy"
              >
              <div class="absolute bottom-2 left-2 flex items-center gap-3 text-white text-xs">
                <span class="flex items-center gap-1">
                  <el-icon><Star /></el-icon>
                  {{ video.digg_count }}
                </span>
              </div>
            </div>
            <div class="p-3">
              <p class="text-white text-sm line-clamp-2 mb-2">
                {{ video.desc }}
              </p>
              <span class="text-gray-400 text-xs">{{ video.author }}</span>
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
            class="user-card flex items-center gap-4 p-4 rounded-xl bg-dark-card cursor-pointer hover:bg-dark-lighter"
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
                {{ user.follower_count }} 粉丝
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
            class="live-card rounded-xl overflow-hidden bg-dark-card cursor-pointer"
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
              <span class="text-gray-400 text-xs">{{ live.author_nickname }}</span>
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
  </div>
</template>
