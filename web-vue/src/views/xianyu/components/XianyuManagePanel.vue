<script setup lang="ts">
import { computed, ref } from 'vue'
import { Box, DataAnalysis, Setting, Van } from '@element-plus/icons-vue'
import type { XianyuUserProfile } from '@/api/modules/xianyu'
import XianyuManageDeliveryPanel from './XianyuManageDeliveryPanel.vue'
import XianyuManageItemsPanel from './XianyuManageItemsPanel.vue'
import XianyuManageRuntimePanel from './XianyuManageRuntimePanel.vue'

const props = defineProps<{
  currentUser?: XianyuUserProfile | null
}>()

const activeTab = ref<'items' | 'delivery' | 'runtime'>('items')
const tabs = computed(() => [
  { key: 'items' as const, label: '商品管理', hint: '同步与编辑', icon: Box, color: 'blue' },
  { key: 'delivery' as const, label: '自动发货', hint: '规则配置', icon: Van, color: 'amber' },
  { key: 'runtime' as const, label: '运行状态', hint: '执行记录', icon: DataAnalysis, color: 'emerald' },
])
const activeTabMeta = computed(() => tabs.value.find((tab) => tab.key === activeTab.value) || tabs.value[0])
const overviewStats = computed(() => [
  { label: '当前账号', value: props.currentUser?.display_name || '沿用登录态', hint: '管理中心' },
  { label: '模块数量', value: '3', hint: '商品 / 发货 / 状态' },
  { label: '默认入口', value: '商品管理', hint: '同步与编辑' },
  { label: '当前焦点', value: activeTabMeta.value?.label || '商品管理', hint: '统一操作节奏' },
])
</script>

<template>
  <section class="mg">
    <header class="mg-header">
      <div class="mg-header__left">
        <div class="mg-header__badge">
          <el-icon :size="14"><Setting /></el-icon>
          <span>管理中心</span>
        </div>
        <h2 class="mg-header__title">集中管理商品缓存、自动发货规则与运行状态</h2>
        <p class="mg-header__desc">同步本地商品、配置发货规则、查看执行记录</p>
      </div>

      <div class="mg-header__account">
        <span class="mg-header__account-label">当前账号</span>
        <strong class="mg-header__account-name">{{ currentUser?.display_name || '沿用登录态' }}</strong>
      </div>
    </header>

    <div class="mg-overview-shell">
      <div class="mg-overview__headline">
        <strong>管理中心</strong>
        <span>统一查看当前账号、默认入口与当前焦点</span>
      </div>

      <div class="mg-overview">
        <article
          v-for="stat in overviewStats"
          :key="stat.label"
          class="mg-overview__stat"
        >
          <span class="mg-overview__label">{{ stat.label }}</span>
          <strong class="mg-overview__value">{{ stat.value }}</strong>
          <span class="mg-overview__hint">{{ stat.hint }}</span>
        </article>
      </div>
    </div>

    <div class="mg-tabs-shell">
      <div class="mg-tabs-shell__head">
        <div>
          <strong>管理模块</strong>
          <p>统一管理商品缓存、发货规则与运行状态</p>
        </div>
        <div class="mg-tabs-shell__intro">
          <span class="mg-tabs-shell__intro-label">当前焦点</span>
          <strong>{{ activeTabMeta.label }}</strong>
          <span>{{ activeTabMeta.hint }}</span>
        </div>
      </div>

      <nav class="mg-tabs">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          type="button"
          class="mg-tab"
          :class="[
            `mg-tab--${tab.color}`,
            { 'mg-tab--active': activeTab === tab.key },
          ]"
          @click="activeTab = tab.key"
        >
          <div class="mg-tab__icon">
            <el-icon :size="22"><component :is="tab.icon" /></el-icon>
          </div>
          <div class="mg-tab__text">
            <strong>{{ tab.label }}</strong>
            <span>{{ tab.hint }}</span>
            <small class="mg-tab__hint">{{ activeTab === tab.key ? '默认工作区节奏' : '点击切换模块' }}</small>
          </div>
        </button>
      </nav>
    </div>

    <XianyuManageItemsPanel v-if="activeTab === 'items'" />
    <XianyuManageDeliveryPanel v-else-if="activeTab === 'delivery'" />
    <XianyuManageRuntimePanel v-else />
  </section>
</template>

<style scoped>
.mg {
  display: grid;
  gap: 20px;
  padding: 20px;
}

.mg-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 24px;
  padding: 24px 28px;
  border-radius: 16px;
  border: 1px solid rgba(var(--app-border-rgb) / 0.4);
  background:
    radial-gradient(ellipse at 0 0, rgba(var(--app-accent-rgb) / 0.1), transparent 50%),
    linear-gradient(135deg, rgba(var(--app-surface-rgb) / 0.96), rgba(var(--app-surface-alt-rgb) / 0.92));
}

.mg-header__badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border-radius: 6px;
  background: rgba(var(--app-accent-rgb) / 0.1);
  color: rgb(var(--app-accent-rgb));
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.mg-header__title {
  margin: 10px 0 4px;
  font-size: 22px;
  font-weight: 700;
  line-height: 1.3;
  color: rgb(var(--app-text-strong-rgb));
}

.mg-header__desc {
  margin: 0;
  font-size: 14px;
  color: rgb(var(--app-text-subtle-rgb));
  line-height: 1.6;
}

.mg-header__account {
  display: grid;
  gap: 4px;
  justify-items: end;
  flex-shrink: 0;
}

.mg-header__account-label {
  font-size: 12px;
  color: rgb(var(--app-text-subtle-rgb));
}

.mg-header__account-name {
  font-size: 14px;
  font-weight: 600;
  color: rgb(var(--app-text-strong-rgb));
}

.mg-overview-shell {
  display: grid;
  gap: 12px;
}

.mg-overview__headline {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.mg-overview__headline strong {
  font-size: 16px;
  font-weight: 700;
  color: rgb(var(--app-text-strong-rgb));
}

.mg-overview__headline span {
  font-size: 12px;
  color: rgb(var(--app-text-subtle-rgb));
}

.mg-overview {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.mg-overview__stat {
  display: grid;
  gap: 8px;
  padding: 16px 18px;
  border-radius: 14px;
  border: 1px solid rgba(var(--app-border-rgb) / 0.3);
  background: linear-gradient(135deg, rgba(var(--app-surface-rgb) / 0.96), rgba(var(--app-surface-alt-rgb) / 0.88));
}

.mg-overview__label,
.mg-overview__hint {
  font-size: 12px;
  color: rgb(var(--app-text-subtle-rgb));
}

.mg-overview__value {
  font-size: 18px;
  font-weight: 700;
  color: rgb(var(--app-text-strong-rgb));
  line-height: 1.2;
}

.mg-tabs-shell {
  display: grid;
  gap: 12px;
}

.mg-tabs-shell__head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
}

.mg-tabs-shell__head strong {
  font-size: 16px;
  font-weight: 700;
  color: rgb(var(--app-text-strong-rgb));
}

.mg-tabs-shell__head p {
  margin: 4px 0 0;
  font-size: 13px;
  color: rgb(var(--app-text-subtle-rgb));
}

.mg-tabs-shell__intro {
  display: grid;
  gap: 2px;
  justify-items: end;
  text-align: right;
}

.mg-tabs-shell__intro-label,
.mg-tabs-shell__intro span {
  font-size: 12px;
  color: rgb(var(--app-text-subtle-rgb));
}

.mg-tabs-shell__intro strong {
  font-size: 15px;
  font-weight: 700;
  color: rgb(var(--app-text-strong-rgb));
}

.mg-tabs {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.mg-tab {
  display: flex;
  gap: 14px;
  align-items: center;
  padding: 18px 20px;
  border-radius: 14px;
  border: 1px solid rgba(var(--app-border-rgb) / 0.36);
  background: rgba(var(--app-surface-alt-rgb) / 0.5);
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease, transform 0.15s ease;
}

.mg-tab:hover {
  transform: translateY(-1px);
  background: rgba(var(--app-surface-rgb) / 0.9);
}

.mg-tab__icon {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  border-radius: 12px;
  flex-shrink: 0;
}

.mg-tab--blue .mg-tab__icon {
  background: rgba(59, 130, 246, 0.12);
  color: rgb(59, 130, 246);
}

.mg-tab--amber .mg-tab__icon {
  background: rgba(245, 158, 11, 0.12);
  color: rgb(217, 119, 6);
}

.mg-tab--emerald .mg-tab__icon {
  background: rgba(16, 185, 129, 0.12);
  color: rgb(16, 185, 129);
}

.mg-tab__text {
  display: grid;
  gap: 2px;
}

.mg-tab__text strong {
  font-size: 15px;
  font-weight: 700;
  color: rgb(var(--app-text-strong-rgb));
}

.mg-tab__text span {
  font-size: 12px;
  color: rgb(var(--app-text-subtle-rgb));
}

.mg-tab__hint {
  font-size: 12px;
  color: rgb(var(--app-text-subtle-rgb));
}

.mg-tab--active.mg-tab--blue {
  border-color: rgba(59, 130, 246, 0.4);
  background: rgba(59, 130, 246, 0.06);
  box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.1), 0 4px 16px rgba(59, 130, 246, 0.1);
}

.mg-tab--active.mg-tab--blue .mg-tab__icon {
  background: rgba(59, 130, 246, 0.18);
}

.mg-tab--active.mg-tab--blue .mg-tab__text strong {
  color: rgb(37, 99, 235);
}

.mg-tab--active.mg-tab--amber {
  border-color: rgba(245, 158, 11, 0.4);
  background: rgba(245, 158, 11, 0.06);
  box-shadow: 0 0 0 1px rgba(245, 158, 11, 0.1), 0 4px 16px rgba(245, 158, 11, 0.1);
}

.mg-tab--active.mg-tab--amber .mg-tab__icon {
  background: rgba(245, 158, 11, 0.18);
}

.mg-tab--active.mg-tab--amber .mg-tab__text strong {
  color: rgb(180, 83, 9);
}

.mg-tab--active.mg-tab--emerald {
  border-color: rgba(16, 185, 129, 0.4);
  background: rgba(16, 185, 129, 0.06);
  box-shadow: 0 0 0 1px rgba(16, 185, 129, 0.1), 0 4px 16px rgba(16, 185, 129, 0.1);
}

.mg-tab--active.mg-tab--emerald .mg-tab__icon {
  background: rgba(16, 185, 129, 0.18);
}

.mg-tab--active.mg-tab--emerald .mg-tab__text strong {
  color: rgb(5, 150, 105);
}

@media (max-width: 768px) {
  .mg {
    padding: 12px;
    gap: 12px;
  }

  .mg-header {
    flex-direction: column;
    padding: 16px;
  }

  .mg-header__account {
    justify-items: start;
  }

  .mg-overview__headline {
    flex-direction: column;
    align-items: flex-start;
  }

  .mg-overview {
    grid-template-columns: 1fr;
  }

  .mg-tabs-shell__head {
    flex-direction: column;
    align-items: flex-start;
  }

  .mg-tabs-shell__intro {
    justify-items: start;
    text-align: left;
  }

  .mg-tabs {
    grid-template-columns: 1fr;
  }
}
</style>
