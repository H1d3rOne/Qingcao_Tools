<script setup lang="ts">
const appInfo = {
  name: '青草工具箱',
  version: '2.0.0',
  author: 'H1d3rOne',
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
      <div class="about-logo inline-flex items-center justify-center w-28 h-28 rounded-3xl mb-4 overflow-hidden">
        <img
          class="w-40 h-40"
          src="/qingcao-logo.svg"
          alt="青草工具箱 Logo"
        >
      </div>
      <h1 class="about-brand-title text-4xl font-bold text-white mb-2">
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
          href="https://github.com/H1d3rOne/Qingcao_Tools"
          target="_blank"
          rel="noopener noreferrer"
          class="text-emerald-400 hover:text-emerald-300"
        >GitHub</a>
        <span class="mx-2">|</span>
        <a
          href="https://github.com/H1d3rOne/Qingcao_Tools/issues"
          target="_blank"
          rel="noopener noreferrer"
          class="text-emerald-400 hover:text-emerald-300"
        >问题反馈</a>
      </p>
    </div>
  </div>
</template>


<style scoped>
.about-brand-title {
  color: rgb(var(--primary-color-rgb));
  background: linear-gradient(135deg, rgb(var(--primary-deep-rgb)) 0%, rgb(var(--primary-color-rgb)) 46%, rgb(var(--app-accent-alt-rgb)) 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  font-family: 'Yuanti SC', 'PingFang SC', 'Microsoft YaHei UI', 'Microsoft YaHei', 'Noto Sans CJK SC', 'Source Han Sans SC', sans-serif;
  font-weight: 900;
  letter-spacing: 0.14em;
  line-height: 1.15;
  text-shadow:
    0 5px 20px rgba(var(--primary-color-rgb) / 0.18),
    0 1px 0 rgba(var(--utility-white-rgb) / 0.3);
}

.about-logo {
  position: relative;
  background:
    linear-gradient(145deg, rgba(var(--utility-white-rgb) / 0.72), rgba(var(--app-surface-rgb) / 0.34)),
    radial-gradient(circle at 28% 18%, rgba(var(--app-accent-soft-rgb) / 0.34), transparent 48%);
  border: 1px solid rgba(var(--primary-color-rgb) / 0.24);
  box-shadow:
    0 20px 48px rgba(var(--primary-color-rgb) / 0.2),
    inset 0 1px 0 rgba(var(--utility-white-rgb) / 0.72);
}

.about-logo::after {
  content: '';
  position: absolute;
  inset: 3px;
  border-radius: 26px;
  pointer-events: none;
  box-shadow: inset 0 0 0 1px rgba(var(--utility-white-rgb) / 0.34);
}

.about-logo img {
  position: relative;
  z-index: 1;
  filter: drop-shadow(0 10px 18px rgba(var(--app-shadow-rgb) / 0.18));
}
</style>
