<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { RefreshRight } from '@element-plus/icons-vue'
import {
  listXianyuDeliveryExecutions,
  getXianyuDeliveryRuntimeStatus,
  type XianyuDeliveryExecutionRecord,
  type XianyuDeliveryRuntimeStatus as RuntimeStatus,
} from '@/api/modules/xianyu'

const loading = ref(false)
const status = ref<RuntimeStatus | null>(null)
const executions = ref<XianyuDeliveryExecutionRecord[]>([])
let timer: ReturnType<typeof setInterval> | null = null

const stats = computed(() => {
  const s = status.value
  if (!s) return []
  return [
    { label: '运行状态', value: s.running ? '运行中' : '未运行', accent: s.running, isStatus: true },
    { label: '启用规则', value: `${s.enabled_rule_count}`, unit: '条', accent: false },
    { label: '最近成功', value: `${s.recent_success_count}`, unit: '次', accent: false },
    { label: '最近失败', value: `${s.recent_failure_count}`, unit: '次', accent: s.recent_failure_count > 0 },
  ]
})

const timeInfo = computed(() => {
  const s = status.value
  if (!s) return []
  const items: { label: string; value: string }[] = []
  if (s.last_event_at) items.push({ label: '最近事件', value: formatTimestamp(s.last_event_at) })
  if (s.last_success_at) items.push({ label: '最近成功', value: formatTimestamp(s.last_success_at) })
  if (s.last_failure_at) items.push({ label: '最近失败', value: formatTimestamp(s.last_failure_at) })
  return items
})

async function loadStatus() {
  loading.value = true
  try {
    const [statusRes, execRes] = await Promise.all([
      getXianyuDeliveryRuntimeStatus(),
      listXianyuDeliveryExecutions({ limit: 20 }),
    ])
    status.value = statusRes.data
    executions.value = execRes.data || []
  } catch (error: any) {
    ElMessage.error(error?.message || '加载运行状态失败')
  } finally {
    loading.value = false
  }
}

function statusClass(exec: XianyuDeliveryExecutionRecord) {
  switch (exec.status) {
    case 'success': return 'mg-exec--success'
    case 'failed': return 'mg-exec--failed'
    case 'skipped': return 'mg-exec--skipped'
    default: return ''
  }
}

function statusLabel(exec: XianyuDeliveryExecutionRecord) {
  switch (exec.status) {
    case 'success': return '成功'
    case 'failed': return '失败'
    case 'skipped': return '跳过'
    default: return exec.status
  }
}

function formatTimestamp(value: number) {
  if (!value) return ''
  const date = new Date(value * 1000)
  if (Number.isNaN(date.getTime())) return ''
  return `${date.getMonth() + 1}/${date.getDate()} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

onMounted(() => {
  void loadStatus()
  timer = setInterval(() => void loadStatus(), 15000)
})

onUnmounted(() => {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
})
</script>

<template>
  <section class="mg-section">
    <div class="mg-section__head">
      <div class="mg-section__info">
        <h3>运行状态</h3>
        <p>查看自动发货运行状态与最近执行记录，每 15 秒自动刷新</p>
      </div>
      <div class="mg-section__actions">
        <el-button :loading="loading" @click="loadStatus">
          <el-icon><RefreshRight /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <div v-if="status" class="mg-runtime-summary">
      <div class="mg-stats">
        <div
          v-for="stat in stats"
          :key="stat.label"
          class="mg-stat"
          :class="{
            'mg-stat--accent': stat.accent,
            'mg-stat--status': stat.isStatus,
          }"
        >
          <span class="mg-stat__label">{{ stat.label }}</span>
          <div class="mg-stat__value-row">
            <strong
              v-if="stat.isStatus && status"
              class="mg-stat__value"
              :class="{ 'mg-stat__value--running': status.running }"
            >
              <span
                v-if="status.running"
                class="mg-stat__pulse"
              />
              {{ stat.value }}
            </strong>
            <strong v-else class="mg-stat__value">{{ stat.value }}</strong>
            <span v-if="stat.unit" class="mg-stat__unit">{{ stat.unit }}</span>
          </div>
        </div>
      </div>

      <div class="mg-runtime-summary__focus">
        <span class="mg-runtime-summary__focus-label">当前观察重点</span>
        <strong>{{ status.last_error ? '优先处理最近异常' : '运行正常，关注最新执行' }}</strong>
      </div>

      <div v-if="timeInfo.length" class="mg-time-info">
        <div
          v-for="item in timeInfo"
          :key="item.label"
          class="mg-time-info__item"
        >
          <span class="mg-time-info__label">{{ item.label }}</span>
          <span class="mg-time-info__value">{{ item.value }}</span>
        </div>
      </div>
    </div>

    <div v-if="status?.last_error" class="mg-error">
      {{ status.last_error }}
    </div>

    <div class="mg-exec-section">
      <div class="mg-exec__head">
        <div>
          <strong>最近执行记录</strong>
          <p class="mg-exec__helper">最近 20 条执行结果，自动刷新用于快速判断是否需要回到规则区处理</p>
        </div>
        <span class="mg-exec__count">{{ executions.length }} 条</span>
      </div>

      <el-empty v-if="!executions.length" description="暂无执行记录" />

      <div v-else class="mg-exec-list">
        <div
          v-for="(exec, idx) in executions"
          :key="idx"
          class="mg-exec"
          :class="statusClass(exec)"
        >
          <div class="mg-exec__left">
            <span class="mg-exec__dot" />
            <div class="mg-exec__info">
              <strong>{{ exec.rule_name }}</strong>
              <p>{{ exec.item_id }}</p>
              <span class="mg-exec__reason">{{ exec.message || '无附加说明' }}</span>
            </div>
          </div>
          <div class="mg-exec__right">
            <span class="mg-exec__status">{{ statusLabel(exec) }}</span>
            <span class="mg-exec__time">{{ formatTimestamp(exec.created_at) }}</span>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.mg-section {
  display: grid;
  gap: 16px;
}

.mg-section__head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  padding-bottom: 16px;
  border-bottom: 1px solid rgba(var(--app-border-rgb) / 0.2);
}

.mg-section__info h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: rgb(var(--app-text-strong-rgb));
}

.mg-section__info p {
  margin: 4px 0 0;
  font-size: 13px;
  color: rgb(var(--app-text-subtle-rgb));
}

.mg-section__actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.mg-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.mg-runtime-summary {
  display: grid;
  gap: 12px;
}

.mg-runtime-summary__focus {
  display: grid;
  gap: 4px;
  padding: 12px 16px;
  border-radius: 12px;
  border: 1px solid rgba(var(--app-border-rgb) / 0.3);
  background: rgba(var(--app-surface-rgb) / 0.68);
}

.mg-runtime-summary__focus-label {
  font-size: 12px;
  color: rgb(var(--app-text-subtle-rgb));
}

.mg-runtime-summary__focus strong {
  font-size: 14px;
  font-weight: 700;
  color: rgb(var(--app-text-strong-rgb));
}

.mg-stat {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 14px 16px;
  border-radius: 10px;
  border: 1px solid rgba(var(--app-border-rgb) / 0.36);
  background: rgba(var(--app-surface-alt-rgb) / 0.5);
}

.mg-stat--accent {
  border-color: rgba(239, 68, 68, 0.24);
  background: rgba(239, 68, 68, 0.06);
}

.mg-stat--status.mg-stat--accent {
  border-color: rgba(34, 197, 94, 0.24);
  background: rgba(34, 197, 94, 0.06);
}

.mg-stat__label {
  font-size: 12px;
  font-weight: 500;
  color: rgb(var(--app-text-subtle-rgb));
}

.mg-stat__value-row {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.mg-stat__value {
  font-size: 20px;
  font-weight: 700;
  line-height: 1.1;
  color: rgb(var(--app-text-strong-rgb));
  font-variant-numeric: tabular-nums;
}

.mg-stat--accent .mg-stat__value {
  color: rgb(220, 38, 38);
}

.mg-stat--status.mg-stat--accent .mg-stat__value {
  color: rgb(22, 163, 74);
}

.mg-stat__value--running {
  display: flex;
  align-items: center;
  gap: 8px;
}

.mg-stat__pulse {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: rgb(34, 197, 94);
  animation: mg-pulse 2s ease-in-out infinite;
}

@keyframes mg-pulse {
  0%, 100% { opacity: 1; box-shadow: 0 0 4px rgba(34, 197, 94, 0.4); }
  50% { opacity: 0.5; box-shadow: 0 0 8px rgba(34, 197, 94, 0.6); }
}

.mg-stat__unit {
  font-size: 13px;
  color: rgb(var(--app-text-subtle-rgb));
}

.mg-time-info {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding: 12px 16px;
  border-radius: 10px;
  border: 1px solid rgba(var(--app-border-rgb) / 0.3);
  background: rgba(var(--app-surface-rgb) / 0.6);
}

.mg-time-info__item {
  display: flex;
  gap: 6px;
  align-items: center;
}

.mg-time-info__label {
  font-size: 12px;
  color: rgb(var(--app-text-subtle-rgb));
}

.mg-time-info__value {
  font-size: 13px;
  font-weight: 500;
  color: rgb(var(--app-text-strong-rgb));
}

.mg-time-info__item + .mg-time-info__item::before {
  content: '·';
  margin-right: 12px;
  color: rgb(var(--app-border-rgb));
}

.mg-error {
  padding: 12px 16px;
  border-radius: 8px;
  background: rgba(239, 68, 68, 0.06);
  border: 1px solid rgba(239, 68, 68, 0.15);
  color: rgb(185, 28, 28);
  font-size: 13px;
  line-height: 1.6;
}

.mg-exec-section {
  display: grid;
  gap: 12px;
}

.mg-exec__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.mg-exec__head strong {
  font-size: 15px;
  font-weight: 600;
  color: rgb(var(--app-text-strong-rgb));
}

.mg-exec__helper {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: rgb(var(--app-text-subtle-rgb));
}

.mg-exec__count {
  padding: 1px 8px;
  border-radius: 4px;
  background: rgba(var(--app-accent-rgb) / 0.1);
  font-size: 12px;
  font-weight: 600;
  color: rgb(var(--app-accent-rgb));
}

.mg-exec-list {
  display: grid;
  gap: 8px;
}

.mg-exec {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  padding: 10px 14px;
  border-radius: 8px;
  border: 1px solid rgba(var(--app-border-rgb) / 0.3);
  background: rgba(var(--app-surface-rgb) / 0.6);
}

.mg-exec__left {
  display: flex;
  gap: 10px;
  align-items: center;
  min-width: 0;
}

.mg-exec__info {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.mg-exec__reason {
  font-size: 12px;
  line-height: 1.5;
  color: rgb(var(--app-text-subtle-rgb));
}

.mg-exec__dot {
  flex-shrink: 0;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: rgb(var(--app-text-subtle-rgb));
}

.mg-exec--success .mg-exec__dot {
  background: rgb(34, 197, 94);
}

.mg-exec--failed .mg-exec__dot {
  background: rgb(239, 68, 68);
}

.mg-exec--skipped .mg-exec__dot {
  background: rgb(234, 179, 8);
}

.mg-exec__info {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.mg-exec__info strong {
  font-size: 13px;
  font-weight: 600;
  color: rgb(var(--app-text-strong-rgb));
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mg-exec__info p {
  margin: 0;
  font-size: 12px;
  color: rgb(var(--app-text-subtle-rgb));
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mg-exec__right {
  display: grid;
  gap: 2px;
  justify-items: end;
  flex-shrink: 0;
}

.mg-exec__status {
  font-size: 12px;
  font-weight: 600;
}

.mg-exec--success .mg-exec__status {
  color: rgb(22, 163, 74);
}

.mg-exec--failed .mg-exec__status {
  color: rgb(220, 38, 38);
}

.mg-exec--skipped .mg-exec__status {
  color: rgb(161, 98, 7);
}

.mg-exec__time {
  font-size: 11px;
  color: rgb(var(--app-text-subtle-rgb));
}

@media (max-width: 768px) {
  .mg-stats {
    grid-template-columns: 1fr 1fr;
  }

  .mg-exec {
    flex-direction: column;
    align-items: flex-start;
  }

  .mg-exec__right {
    justify-items: start;
  }
}

@media (prefers-reduced-motion: reduce) {
  .mg-stat__pulse {
    animation: none;
  }
}
</style>
