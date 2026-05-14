import type { RouteRecordRaw } from 'vue-router'

export const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/douyin'
  },
  {
    path: '/douyin',
    component: () => import('@/layouts/DefaultLayout.vue'),
    children: [
      {
        path: '',
        name: 'DouyinHome',
        component: () => import('@/views/douyin/home/index.vue'),
        meta: { title: '抖音解析 - 首页' }
      },
      {
        path: 'video',
        name: 'DouyinVideo',
        component: () => import('@/views/douyin/video/index.vue'),
        meta: { title: '作品查询' }
      },
      {
        path: 'video/:id',
        name: 'DouyinVideoDetail',
        component: () => import('@/views/douyin/video/detail.vue'),
        meta: { title: '作品详情' }
      },
      {
        path: 'user',
        name: 'DouyinUser',
        component: () => import('@/views/douyin/user/index.vue'),
        meta: { title: '用户查询' }
      },
      {
        path: 'user/:id',
        name: 'DouyinUserProfile',
        component: () => import('@/views/douyin/user/profile.vue'),
        meta: { title: '用户主页' }
      },
      {
        path: 'search',
        name: 'DouyinSearch',
        component: () => import('@/views/douyin/search/video.vue'),
        meta: { title: '全能搜索', keepAlive: true }
      },
      {
        path: 'search/user',
        name: 'DouyinSearchUser',
        component: () => import('@/views/douyin/search/user.vue'),
        meta: { title: '用户搜索' }
      },
      {
        path: 'live',
        name: 'DouyinLive',
        component: () => import('@/views/douyin/live/index.vue'),
        meta: { title: '直播间查询' }
      }
    ]
  },
  {
    path: '/quark',
    component: () => import('@/layouts/DefaultLayout.vue'),
    children: [
      {
        path: '',
        redirect: '/quark/login'
      },
      {
        path: 'login',
        name: 'QuarkLogin',
        component: () => import('@/views/quark/login/index.vue'),
        meta: { title: '夸克工具 - 登录', quarkPublic: true }
      },
      {
        path: 'files',
        name: 'QuarkFiles',
        component: () => import('@/views/quark/files/index.vue'),
        meta: { title: '夸克工具 - 文件管理', quarkRequiresAuth: true }
      },
      {
        path: ':pathMatch(.*)*',
        redirect: '/quark/login'
      }
    ]
  },
  {
    path: '/wechat',
    component: () => import('@/layouts/DefaultLayout.vue'),
    children: [
      {
        path: '',
        name: 'Wechat',
        component: () => import('@/views/wechat/index.vue'),
        meta: { title: '视频号下载' }
      }
    ]
  },
  {
    path: '/xianyu',
    component: () => import('@/layouts/DefaultLayout.vue'),
    children: [
      {
        path: 'login',
        name: 'XianyuLogin',
        component: () => import('@/views/xianyu/login/index.vue'),
        meta: { title: '闲鱼工具 - 登录', xianyuPublic: true }
      },
      {
        path: '',
        name: 'Xianyu',
        component: () => import('@/views/xianyu/index.vue'),
        meta: { title: '闲鱼工具', xianyuRequiresAuth: true }
      }
    ]
  },
  {
    path: '/notify',
    component: () => import('@/layouts/DefaultLayout.vue'),
    children: [
      {
        path: '',
        name: 'Notify',
        component: () => import('@/views/notify/index.vue'),
        meta: { title: '消息推送' }
      }
    ]
  },
  {
    path: '/settings',
    component: () => import('@/layouts/DefaultLayout.vue'),
    children: [
      {
        path: '',
        name: 'Settings',
        component: () => import('@/views/settings/index.vue'),
        meta: { title: '系统设置' }
      },
      {
        path: 'about',
        name: 'About',
        component: () => import('@/views/settings/about.vue'),
        meta: { title: '关于' }
      }
    ]
  },
  {
    path: '/404',
    name: 'NotFound',
    component: () => import('@/views/error/404.vue'),
    meta: { title: '页面不存在' }
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/404'
  }
]
