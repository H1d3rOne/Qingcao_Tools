<script setup lang="ts">
import { ref } from 'vue'
import { User, DocumentCopy, Grid, Download, Star } from '@element-plus/icons-vue'
import { getUserInfo, getUserWorks } from '@/api'
import type { UserInfo, UserWork } from '@/api/modules/user'
import { useNotification } from '@/composables'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import EmptyState from '@/components/common/EmptyState.vue'

const { error, success } = useNotification()

const inputUrl = ref('')
const loading = ref(false)
const userInfo = ref<UserInfo | null>(null)
const userWorks = ref<UserWork[]>([])
const worksLoading = ref(false)

async function handleSearch() {
  if (!inputUrl.value.trim()) {
    error('请输入用户主页链接')
    return
  }

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
    console.error('查询失败:', err)
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

function handlePaste() {
  navigator.clipboard.readText().then(text => {
    inputUrl.value = text
  })
}
</script>

<template>
  <div class="user-page max-w-6xl mx-auto">
    <div class="mb-8">
      <h2 class="text-2xl font-bold text-white mb-2">
        用户查询
      </h2>
      <p class="text-gray-400">
        输入抖音用户主页链接，获取用户详细信息和作品列表
      </p>
    </div>

    <!-- 搜索框 -->
    <div class="search-box p-6 rounded-xl bg-dark-card mb-6">
      <div class="flex gap-4">
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

    <!-- 查询结果 -->
    <template v-if="userInfo">
      <!-- 用户信息卡片 -->
      <div class="user-card p-6 rounded-xl bg-dark-card mb-6">
        <div class="flex items-start gap-6">
          <img
            v-if="userInfo.avatar"
            :src="userInfo.avatar"
            class="w-20 h-20 rounded-full object-cover"
          >
          <div class="flex-1">
            <div class="flex items-center gap-3 mb-2">
              <span class="text-2xl font-bold text-white">{{ userInfo.nickname }}</span>
            </div>
            <div class="text-gray-400 text-sm mb-4">
              <span
                v-if="userInfo.unique_id"
                class="mr-4"
              >
                抖音号：{{ userInfo.unique_id }}
              </span>
            </div>
            <p
              v-if="userInfo.signature"
              class="text-gray-300 mb-4"
            >
              {{ userInfo.signature }}
            </p>
            <div class="flex items-center gap-8">
              <div>
                <span class="text-white font-medium">{{ userInfo.follower_count }}</span>
                <span class="text-gray-400 ml-1">粉丝</span>
              </div>
              <div>
                <span class="text-white font-medium">{{ userInfo.following_count }}</span>
                <span class="text-gray-400 ml-1">关注</span>
              </div>
              <div>
                <span class="text-white font-medium">{{ userInfo.aweme_count }}</span>
                <span class="text-gray-400 ml-1">作品</span>
              </div>
              <div>
                <span class="text-white font-medium">{{ userInfo.favoriting_count }}</span>
                <span class="text-gray-400 ml-1">获赞</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 作品列表 -->
      <h3 class="text-white font-medium mb-4">
        作品列表 ({{ userWorks.length }})
      </h3>
      <div
        v-if="userWorks.length > 0"
        class="video-grid grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4"
      >
        <div
          v-for="work in userWorks"
          :key="work.aweme_id"
          class="video-card group relative rounded-xl overflow-hidden bg-dark-card"
        >
          <div class="aspect-[9/16] relative">
            <img
              :src="work.cover"
              :alt="work.desc"
              class="w-full h-full object-cover"
              loading="lazy"
            >
            <div class="absolute bottom-2 left-2 flex items-center gap-3 text-white text-xs">
              <span class="flex items-center gap-1">
                <el-icon><Star /></el-icon>
                {{ work.digg_count }}
              </span>
            </div>
          </div>
          <div class="p-3">
            <p class="text-white text-sm line-clamp-2">
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
    </template>

    <!-- 功能说明 -->
    <div
      v-if="!userInfo"
      class="mt-8 grid grid-cols-1 md:grid-cols-3 gap-6"
    >
      <div class="feature-card p-6 rounded-xl bg-dark-card">
        <el-icon class="text-primary text-3xl mb-4">
          <User />
        </el-icon>
        <h3 class="text-white font-medium mb-2">
          用户信息
        </h3>
        <p class="text-gray-400 text-sm">
          获取用户基本信息，粉丝数、作品数等
        </p>
      </div>
      <div class="feature-card p-6 rounded-xl bg-dark-card">
        <el-icon class="text-primary text-3xl mb-4">
          <Grid />
        </el-icon>
        <h3 class="text-white font-medium mb-2">
          作品列表
        </h3>
        <p class="text-gray-400 text-sm">
          查看用户发布的所有作品
        </p>
      </div>
      <div class="feature-card p-6 rounded-xl bg-dark-card">
        <el-icon class="text-primary text-3xl mb-4">
          <Download />
        </el-icon>
        <h3 class="text-white font-medium mb-2">
          批量下载
        </h3>
        <p class="text-gray-400 text-sm">
          一键下载用户所有作品
        </p>
      </div>
    </div>
  </div>
</template>
