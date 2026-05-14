<script setup lang="ts">
import { computed } from 'vue'
import { User as UserIcon, Check, ArrowRight } from '@element-plus/icons-vue'
import { formatNumber } from '@/utils/format'
import type { User, Author } from '@/types/api'

interface Props {
  user: User | Author
}

const props = defineProps<Props>()

const emit = defineEmits<{
  click: [user: User | Author]
}>()

const avatarUrl = computed(() => props.user.avatar)
const isVerified = computed(() => (props.user as any).is_verify === 1)
</script>

<template>
  <div class="user-card" @click="emit('click', user)">
    <div class="user-avatar-wrap">
      <img v-if="avatarUrl" :src="avatarUrl" class="user-avatar" />
      <div v-else class="user-avatar-placeholder">
        <el-icon><UserIcon /></el-icon>
      </div>
      <div v-if="isVerified" class="verify-badge">
        <el-icon><Check /></el-icon>
      </div>
    </div>

    <div class="user-info">
      <div class="user-name-row">
        <span class="user-nickname">{{ user.nickname }}</span>
        <span v-if="user.unique_id" class="user-unique-id">@{{ user.unique_id }}</span>
      </div>
      <p v-if="user.signature" class="user-signature">{{ user.signature }}</p>
      <div class="user-stats">
        <span><span class="stats-num">{{ formatNumber(user.follower_count) }}</span> 粉丝</span>
        <span><span class="stats-num">{{ formatNumber((user as User).aweme_count || 0) }}</span> 作品</span>
      </div>
    </div>

    <el-icon class="user-arrow"><ArrowRight /></el-icon>
  </div>
</template>

<style scoped>
.user-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
  border-radius: 14px;
  background: rgba(var(--app-surface-rgb) / 0.92);
  border: 1px solid rgba(var(--app-border-rgb) / 0.7);
  cursor: pointer;
  transition: all 0.2s ease;
}

.user-card:hover {
  border-color: rgba(var(--primary-color-rgb) / 0.3);
  background: rgba(var(--app-surface-alt-rgb) / 0.92);
}

.user-avatar-wrap {
  position: relative;
  flex-shrink: 0;
}

.user-avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  object-fit: cover;
}

.user-avatar-placeholder {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: rgba(var(--app-surface-alt-rgb) / 0.92);
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgb(var(--app-text-muted-rgb));
  font-size: 24px;
}

.verify-badge {
  position: absolute;
  bottom: -2px;
  right: -2px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: rgb(var(--primary-color-rgb));
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgb(var(--utility-white-rgb));
  font-size: 10px;
}

.user-info {
  flex: 1;
  min-width: 0;
}

.user-name-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.user-nickname {
  font-weight: 500;
  color: rgb(var(--app-text-strong-rgb));
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-unique-id {
  color: rgb(var(--app-text-subtle-rgb));
  font-size: 12px;
}

.user-signature {
  color: rgb(var(--app-text-muted-rgb));
  font-size: 12px;
  margin: 4px 0 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-stats {
  display: flex;
  gap: 14px;
  margin-top: 6px;
  font-size: 12px;
  color: rgb(var(--app-text-muted-rgb));
}

.stats-num {
  color: rgb(var(--app-text-strong-rgb));
}

.user-arrow {
  color: rgb(var(--app-text-subtle-rgb));
  flex-shrink: 0;
}
</style>
