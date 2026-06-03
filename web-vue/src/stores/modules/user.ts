import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { User, Video } from '@/types/api'
import { getUserInfoBySecUid, getUserVideos, getUserLikes } from '@/api'

function normalizeWorksPayload(payload: any) {
  if (Array.isArray(payload)) {
    return {
      data: payload,
      has_more: false,
      cursor: 0
    }
  }
  return {
    data: payload?.data || [],
    has_more: Boolean(payload?.has_more),
    cursor: Number(payload?.cursor || 0)
  }
}

export const useUserStore = defineStore('user', () => {
  // State
  const currentUser = ref<User | null>(null)
  const userVideos = ref<Video[]>([])
  const userLikes = ref<Video[]>([])
  const loading = ref(false)
  const videosLoading = ref(false)
  const likesLoading = ref(false)
  const videosHasMore = ref(true)
  const likesHasMore = ref(true)
  const videosCursor = ref(0)
  const likesCursor = ref(0)

  // Getters
  const userId = computed(() => currentUser.value?.uid)
  const secUid = computed(() => currentUser.value?.sec_uid)

  // Actions
  async function fetchUserInfo(sec_uid: string) {
    console.log('[UserStore] fetchUserInfo called with sec_uid:', sec_uid)
    loading.value = true
    try {
      const res = await getUserInfoBySecUid(sec_uid)
      console.log('[UserStore] API response:', res)
      console.log('[UserStore] res.data:', res.data)
      // 直接赋值
      currentUser.value = res.data
      console.log('[UserStore] currentUser after update:', currentUser.value)
      return res.data
    } catch (error) {
      console.error('[UserStore] fetchUserInfo error:', error)
      throw error
    } finally {
      loading.value = false
    }
  }

  async function fetchUserVideos(sec_uid: string, cursor = 0, append = false) {
    if (videosLoading.value) return
    
    videosLoading.value = true
    try {
      const res = await getUserVideos({ 
        sec_uid, 
        cursor,
        count: 24 
      })
      
      const payload = normalizeWorksPayload(res.data)

      if (append) {
        userVideos.value = [...userVideos.value, ...payload.data]
      } else {
        userVideos.value = payload.data
      }
      
      videosHasMore.value = payload.has_more
      videosCursor.value = payload.cursor
      
      return payload
    } finally {
      videosLoading.value = false
    }
  }

  async function fetchUserLikes(sec_uid: string, cursor = 0, append = false) {
    if (likesLoading.value) return
    
    likesLoading.value = true
    try {
      const res = await getUserLikes({ 
        sec_uid, 
        cursor,
        count: 24 
      })
      
      if (append) {
        userLikes.value = [...userLikes.value, ...res.data.data]
      } else {
        userLikes.value = res.data.data
      }
      
      likesHasMore.value = res.data.has_more
      likesCursor.value = res.data.cursor
      
      return res.data
    } finally {
      likesLoading.value = false
    }
  }

  function clearCurrentUser() {
    currentUser.value = null
    userVideos.value = []
    userLikes.value = []
    videosCursor.value = 0
    likesCursor.value = 0
    videosHasMore.value = true
    likesHasMore.value = true
  }

  return {
    currentUser,
    userVideos,
    userLikes,
    loading,
    videosLoading,
    likesLoading,
    videosHasMore,
    likesHasMore,
    videosCursor,
    likesCursor,
    userId,
    secUid,
    fetchUserInfo,
    fetchUserVideos,
    fetchUserLikes,
    clearCurrentUser
  }
}, {
  persist: false  // 暂时禁用持久化，确保每次都是最新数据
})
