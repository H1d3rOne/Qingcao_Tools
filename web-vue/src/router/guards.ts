// 路由守卫相关逻辑
import type { Router } from 'vue-router'

export function setupRouterGuards(router: Router) {
  router.beforeEach((to, from, next) => {
    // 可以在这里添加权限验证等逻辑
    next()
  })

  router.afterEach((to) => {
    // 页面切换后的处理
  })
}
