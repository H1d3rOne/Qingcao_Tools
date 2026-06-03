<script setup lang="ts">
import { computed } from 'vue'
import { View, Star, Download } from '@element-plus/icons-vue'
import { formatNumber } from '@/utils/format'
import type { Video } from '@/types/api'

interface Props {
  video: Video
}

const props = defineProps<Props>()

const emit = defineEmits<{
  click: [video: Video]
  download: [video: Video]
}>()

const coverUrl = computed(() => {
  if (typeof props.video.cover === 'string') {
    return props.video.cover
  }
  return props.video.cover?.url_list?.[0] || props.video.cover_url || ''
})
const authorAvatar = computed(() => props.video.author?.avatar)
const duration = computed(() => props.video.video?.duration || props.video.duration)

function handleClick() {
  emit('click', props.video)
}

function handleDownload(e: Event) {
  e.stopPropagation()
  emit('download', props.video)
}
</script>

<template>
  <div
    class="video-card group relative rounded-xl overflow-hidden cursor-pointer transition-all duration-300 hover:scale-[1.02]"
    @click="handleClick"
  >
    <div class="aspect-[9/16] relative">
      <img
        :src="coverUrl"
        :alt="video.desc"
        class="w-full h-full object-cover"
        loading="lazy"
      >
      
      <div class="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity play-overlay">
        <el-icon class="play-icon">
          <svg viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg">
            <path fill="currentColor" d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64zm156.1 498.3L408.9 703.4c-9.3 6.7-22.1-.4-22.1-11.7V332.3c0-11.3 12.8-18.4 22.1-11.7l259.2 140.3c8.6 4.7 8.6 18.7 0 23.4z" />
          </svg>
        </el-icon>
      </div>

      <div v-if="duration" class="duration-badge">
        {{ Math.floor(duration / 60) }}:{{ String(duration % 60).padStart(2, '0') }}
      </div>

      <div class="stats-overlay">
        <span class="flex items-center gap-1">
          <el-icon><View /></el-icon>
          {{ formatNumber(video.statistics?.play_count) }}
        </span>
        <span class="flex items-center gap-1">
          <el-icon><Star /></el-icon>
          {{ formatNumber(video.statistics?.digg_count) }}
        </span>
      </div>

      <button class="download-btn" @click="handleDownload">
        <el-icon><Download /></el-icon>
      </button>
    </div>

    <div class="card-info">
      <p class="card-desc">{{ video.desc }}</p>
      <div class="card-author">
        <img v-if="authorAvatar" :src="authorAvatar" class="author-avatar" />
        <span class="author-name">{{ video.author?.nickname }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.video-card {
  background: rgba(var(--app-surface-rgb) / 0.92);
  border: 1px solid rgba(var(--app-border-rgb) / 0.7);
}

.video-card:hover {
  border-color: rgba(var(--primary-color-rgb) / 0.3);
  box-shadow: 0 8px 24px rgba(var(--app-shadow-rgb) / 0.2);
}

.play-overlay {
  background: rgba(0, 0, 0, 0.35);
}

.play-icon {
  font-size: 48px;
  color: rgb(var(--utility-white-rgb));
  filter: drop-shadow(0 2px 8px rgba(0, 0, 0, 0.3));
}

.duration-badge {
  position: absolute;
  bottom: 8px;
  right: 8px;
  padding: 2px 8px;
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.65);
  color: rgb(var(--utility-white-rgb));
  font-size: 12px;
}

.stats-overlay {
  position: absolute;
  bottom: 8px;
  left: 8px;
  display: flex;
  align-items: center;
  gap: 12px;
  color: rgb(var(--utility-white-rgb));
  font-size: 12px;
}

.download-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  padding: 6px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.5);
  border: none;
  color: rgb(var(--utility-white-rgb));
  cursor: pointer;
  opacity: 0;
  transition: all 0.2s ease;
}

.video-card:hover .download-btn {
  opacity: 1;
}

.download-btn:hover {
  background: rgb(var(--primary-color-rgb));
}

.card-info {
  padding: 10px 12px;
}

.card-desc {
  color: rgb(var(--app-text-strong-rgb));
  font-size: 13px;
  line-height: 1.5;
  margin: 0 0 6px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-author {
  display: flex;
  align-items: center;
  gap: 6px;
}

.author-avatar {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  object-fit: cover;
}

.author-name {
  color: rgb(var(--app-text-muted-rgb));
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
