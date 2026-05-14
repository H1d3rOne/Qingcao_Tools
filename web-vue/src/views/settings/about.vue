<script setup lang="ts">
import { ref } from 'vue'

const appInfo = {
  name: 'Qingcao_Tools',
  version: '1.0.0',
  author: '青草团队',
  description: '一款集成多种实用工具的工具箱应用，目前支持抖音解析、夸克网盘等功能。',
  features: [
    '抖音视频/用户/直播数据解析',
    '夸克网盘资源转存与管理',
    '优雅的深色主题界面',
    '持续更新迭代'
  ],
  tech: [
    { name: 'Vue 3', desc: '渐进式 JavaScript 框架' },
    { name: 'TypeScript', desc: '类型安全的 JavaScript 超集' },
    { name: 'Element Plus', desc: 'Vue 3 组件库' },
    { name: 'FastAPI', desc: '现代 Python Web 框架' },
    { name: 'Tailwind CSS', desc: '原子化 CSS 框架' }
  ]
}
</script>

<template>
  <div class="about-page max-w-4xl mx-auto">
    <!-- Logo 和标题 -->
    <div class="text-center mb-8">
      <div class="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 shadow-lg shadow-emerald-500/30 mb-4">
        <span class="text-white font-bold text-3xl">Q</span>
      </div>
      <h1 class="text-3xl font-bold text-white mb-2">
        {{ appInfo.name }}
      </h1>
      <p class="text-gray-400">
        v{{ appInfo.version }}
      </p>
    </div>

    <!-- 描述 -->
    <div class="bg-dark-card rounded-xl border border-gray-700/50 p-6 mb-6">
      <p class="text-gray-300 leading-relaxed">
        {{ appInfo.description }}
      </p>
    </div>

    <!-- 功能特点 -->
    <div class="bg-dark-card rounded-xl border border-gray-700/50 p-6 mb-6">
      <h2 class="text-lg font-semibold text-white mb-4">
        功能特点
      </h2>
      <ul class="grid grid-cols-2 gap-3">
        <li
          v-for="(feature, index) in appInfo.features"
          :key="index"
          class="flex items-center text-gray-300"
        >
          <el-icon class="text-emerald-400 mr-2">
            <i class="i-ep-check" />
          </el-icon>
          {{ feature }}
        </li>
      </ul>
    </div>

    <!-- 技术栈 -->
    <div class="bg-dark-card rounded-xl border border-gray-700/50 p-6 mb-6">
      <h2 class="text-lg font-semibold text-white mb-4">
        技术栈
      </h2>
      <div class="grid grid-cols-2 gap-4">
        <div
          v-for="tech in appInfo.tech"
          :key="tech.name"
          class="flex items-center p-3 bg-dark-lighter/50 rounded-lg"
        >
          <div class="w-10 h-10 rounded-lg bg-emerald-500/20 flex items-center justify-center mr-3">
            <el-icon class="text-emerald-400">
              <i class="i-ep-code" />
            </el-icon>
          </div>
          <div>
            <div class="text-white font-medium">
              {{ tech.name }}
            </div>
            <div class="text-gray-500 text-xs">
              {{ tech.desc }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 底部信息 -->
    <div class="text-center text-gray-500 text-sm">
      <p>© 2024 {{ appInfo.author }}. All rights reserved.</p>
      <p class="mt-1">
        <a
          href="#"
          class="text-emerald-400 hover:text-emerald-300"
        >GitHub</a>
        <span class="mx-2">|</span>
        <a
          href="#"
          class="text-emerald-400 hover:text-emerald-300"
        >问题反馈</a>
      </p>
    </div>
  </div>
</template>
