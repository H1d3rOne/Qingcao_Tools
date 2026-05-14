import { defineStore } from 'pinia'
import { ref } from 'vue'

// 搜索历史记录
export const useSearchStore = defineStore('search', () => {
  const history = ref<string[]>([])
  const maxHistory = 20

  function addHistory(keyword: string) {
    // 移除重复项
    const index = history.value.indexOf(keyword)
    if (index > -1) {
      history.value.splice(index, 1)
    }
    // 添加到开头
    history.value.unshift(keyword)
    // 限制数量
    if (history.value.length > maxHistory) {
      history.value = history.value.slice(0, maxHistory)
    }
  }

  function removeHistory(keyword: string) {
    const index = history.value.indexOf(keyword)
    if (index > -1) {
      history.value.splice(index, 1)
    }
  }

  function clearHistory() {
    history.value = []
  }

  return {
    history,
    addHistory,
    removeHistory,
    clearHistory
  }
}, {
  persist: {
    key: 'douyin-search'
  }
})
