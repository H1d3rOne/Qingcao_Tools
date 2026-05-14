import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

export const useAppStore = defineStore('app', () => {
  const sidebarCollapsed = ref(false)
  const loading = ref(false)
  const currentModule = ref('home')

  const isCollapsed = computed(() => sidebarCollapsed.value)

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  function setLoading(value: boolean) {
    loading.value = value
  }

  function setCurrentModule(module: string) {
    currentModule.value = module
  }

  return {
    sidebarCollapsed,
    loading,
    currentModule,
    isCollapsed,
    toggleSidebar,
    setLoading,
    setCurrentModule
  }
}, {
  persist: {
    key: 'douyin-app',
    paths: ['sidebarCollapsed']
  }
})
