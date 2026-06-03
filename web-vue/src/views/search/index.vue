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
import type { User, Author, SearchParams } from '@/types/api'

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

function handleUserClick(user: User | Author) {
  router.push(`/user/${user.sec_uid}`)
}
</script>

<template>
  <div class="search-user">
    <!-- 搜索框 -->
    <div class="search-box mb-6">
      <div class="flex gap-4">
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
        class="user-list grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
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
    </template>
  </div>
</template>
