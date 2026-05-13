<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { Search } from '@element-plus/icons-vue'
import { searchUsers } from '@/api'
import type { SearchUser } from '@/api/modules/search'

const router = useRouter()
const keyword = ref('')
const loading = ref(false)
const users = ref<SearchUser[]>([])

async function handleSearch() {
  if (!keyword.value.trim()) return
  
  loading.value = true
  try {
    const res = await searchUsers({ keyword: keyword.value.trim(), limit: 30 })
    users.value = res.data.data || []
  } catch (error) {
    // console.error('搜索失败:', error)
  } finally {
    loading.value = false
  }
}

function goToUser(secUid: string) {
  router.push(`/douyin/user/${secUid}`)
}
</script>

<template>
  <div class="search-user-page">
    <!-- 搜索框 -->
    <div class="search-box">
      <el-input
        v-model="keyword"
        placeholder="搜索抖音用户"
        size="large"
        class="search-input"
        @keyup.enter="handleSearch"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
        <template #append>
          <el-button
            type="primary"
            :loading="loading"
            @click="handleSearch"
          >
            搜索
          </el-button>
        </template>
      </el-input>
    </div>

    <!-- 搜索结果 -->
    <div
      v-if="users.length > 0"
      class="user-list"
    >
      <div
        v-for="user in users"
        :key="user.sec_uid"
        class="user-card"
        @click="goToUser(user.sec_uid)"
      >
        <div class="user-card-inner">
          <el-avatar
            :size="56"
            :src="user.avatar"
          />
          <div class="user-info">
            <div class="user-name">
              {{ user.nickname }}
            </div>
            <div class="user-signature">
              {{ user.signature || '暂无签名' }}
            </div>
            <div class="user-stats">
              <span class="stat">粉丝: {{ user.follower_count || 0 }}</span>
              <span class="stat">作品: {{ user.aweme_count || 0 }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div
      v-else-if="!loading"
      class="empty-state"
    >
      <el-icon
        class="empty-icon"
        :size="64"
      >
        <Search />
      </el-icon>
      <p class="empty-text">
        输入关键词搜索用户
      </p>
    </div>
  </div>
</template>

<style scoped>
.search-user-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.search-box {
  padding: 16px;
  border-radius: 16px;
  border: 1px solid rgba(var(--app-border-rgb), 0.52);
  background: rgba(var(--app-surface-rgb), 0.88);
  box-shadow:
    0 10px 24px rgba(var(--app-shadow-rgb), 0.07),
    inset 0 1px 0 rgba(var(--utility-white-rgb), 0.5);
  backdrop-filter: blur(12px);
}

.search-input :deep(.el-input__wrapper) {
  background-color: var(--dark-card);
  border-color: #3a3a3a;
}

.search-input :deep(.el-input-group__append) {
  background-color: var(--primary-color);
  border-color: var(--primary-color);
}

.user-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 16px;
}

.user-card {
  padding: 18px;
  border-radius: 14px;
  border: 1px solid rgba(var(--app-border-rgb), 0.45);
  background: rgba(var(--app-surface-rgb), 0.92);
  cursor: pointer;
  transition: all 0.25s ease;
  box-shadow: 0 4px 12px rgba(var(--app-shadow-rgb), 0.05);
}

.user-card:hover {
  border-color: rgba(var(--primary-color-rgb), 0.5);
  background: rgba(var(--app-surface-rgb), 0.98);
  box-shadow: 0 8px 24px rgba(var(--app-shadow-rgb), 0.1);
  transform: translateY(-2px);
}

.user-card-inner {
  display: flex;
  align-items: center;
  gap: 16px;
}

.user-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.user-name {
  font-size: 16px;
  font-weight: 600;
  color: rgb(var(--app-text-strong-rgb));
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-signature {
  font-size: 13px;
  color: rgb(var(--app-text-muted-rgb));
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-stats {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 4px;
}

.stat {
  font-size: 12px;
  color: rgb(var(--app-text-subtle-rgb));
  padding: 4px 10px;
  border-radius: 20px;
  background: rgba(var(--app-surface-alt-rgb), 0.7);
  border: 1px solid rgba(var(--app-border-rgb), 0.2);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
}

.empty-icon {
  color: rgb(var(--app-text-subtle-rgb));
  margin-bottom: 20px;
}

.empty-text {
  font-size: 16px;
  color: rgb(var(--app-text-muted-rgb));
}
</style>
