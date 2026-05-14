import { createRouter, createWebHistory } from 'vue-router'
import pinia, { useQuarkUserStore, useXianyuUserStore } from '@/stores'
import { routes } from './routes'

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(_to, _from, savedPosition) {
    if (savedPosition) {
      return savedPosition
    }
    return { top: 0 }
  }
})

router.beforeEach(async (to, _from, next) => {
  const title = to.meta.title as string | undefined
  document.title = title ? `${title} - Qingcao_Tools` : 'Qingcao_Tools'

  const isQuarkRoute = to.path.startsWith('/quark')
  const isXianyuRoute = to.path.startsWith('/xianyu')
  document.body.classList.toggle('quark-theme-active', isQuarkRoute)

  if (isQuarkRoute) {
    const quarkStore = useQuarkUserStore(pinia)
    if (!quarkStore.initialized) {
      await quarkStore.init()
    }

    if (to.meta.quarkRequiresAuth && !quarkStore.isLoggedIn) {
      next({ name: 'QuarkLogin', query: { redirect: to.fullPath } })
      return
    }

    if (to.name === 'QuarkLogin' && quarkStore.isLoggedIn) {
      next({ name: 'QuarkFiles' })
      return
    }
  }

  if (isXianyuRoute) {
    const xianyuStore = useXianyuUserStore(pinia)
    if (!xianyuStore.initialized) {
      await xianyuStore.init()
    }

    if (to.meta.xianyuRequiresAuth && !xianyuStore.isLoggedIn) {
      next({ name: 'XianyuLogin', query: { redirect: to.fullPath } })
      return
    }

    if (to.name === 'XianyuLogin' && xianyuStore.isLoggedIn) {
      next({ name: 'Xianyu' })
      return
    }
  }

  next()
})

export default router
