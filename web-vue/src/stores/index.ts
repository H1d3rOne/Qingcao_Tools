import { createPinia } from 'pinia'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'

const pinia = createPinia()
pinia.use(piniaPluginPersistedstate)

export default pinia

// 导出所有 store
export * from './modules/app'
export * from './modules/video'
export * from './modules/user'
export * from './modules/search'

export * from './modules/quark'
export * from './modules/xianyu'
