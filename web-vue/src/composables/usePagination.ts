import { ref, computed } from 'vue'
import type { Ref } from 'vue'

interface PaginationOptions<T, P> {
  fetchFn: (params: P) => Promise<{ data: any }>
  pageSize?: number
}

export function usePagination<T, P extends Record<string, any>>(
  options: PaginationOptions<T, P>
) {
  const { fetchFn, pageSize = 20 } = options

  const list: Ref<T[]> = ref([])
  const loading = ref(false)
  const hasMore = ref(true)
  const cursor = ref(0)

  const isEmpty = computed(() => list.value.length === 0 && !loading.value)
  const hasData = computed(() => list.value.length > 0)

  async function loadMore(params: Omit<P, 'cursor' | 'count'>, append = true) {
    if (loading.value || !hasMore.value) return { data: [], has_more: false, cursor: 0 }

    loading.value = true
    try {
      const res = await fetchFn({
        ...params,
        cursor: cursor.value,
        count: pageSize
      } as unknown as P)

      const payload = res.data || {}
      const data = (payload.data || payload.items || []) as T[]
      const has_more = Boolean(payload.has_more)
      const newCursor = Number(payload.cursor ?? payload.next_offset ?? 0)

      if (append) {
        list.value = [...list.value, ...data]
      } else {
        list.value = data
      }

      hasMore.value = has_more
      cursor.value = newCursor

      return { data, has_more, cursor: newCursor }
    } catch (error) {
      console.error('加载更多失败:', error)
      return { data: [], has_more: false, cursor: 0 }
    } finally {
      loading.value = false
    }
  }

  function reset() {
    list.value = []
    cursor.value = 0
    hasMore.value = true
    loading.value = false
  }

  return {
    list,
    loading,
    hasMore,
    isEmpty,
    hasData,
    cursor,
    loadMore,
    reset
  }
}
