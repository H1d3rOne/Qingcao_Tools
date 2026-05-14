<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Search } from '@element-plus/icons-vue'
import { searchUsers } from '@/api'
import { useSearchStore } from '@/stores'
import { usePagination } from '@/composables'
import UserCard from '@/components/business/UserCard.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import type { User, SearchParams } from '@/types/api'

const route = useRoute()
const router = useRouter()
const searchStore = useSearchStore()

const keyword = ref('')

const { 
  list: users, 
  loading, 
  hasMore, 
  isEmpty,
  loadMore, 
  reset 
} = usePagination<User, SearchParams>({
  fetchFn: (params) => searchUsers(params)
})

onMounted(() => {
  if (route.query.q) {
    keyword.value = route.query.q as string
    handleSearch()
  }
})

watch(() => route.query.q, (newQ) => {
  if (newQ && newQ !== keyword.value) {
    keyword.value = newQ as string
    handleSearch()
  }
})

async function handleSearch() {
  if (!keyword.value.trim()) return
  
  searchStore.addHistory(keyword.value)
  router.push({ query: { q: keyword.value } })
  
  reset()
  await loadMore({ keyword: keyword.value })
}

async function handleLoadMore() {
  await loadMore({ keyword: keyword.value })
}

function handleUserClick(user: User) {
  router.push(`/user/${user.sec_uid}`)
}
</script>

<template>
  <div class="search-page">
    <!-- 搜索框 -->
    <div class="search-box">
      <div class="search-input-group">
        <el-input
          v-model="keyword"
          placeholder="搜索用户"
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
          @click="handleSearch"
        >
          搜索
        </el-button>
      </div>
    </div>

    <!-- 结果列表 -->
    <template v-if="keyword">
      <div
        v-if="!isEmpty"
        class="user-list"
      >
        <UserCard
          v-for="user in users"
          :key="user.uid"
          :user="user"
          @click="handleUserClick"
        />
      </div>

      <EmptyState
        v-else-if="!loading"
        text="未找到相关用户"
      />

      <LoadingSpinner v-if="loading" />

      <div
        v-if="hasMore && users.length > 0"
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
    </template>
  </div>
</template>

<style scoped>
.search-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.search-box {
  padding: 18px;
  border-radius: 16px;
  border: 1.5px solid rgba(var(--app-border-rgb) / 0.7);
  background: rgba(var(--app-surface-rgb) / 0.95);
  box-shadow: 0 8px 20px rgba(var(--app-shadow-rgb) / 0.08);
}

.search-input-group {
  display: flex;
  gap: 12px;
}

.search-input-group .el-input {
  flex: 1;
}

.user-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}

.load-more {
  text-align: center;
  padding: 20px 0;
}

@media (max-width: 768px) {
  .search-page {
    padding: 16px;
  }

  .search-input-group {
    flex-direction: column;
  }

  .user-list {
    grid-template-columns: 1fr;
  }
}
</style>
