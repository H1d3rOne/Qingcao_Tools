import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Video } from '@/types/api'
import { getVideoInfo, getVideoComments } from '@/api'
import type { Comment } from '@/types/api'

export const useVideoStore = defineStore('video', () => {
  // State
  const currentVideo = ref<Video | null>(null)
  const comments = ref<Comment[]>([])
  const relatedVideos = ref<Video[]>([])
  const loading = ref(false)
  const commentsLoading = ref(false)
  const commentsHasMore = ref(true)
  const commentsCursor = ref(0)

  // Getters
  const videoId = computed(() => currentVideo.value?.aweme_id)

  // Actions
  async function fetchVideoInfo(aweme_id: string) {
    loading.value = true
    try {
      const res = await getVideoInfo(aweme_id)
      currentVideo.value = res.data
      return res.data
    } finally {
      loading.value = false
    }
  }

  async function fetchComments(aweme_id: string, cursor = 0, append = false) {
    if (commentsLoading.value) return
    
    commentsLoading.value = true
    try {
      const res = await getVideoComments({ 
        aweme_id, 
        cursor,
        count: 20 
      })
      
      if (append) {
        comments.value = [...comments.value, ...res.data.data]
      } else {
        comments.value = res.data.data
      }
      
      commentsHasMore.value = res.data.has_more
      commentsCursor.value = res.data.cursor
      
      return res.data
    } finally {
      commentsLoading.value = false
    }
  }

  function resetComments() {
    comments.value = []
    commentsCursor.value = 0
    commentsHasMore.value = true
  }

  function clearCurrentVideo() {
    currentVideo.value = null
    comments.value = []
    relatedVideos.value = []
  }

  return {
    currentVideo,
    comments,
    relatedVideos,
    loading,
    commentsLoading,
    commentsHasMore,
    commentsCursor,
    videoId,
    fetchVideoInfo,
    fetchComments,
    resetComments,
    clearCurrentVideo
  }
}, {
  persist: {
    key: 'douyin-video',
    paths: ['currentVideo']
  }
})
