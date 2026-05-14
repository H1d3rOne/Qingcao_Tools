<script setup lang="ts">
import { computed } from 'vue'
import { User, Star, ChatDotRound } from '@element-plus/icons-vue'
import { formatTime } from '@/utils/format'
import type { Comment } from '@/types/api'

interface Props {
  comment: Comment
}

const props = defineProps<Props>()

const emit = defineEmits<{
  reply: [comment: Comment]
}>()

const avatarUrl = computed(() => props.comment.user?.avatar)
</script>

<template>
  <div class="comment-item flex gap-3 p-4 rounded-lg bg-dark-card/50 hover:bg-dark-card transition-colors">
    <!-- 头像 -->
    <img
      v-if="avatarUrl"
      :src="avatarUrl"
      class="w-10 h-10 rounded-full object-cover flex-shrink-0"
    >
    <div
      v-else
      class="w-10 h-10 rounded-full bg-dark-lighter flex items-center justify-center flex-shrink-0"
    >
      <el-icon class="text-gray-400">
        <User />
      </el-icon>
    </div>

    <!-- 内容 -->
    <div class="flex-1 min-w-0">
      <div class="flex items-center gap-2">
        <span class="text-white text-sm font-medium">{{ comment.user?.nickname }}</span>
        <span class="text-gray-500 text-xs">{{ formatTime(comment.create_time, 'MM-DD HH:mm') }}</span>
      </div>
      
      <p class="text-gray-300 text-sm mt-1 leading-relaxed">
        {{ comment.text }}
      </p>

      <!-- 互动 -->
      <div class="flex items-center gap-4 mt-2 text-xs text-gray-400">
        <button class="flex items-center gap-1 hover:text-primary transition-colors">
          <el-icon><Star /></el-icon>
          {{ comment.digg_count || 0 }}
        </button>
        <button
          class="flex items-center gap-1 hover:text-primary transition-colors"
          @click="emit('reply', comment)"
        >
          <el-icon><ChatDotRound /></el-icon>
          回复
        </button>
      </div>

      <!-- 回复列表 -->
      <div
        v-if="comment.reply_comment && comment.reply_comment.length > 0"
        class="mt-3 space-y-2"
      >
        <CommentItem
          v-for="reply in comment.reply_comment.slice(0, 3)"
          :key="reply.cid"
          :comment="reply"
          @reply="emit('reply', $event)"
        />
        <button
          v-if="comment.reply_comment.length > 3"
          class="text-primary text-xs"
        >
          查看更多 {{ comment.reply_comment.length - 3 }} 条回复
        </button>
      </div>
    </div>
  </div>
</template>
