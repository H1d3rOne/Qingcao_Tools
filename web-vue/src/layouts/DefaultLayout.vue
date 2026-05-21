<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAppStore } from '@/stores'
import {
  VideoPlay,
  Setting,
  Fold,
  Expand,
  Cloudy,
  Promotion,
  Cellphone,
  ShoppingCart
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const appStore = useAppStore()

const menuItems = [
  {
    path: '/douyin',
    icon: VideoPlay,
    title: '抖音解析',
    module: 'douyin'
  },
  {
    path: '/wechat',
    icon: Cellphone,
    title: '视频号助手',
    module: 'wechat'
  },
  {
    path: '/xianyu',
    icon: ShoppingCart,
    title: '闲鱼工具',
    module: 'xianyu'
  },
  {
    path: '/quark',
    icon: Cloudy,
    title: '夸克工具',
    module: 'quark'
  },
  {
    path: '/notify',
    icon: Promotion,
    title: '消息推送',
    module: 'notify'
  },
  {
    path: '/settings',
    icon: Setting,
    title: '设置',
    module: 'settings'
  }
]

const activeModule = computed(() => {
  const path = route.path
  if (path.startsWith('/douyin')) return 'douyin'
  if (path.startsWith('/quark')) return 'quark'
  if (path.startsWith('/wechat')) return 'wechat'
  if (path.startsWith('/xianyu')) return 'xianyu'
  if (path.startsWith('/notify')) return 'notify'
  if (path.startsWith('/settings')) return 'settings'
  return 'home'
})

const douyinSubMenus = [
  { path: '/douyin', title: '首页', exact: true },
  { path: '/douyin/video', title: '视频' },
  { path: '/douyin/user', title: '用户' },
  { path: '/douyin/search', title: '搜索' },
  { path: '/douyin/live', title: '直播' }
]

const quarkSubMenus: Array<{ path: string; title: string; exact?: boolean }> = []

const currentSubMenus = computed(() => {
  if (activeModule.value === 'douyin') return douyinSubMenus
  if (activeModule.value === 'quark') return quarkSubMenus
  return []
})

const isQuarkImmersive = computed(() => activeModule.value === 'quark')
const mainContainerClass = computed(() => {
  if (isQuarkImmersive.value) return 'is-immersive p-0'
  if (activeModule.value === 'wechat') return 'is-default px-6 pb-3 pt-0'
  if (activeModule.value === 'xianyu') return 'is-default px-6 pb-6 pt-0'
  return 'is-default p-6'
})

function handleMenuSelect(path: string) {
  router.push(path)
}

function isActiveSubMenu(subPath: string, exact: boolean = false) {
  if (exact) {
    return route.path === subPath
  }
  return route.path.startsWith(subPath)
}

function getKeepAliveComponents(): string[] {
  return ['DouyinSearch']
}
</script>

<template>
  <div class="layout-shell h-screen flex">
    <aside
      class="sidebar transition-all duration-300 flex flex-col"
      :class="appStore.sidebarCollapsed ? 'w-16' : 'w-56'"
    >
      <div class="logo h-16 flex items-center justify-center px-3">
        <div class="logo-lockup flex items-center justify-center">
          <div class="logo-icon w-12 h-12 rounded-2xl flex items-center justify-center">
            <img
              class="logo-image"
              src="/qingcao-logo.svg"
              alt="青草工具箱 Logo"
            >
          </div>
          <span
            v-show="!appStore.sidebarCollapsed"
            class="logo-text ml-3 text-lg font-bold whitespace-nowrap"
          >
            青草工具箱
          </span>
        </div>
      </div>

      <nav class="flex-1 py-4 overflow-y-auto">
        <div class="px-3 mb-2">
          <span
            v-show="!appStore.sidebarCollapsed"
            class="module-title text-xs font-medium uppercase tracking-wider"
          >
            功能模块
          </span>
        </div>
        <ul class="space-y-1 px-2">
          <li
            v-for="item in menuItems"
            :key="item.path"
          >
            <div
              class="menu-item flex items-center px-3 py-3 rounded-lg cursor-pointer transition-all group"
              :class="[
                activeModule === item.module ? 'is-active' : 'is-idle'
              ]"
              @click="handleMenuSelect(item.path)"
            >
              <el-icon
                :size="20"
                class="transition-transform group-hover:scale-110"
              >
                <component :is="item.icon" />
              </el-icon>
              <span
                v-show="!appStore.sidebarCollapsed"
                class="ml-3 whitespace-nowrap font-medium"
              >
                {{ item.title }}
              </span>
              <span
                v-if="activeModule === item.module && !appStore.sidebarCollapsed"
                class="menu-item-dot ml-auto w-1.5 h-1.5 rounded-full"
              />
            </div>
          </li>
        </ul>
      </nav>

      <div class="sidebar-footer p-4">
        <button
          class="collapse-trigger w-full p-2.5 rounded-lg transition-all"
          @click="appStore.toggleSidebar"
        >
          <el-icon :size="18">
            <Fold v-if="!appStore.sidebarCollapsed" />
            <Expand v-else />
          </el-icon>
        </button>
      </div>
    </aside>

    <main class="flex-1 flex flex-col overflow-hidden">
      <header
        v-if="currentSubMenus.length > 0 && !isQuarkImmersive"
        class="module-sub-header h-12 backdrop-blur-sm flex items-center px-4"
      >
        <div class="flex items-center space-x-1">
          <div
            v-for="sub in currentSubMenus"
            :key="sub.path"
            class="sub-menu-item px-3 py-1.5 rounded-md text-sm cursor-pointer transition-all"
            :class="[
              isActiveSubMenu(sub.path, sub.exact) ? 'is-active' : 'is-idle'
            ]"
            @click="handleMenuSelect(sub.path)"
          >
            {{ sub.title }}
          </div>
        </div>
      </header>

      <div
        id="main-scroll-container"
        class="main-scroll-container flex-1 overflow-auto"
        :class="mainContainerClass"
      >
        <router-view v-slot="{ Component, route: currentRoute }">
          <transition
            name="fade"
            mode="out-in"
          >
            <keep-alive :include="getKeepAliveComponents()">
              <component
                :is="Component"
                :key="currentRoute.fullPath"
              />
            </keep-alive>
          </transition>
        </router-view>
      </div>
    </main>
  </div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.layout-shell {
  background: rgb(var(--app-bg-rgb));
}

.sidebar {
  background: rgba(var(--app-surface-alt-rgb) / 0.96);
  border-right: 1px solid rgba(var(--app-border-rgb) / 0.7);
}

.logo {
  border-bottom: 1px solid rgba(var(--app-border-rgb) / 0.5);
}

.logo-lockup {
  min-width: 0;
}

.logo-icon {
  position: relative;
  overflow: hidden;
  background: transparent;
  box-shadow: 0 12px 30px rgba(var(--primary-color-rgb) / 0.18);
}

.logo-image {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.logo-text {
  color: rgb(var(--primary-color-rgb));
  background: linear-gradient(135deg, rgb(var(--primary-deep-rgb)) 0%, rgb(var(--primary-color-rgb)) 48%, rgb(var(--app-accent-alt-rgb)) 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  font-family: 'Yuanti SC', 'PingFang SC', 'Microsoft YaHei UI', 'Microsoft YaHei', 'Noto Sans CJK SC', 'Source Han Sans SC', sans-serif;
  font-size: 1.18rem;
  font-weight: 900;
  letter-spacing: 0.12em;
  line-height: 1;
  text-shadow: 0 4px 14px rgba(var(--primary-color-rgb) / 0.18);
}

.module-title {
  color: rgb(var(--app-text-subtle-rgb));
}

.menu-item,
.sub-menu-item,
.collapse-trigger {
  user-select: none;
}

.menu-item.is-idle {
  color: rgb(var(--app-text-muted-rgb));
}

.menu-item.is-idle:hover {
  color: rgb(var(--app-text-strong-rgb));
  background: rgba(var(--primary-color-rgb) / 0.06);
}

.menu-item.is-active {
  color: rgb(var(--primary-color-rgb));
  border: 1px solid rgba(var(--primary-color-rgb) / 0.3);
  background: rgba(var(--primary-color-rgb) / 0.1);
}

.menu-item-dot {
  background: rgb(var(--primary-color-rgb));
  box-shadow: 0 0 8px rgba(var(--primary-color-rgb) / 0.5);
}

.sidebar-footer {
  border-top: 1px solid rgba(var(--app-border-rgb) / 0.5);
}

.collapse-trigger {
  color: rgb(var(--app-text-muted-rgb));
  background: rgba(var(--app-surface-rgb) / 0.8);
  border: 1px solid rgba(var(--app-border-rgb) / 0.5);
}

.collapse-trigger:hover {
  color: rgb(var(--app-text-strong-rgb));
  border-color: rgba(var(--primary-color-rgb) / 0.4);
}

.module-sub-header {
  background: rgba(var(--app-surface-alt-rgb) / 0.9);
  border-bottom: 1px solid rgba(var(--app-border-rgb) / 0.6);
}

.sub-menu-item.is-idle {
  color: rgb(var(--app-text-muted-rgb));
}

.sub-menu-item.is-idle:hover {
  color: rgb(var(--app-text-strong-rgb));
  background: rgba(var(--primary-color-rgb) / 0.06);
}

.sub-menu-item.is-active {
  color: rgb(var(--primary-color-rgb));
  background: rgba(var(--primary-color-rgb) / 0.1);
  border: 1px solid rgba(var(--primary-color-rgb) / 0.3);
}

.main-scroll-container.is-default {
  background:
    radial-gradient(ellipse at 8% 2%, rgba(var(--primary-color-rgb) / 0.06), transparent 30%),
    radial-gradient(ellipse at 92% 0%, rgba(var(--app-accent-alt-rgb) / 0.04), transparent 28%),
    linear-gradient(180deg, rgb(var(--app-bg-rgb)) 0%, rgb(var(--app-bg-deep-rgb)) 100%);
}

.main-scroll-container.is-immersive {
  background: rgb(var(--app-bg-rgb));
}

::-webkit-scrollbar {
  width: 5px;
  height: 5px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: rgba(var(--app-border-rgb) / 0.6);
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: rgba(var(--primary-color-rgb) / 0.4);
}
</style>
