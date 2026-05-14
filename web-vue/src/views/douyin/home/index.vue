<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { VideoPlay, User, Search, VideoCamera } from '@element-plus/icons-vue'
import { getStatus } from '@/api'

const router = useRouter()

const status = ref<{ cookie_configured: boolean; live_cookie_configured?: boolean }>({
  cookie_configured: false
})

onMounted(async () => {
  await loadStatus()
})

async function loadStatus() {
  try {
    const res = await getStatus()
    if (res && res.data) {
      status.value = res.data
    }
  } catch (err) {
    // ignore
  }
}

const features = [
  {
    icon: VideoPlay,
    title: '作品解析',
    desc: '解析视频详情，获取评论，无水印下载',
    path: '/douyin/video',
    accent: 'emerald'
  },
  {
    icon: User,
    title: '用户查询',
    desc: '查看用户信息、作品列表和点赞',
    path: '/douyin/user',
    accent: 'teal'
  },
  {
    icon: Search,
    title: '内容搜索',
    desc: '搜索视频、用户等热门内容',
    path: '/douyin/search',
    accent: 'cyan'
  },
  {
    icon: VideoCamera,
    title: '直播间',
    desc: '获取直播间信息和实时弹幕',
    path: '/douyin/live',
    accent: 'lime'
  }
]

const quickStats = [
  { label: '已解析', value: '1,234', suffix: '个视频' },
  { label: '已下载', value: '567', suffix: '个文件' },
  { label: '成功率', value: '99.2', suffix: '%' }
]
</script>

<template>
  <div class="douyin-home">
    <!-- 欢迎横幅卡片 -->
    <div class="card welcome-card">
      <div class="welcome-glow" />
      <div class="welcome-content">
        <h1 class="welcome-title">抖音数据解析工具</h1>
        <p class="welcome-desc">专业的抖音内容解析与数据采集工具，支持视频、用户、直播等多种数据解析</p>
        <div class="welcome-tags">
          <el-tag :type="status?.cookie_configured ? 'success' : 'warning'" size="small">
            Cookie: {{ status?.cookie_configured ? '已配置' : '未配置' }}
          </el-tag>
          <el-tag v-if="status?.live_cookie_configured" type="success" size="small">
            直播Cookie: 已配置
          </el-tag>
        </div>
      </div>
    </div>

    <!-- 功能卡片网格 -->
    <div class="feature-grid">
      <div
        v-for="feature in features"
        :key="feature.path"
        class="card feature-card"
        :class="`feature-card--${feature.accent}`"
        @click="router.push(feature.path)"
      >
        <div class="feature-card__icon">
          <el-icon :size="24"><component :is="feature.icon" /></el-icon>
        </div>
        <div class="feature-card__body">
          <h3 class="feature-card__title">{{ feature.title }}</h3>
          <p class="feature-card__desc">{{ feature.desc }}</p>
        </div>
        <div class="feature-card__arrow">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M6 3l5 5-5 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </div>
      </div>
    </div>

    <!-- 底部卡片区域 -->
    <div class="bottom-grid">
      <!-- 统计卡片 -->
      <div class="card stats-card">
        <div class="card-header">
          <h3 class="card-title">使用统计</h3>
        </div>
        <div class="stats-list">
          <div v-for="stat in quickStats" :key="stat.label" class="stat-row">
            <span class="stat-label">{{ stat.label }}</span>
            <div class="stat-value-wrap">
              <span class="stat-value">{{ stat.value }}</span>
              <span class="stat-suffix">{{ stat.suffix }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 快速开始卡片 -->
      <div class="card guide-card">
        <div class="card-header">
          <h3 class="card-title">快速开始</h3>
        </div>
        <div class="guide-grid">
          <div v-for="(step, i) in 4" :key="i" class="guide-step">
            <span class="guide-step__num">{{ i + 1 }}</span>
            <div class="guide-step__text">
              <p class="guide-step__title">{{ ['配置 Cookie', '复制分享链接', '粘贴解析', '下载保存'][i] }}</p>
              <p class="guide-step__desc">{{ ['前往设置页面配置抖音 Cookie', '在抖音 APP 分享复制链接', '粘贴链接即可解析数据', '无水印下载视频或图片'][i] }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.douyin-home {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  animation: homeFadeIn 0.4s ease;
}

@keyframes homeFadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

/* 通用卡片样式 */
.card {
  background: rgba(var(--app-surface-rgb) / 0.96);
  border: 1px solid rgba(var(--app-border-strong-rgb) / 0.45);
  border-radius: 16px;
  box-shadow:
    0 1px 2px rgba(var(--app-shadow-rgb) / 0.06),
    0 4px 12px rgba(var(--app-shadow-rgb) / 0.08),
    0 12px 28px rgba(var(--app-shadow-rgb) / 0.06);
  overflow: visible;
}

.card-header {
  padding: 0 0 16px 0;
  margin-bottom: 16px;
  border-bottom: 1px solid rgba(var(--app-border-strong-rgb) / 0.3);
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: rgb(var(--app-text-strong-rgb));
  margin: 0;
}

/* 欢迎卡片 */
.welcome-card {
  position: relative;
  padding: 32px 36px;
}

.welcome-glow {
  position: absolute;
  top: -40%;
  right: -10%;
  width: 320px;
  height: 320px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(var(--primary-color-rgb) / 0.12), transparent 70%);
  pointer-events: none;
}

.welcome-content {
  position: relative;
  z-index: 1;
}

.welcome-title {
  font-size: 24px;
  font-weight: 700;
  color: rgb(var(--app-text-strong-rgb));
  margin: 0 0 10px;
  letter-spacing: -0.02em;
}

.welcome-desc {
  font-size: 14px;
  color: rgb(var(--app-text-muted-rgb));
  margin: 0 0 16px;
  line-height: 1.7;
}

.welcome-tags {
  display: flex;
  gap: 10px;
}

/* 功能卡片网格 */
.feature-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.feature-card {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 22px;
  cursor: pointer;
  transition: all 0.25s ease;
  position: relative;
}

.feature-card:hover {
  transform: translateY(-3px);
  box-shadow:
    0 4px 12px rgba(var(--app-shadow-rgb) / 0.14),
    0 12px 32px rgba(var(--app-shadow-rgb) / 0.16);
}

.feature-card__icon {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.feature-card--emerald .feature-card__icon {
  background: rgba(var(--primary-color-rgb) / 0.14);
  color: rgb(var(--primary-color-rgb));
}

.feature-card--teal .feature-card__icon {
  background: rgba(var(--app-accent-soft-rgb) / 0.14);
  color: rgb(var(--app-accent-soft-rgb));
}

.feature-card--cyan .feature-card__icon {
  background: rgba(var(--app-accent-alt-rgb) / 0.14);
  color: rgb(var(--app-accent-alt-rgb));
}

.feature-card--lime .feature-card__icon {
  background: rgba(132 204 22, 0.14);
  color: rgb(132 204 22);
}

.feature-card__title {
  font-size: 16px;
  font-weight: 600;
  color: rgb(var(--app-text-strong-rgb));
  margin: 0;
}

.feature-card__desc {
  font-size: 13px;
  color: rgb(var(--app-text-muted-rgb));
  margin: 0;
  line-height: 1.6;
}

.feature-card__arrow {
  position: absolute;
  top: 22px;
  right: 18px;
  color: rgb(var(--app-text-subtle-rgb));
  transition: all 0.25s ease;
}

.feature-card:hover .feature-card__arrow {
  color: rgb(var(--primary-color-rgb));
  transform: translateX(3px);
}

/* 底部卡片网格 */
.bottom-grid {
  display: grid;
  grid-template-columns: 1fr 2fr;
  gap: 16px;
}

.stats-card,
.guide-card {
  padding: 24px;
}

/* 统计卡片 */
.stats-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.stat-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-radius: 10px;
  background: rgba(var(--app-surface-alt-rgb) / 0.8);
  border: 1px solid rgba(var(--app-border-strong-rgb) / 0.2);
  box-shadow: 0 2px 6px rgba(var(--app-shadow-rgb) / 0.04);
}

.stat-label {
  font-size: 13px;
  color: rgb(var(--app-text-muted-rgb));
}

.stat-value-wrap {
  text-align: right;
}

.stat-value {
  font-size: 16px;
  font-weight: 600;
  color: rgb(var(--app-text-strong-rgb));
}

.stat-suffix {
  font-size: 12px;
  color: rgb(var(--app-text-subtle-rgb));
  margin-left: 4px;
}

/* 快速开始卡片 */
.guide-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.guide-step {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  padding: 14px;
  border-radius: 12px;
  background: rgba(var(--app-surface-alt-rgb) / 0.8);
  border: 1px solid rgba(var(--app-border-strong-rgb) / 0.2);
  box-shadow: 0 2px 6px rgba(var(--app-shadow-rgb) / 0.04);
  transition: all 0.2s ease;
}

.guide-step:hover {
  background: rgba(var(--app-surface-alt-rgb) / 0.9);
  border-color: rgba(var(--app-border-rgb) / 0.6);
}

.guide-step__num {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: rgba(var(--primary-color-rgb) / 0.14);
  color: rgb(var(--primary-color-rgb));
  font-size: 13px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.guide-step__title {
  font-size: 14px;
  font-weight: 500;
  color: rgb(var(--app-text-strong-rgb));
  margin: 0 0 4px;
}

.guide-step__desc {
  font-size: 12px;
  color: rgb(var(--app-text-subtle-rgb));
  margin: 0;
  line-height: 1.6;
}

/* 响应式 */
@media (max-width: 1024px) {
  .feature-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .douyin-home {
    padding: 16px;
  }

  .feature-grid {
    grid-template-columns: 1fr;
  }

  .bottom-grid {
    grid-template-columns: 1fr;
  }

  .guide-grid {
    grid-template-columns: 1fr;
  }
}
</style>
