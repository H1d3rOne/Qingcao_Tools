<script setup lang="ts">
import { ref } from 'vue'
import { VideoCamera, DataLine, TrendCharts } from '@element-plus/icons-vue'
import { getLiveInfo } from '@/api'
import { useNotification } from '@/composables'

const { error, success } = useNotification()

const inputRoomId = ref('')
const loading = ref(false)
const liveInfo = ref<any>(null)

async function handleSearch() {
  if (!inputRoomId.value.trim()) {
    error('请输入直播间ID')
    return
  }

  loading.value = true
  liveInfo.value = null
  
  try {
    const res = await getLiveInfo(inputRoomId.value.trim())
    liveInfo.value = res
    success('查询成功')
  } catch (err) {
    console.error('查询失败:', err)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="live-page max-w-4xl mx-auto">
    <div class="mb-8">
      <h2 class="text-2xl font-bold text-white mb-2">
        直播间查询
      </h2>
      <p class="text-gray-400">
        输入直播间ID，获取直播详细信息
      </p>
    </div>

    <!-- 搜索框 -->
    <div class="search-box p-6 rounded-xl bg-dark-card">
      <div class="flex gap-4">
        <el-input
          v-model="inputRoomId"
          placeholder="请输入直播间ID"
          size="large"
          clearable
          @keyup.enter="handleSearch"
        >
          <template #prefix>
            <el-icon><VideoCamera /></el-icon>
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
      </div>
    </div>

    <!-- 查询结果 -->
    <div
      v-if="liveInfo"
      class="mt-6 p-6 rounded-xl bg-dark-card"
    >
      <h3 class="text-white font-medium mb-4">
        直播间信息
      </h3>
      <pre class="text-gray-300 text-sm overflow-auto">{{ JSON.stringify(liveInfo, null, 2) }}</pre>
    </div>

    <!-- 功能说明 -->
    <div
      v-if="!liveInfo"
      class="mt-8 grid grid-cols-1 md:grid-cols-3 gap-6"
    >
      <div class="feature-card p-6 rounded-xl bg-dark-card">
        <el-icon class="text-primary text-3xl mb-4">
          <VideoCamera />
        </el-icon>
        <h3 class="text-white font-medium mb-2">
          直播信息
        </h3>
        <p class="text-gray-400 text-sm">
          获取直播间基本信息和状态
        </p>
      </div>
      <div class="feature-card p-6 rounded-xl bg-dark-card">
        <el-icon class="text-primary text-3xl mb-4">
          <DataLine />
        </el-icon>
        <h3 class="text-white font-medium mb-2">
          数据统计
        </h3>
        <p class="text-gray-400 text-sm">
          观看人数、点赞数、礼物数等
        </p>
      </div>
      <div class="feature-card p-6 rounded-xl bg-dark-card">
        <el-icon class="text-primary text-3xl mb-4">
          <TrendCharts />
        </el-icon>
        <h3 class="text-white font-medium mb-2">
          贡献榜
        </h3>
        <p class="text-gray-400 text-sm">
          查看直播间礼物贡献排行榜
        </p>
      </div>
    </div>
  </div>
</template>
