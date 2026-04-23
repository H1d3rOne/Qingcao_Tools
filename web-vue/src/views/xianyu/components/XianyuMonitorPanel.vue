<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown, Bell, Delete, EditPen, Plus, RefreshRight, SwitchButton, VideoPlay } from '@element-plus/icons-vue'
import {
  createXianyuMonitorTask,
  deleteXianyuMonitorTask,
  getXianyuMonitorHits,
  listXianyuMonitorTasks,
  runXianyuMonitorTask,
  toggleXianyuMonitorTask,
  updateXianyuMonitorTask,
  type XianyuMonitorHit,
  type XianyuMonitorTask,
  type XianyuMonitorTaskCreate,
  type XianyuUserProfile,
} from '@/api/modules/xianyu'

type MonitorPreset = Partial<XianyuMonitorTaskCreate>

interface MonitorFormState {
  name: string
  keyword: string
  page: number
  page_size: number
  sort_field: string
  sort_value: string
  min_price: number | null
  max_price: number | null
  interval_seconds: number
  prop_values_text: string
  // 触发条件
  max_hits: number | null
  published_within_hours: number | null
  // 执行动作
  webhook_url: string
  contact_seller_enabled: boolean
}

const props = defineProps<{
  currentUser?: XianyuUserProfile | null
  searchPreset?: MonitorPreset | null
  initialTaskId?: string
}>()

const loading = ref(false)
const saving = ref(false)
const hitsLoading = ref(false)
const hitsExpanded = ref(false)
const activeTaskId = ref('')
const dialogVisible = ref(false)
const editingTaskId = ref('')
const runningTaskIds = ref<string[]>([])
const tasks = ref<XianyuMonitorTask[]>([])
const activeHits = ref<XianyuMonitorHit[]>([])

const formState = reactive<MonitorFormState>({
  name: '',
  keyword: '',
  page: 1,
  page_size: 20,
  sort_field: '',
  sort_value: '',
  min_price: null,
  max_price: null,
  interval_seconds: 180,
  prop_values_text: '{}',
  max_hits: null,
  published_within_hours: null,
  webhook_url: '',
  contact_seller_enabled: false,
})

const activeTask = computed(() => tasks.value.find((item) => item.id === activeTaskId.value) || null)
const enabledTaskCount = computed(() => tasks.value.filter((item) => item.enabled).length)
const latestHitCount = computed(() => tasks.value.reduce((sum, item) => sum + item.latest_hits.length, 0))
const monitorStats = computed(() => [
  { label: '监控任务', value: `${tasks.value.length}`, unit: '个', accent: false },
  { label: '启用中', value: `${enabledTaskCount.value}`, unit: '个', accent: true },
  { label: '最近命中', value: `${latestHitCount.value}`, unit: '条', accent: false },
  {
    label: '账号状态',
    value: props.currentUser?.display_name ? '已登录' : '沿用登录态',
    unit: props.currentUser?.display_name || '',
    accent: !!props.currentUser?.display_name,
  },
])
const canUseSearchPreset = computed(() => Boolean(props.searchPreset?.keyword?.trim()))
const dialogTitle = computed(() => (editingTaskId.value ? '编辑监控任务' : '新建监控任务'))

watch(activeTaskId, async (taskId) => {
  hitsExpanded.value = false
  if (!taskId) {
    activeHits.value = []
    return
  }
  await loadHits(taskId)
})

watch(() => props.initialTaskId, async (taskId) => {
  if (!taskId) return
  await loadTasks(taskId)
  const task = tasks.value.find((t) => t.id === taskId)
  if (task) {
    openEditDialog(task)
  }
})

function formatTimestamp(value: number) {
  if (!value) return '未执行'
  const date = new Date(value * 1000)
  if (Number.isNaN(date.getTime())) return '未知时间'
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

function formatInterval(seconds: number) {
  if (seconds < 60) return `${seconds} 秒`
  if (seconds % 60 === 0) return `${seconds / 60} 分钟`
  return `${Math.floor(seconds / 60)} 分 ${seconds % 60} 秒`
}

function normalizeSortLabel(task: Pick<XianyuMonitorTask, 'sort_field' | 'sort_value'>) {
  if (task.sort_field === 'price' && task.sort_value === 'asc') return '价格升序'
  if (task.sort_field === 'price' && task.sort_value === 'desc') return '价格降序'
  return '综合排序'
}

function buildTaskSummary(task: XianyuMonitorTask) {
  const parts = [
    `每次拉取 ${task.page_size} 条`,
    normalizeSortLabel(task),
  ]

  if (task.published_within_hours) {
    parts.push(`近 ${task.published_within_hours} 小时`)
  }

  if (task.max_hits) {
    parts.push(`最多 ${task.max_hits} 命中`)
  }

  parts.push(`已见商品 ${task.seen_item_ids.length}`)

  return parts.join(' · ')
}

function buildTaskPriceRange(task: Pick<XianyuMonitorTask, 'min_price' | 'max_price'>) {
  if (task.min_price !== null && task.min_price !== undefined && task.max_price !== null && task.max_price !== undefined) {
    return `价格 ¥${task.min_price} - ¥${task.max_price}`
  }

  if (task.min_price !== null && task.min_price !== undefined) {
    return `最低 ¥${task.min_price}`
  }

  if (task.max_price !== null && task.max_price !== undefined) {
    return `最高 ¥${task.max_price}`
  }

  return '价格不限'
}

function formatPropValues(propValues: Record<string, string>) {
  const entries = Object.entries(propValues || {})
  if (!entries.length) return []
  return entries.map(([key, value]) => `${key}:${value}`)
}

function resetForm() {
  formState.name = ''
  formState.keyword = ''
  formState.page = 1
  formState.page_size = 20
  formState.sort_field = ''
  formState.sort_value = ''
  formState.min_price = null
  formState.max_price = null
  formState.interval_seconds = 180
  formState.prop_values_text = '{}'
  formState.max_hits = null
  formState.published_within_hours = null
  formState.webhook_url = ''
  formState.contact_seller_enabled = false
  editingTaskId.value = ''
}

function applyPreset(preset?: MonitorPreset | null) {
  formState.name = `${preset?.name?.trim() || preset?.keyword?.trim() || '闲鱼'}监控`
  formState.keyword = preset?.keyword?.trim() || ''
  formState.page = preset?.page || 1
  formState.page_size = preset?.page_size || 20
  formState.sort_field = preset?.sort_field || ''
  formState.sort_value = preset?.sort_value || ''
  formState.min_price = preset?.min_price ?? null
  formState.max_price = preset?.max_price ?? null
  formState.interval_seconds = preset?.interval_seconds || 180
  formState.prop_values_text = JSON.stringify(preset?.prop_values || {}, null, 2)
  formState.max_hits = preset?.max_hits ?? null
  formState.published_within_hours = preset?.published_within_hours ?? null
  formState.webhook_url = preset?.webhook_url || ''
  formState.contact_seller_enabled = preset?.contact_seller_enabled || false
}

function openCreateDialog() {
  resetForm()
  dialogVisible.value = true
}

function openDialogWithSearchPreset() {
  resetForm()
  applyPreset(props.searchPreset)
  dialogVisible.value = true
}

function openEditDialog(task: XianyuMonitorTask) {
  editingTaskId.value = task.id
  formState.name = task.name
  formState.keyword = task.keyword
  formState.page = task.page
  formState.page_size = task.page_size
  formState.sort_field = task.sort_field
  formState.sort_value = task.sort_value
  formState.min_price = task.min_price ?? null
  formState.max_price = task.max_price ?? null
  formState.interval_seconds = task.interval_seconds
  formState.prop_values_text = JSON.stringify(task.prop_values || {}, null, 2)
  formState.max_hits = task.max_hits ?? null
  formState.published_within_hours = task.published_within_hours ?? null
  formState.webhook_url = task.webhook_url || ''
  formState.contact_seller_enabled = task.contact_seller_enabled || false
  dialogVisible.value = true
}

function handleSortValueChange(value: string) {
  const [sortField = '', sortValue = ''] = String(value || ':').split(':')
  formState.sort_field = sortField
  formState.sort_value = sortValue
}

function openHitDetail(url: string) {
  if (!url) return
  window.open(url, '_blank', 'noopener,noreferrer')
}

function toggleHitsPreview() {
  hitsExpanded.value = !hitsExpanded.value
}

function getErrorMessage(err: unknown, fallback: string) {
  return err instanceof Error ? err.message : fallback
}

function buildFormPayload() {
  const keyword = formState.keyword.trim()
  const name = formState.name.trim() || `${keyword}监控`
  const minPrice = formState.min_price ?? null
  const maxPrice = formState.max_price ?? null

  if (!keyword) {
    throw new Error('请输入监控关键词')
  }

  let propValues: Record<string, string> = {}
  if (formState.prop_values_text.trim()) {
    const parsed = JSON.parse(formState.prop_values_text)
    if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
      throw new Error('筛选属性必须是 JSON 对象')
    }
    propValues = Object.fromEntries(
      Object.entries(parsed).map(([key, value]) => [String(key), String(value)]),
    )
  }

  const payload: XianyuMonitorTaskCreate = {
    name,
    keyword,
    page: formState.page,
    page_size: formState.page_size,
    sort_field: formState.sort_field,
    sort_value: formState.sort_value,
    prop_values: propValues,
    min_price: minPrice,
    max_price: maxPrice,
    interval_seconds: formState.interval_seconds,
    max_hits: formState.max_hits,
    published_within_hours: formState.published_within_hours,
    webhook_url: formState.webhook_url.trim(),
    contact_seller_enabled: formState.contact_seller_enabled,
  }

  if (minPrice !== null && maxPrice !== null && minPrice > maxPrice) {
    payload.min_price = maxPrice
    payload.max_price = minPrice
  }

  return payload
}

async function loadTasks(preferredTaskId = '') {
  loading.value = true
  try {
    const response = await listXianyuMonitorTasks()
    tasks.value = response.data || []

    if (!tasks.value.length) {
      activeTaskId.value = ''
      activeHits.value = []
      return
    }

    const nextTaskId = preferredTaskId && tasks.value.some((item) => item.id === preferredTaskId)
      ? preferredTaskId
      : activeTaskId.value && tasks.value.some((item) => item.id === activeTaskId.value)
        ? activeTaskId.value
        : tasks.value[0].id

    activeTaskId.value = nextTaskId
  } finally {
    loading.value = false
  }
}

async function loadHits(taskId: string) {
  hitsLoading.value = true
  try {
    const response = await getXianyuMonitorHits(taskId)
    activeHits.value = response.data || []
  } finally {
    hitsLoading.value = false
  }
}

async function handleSubmit() {
  try {
    const payload = buildFormPayload()
    saving.value = true

    if (editingTaskId.value) {
      await updateXianyuMonitorTask(editingTaskId.value, payload)
      ElMessage.success('监控任务已更新')
      await loadTasks(editingTaskId.value)
    } else {
      const response = await createXianyuMonitorTask(payload)
      ElMessage.success('监控任务已创建')
      await loadTasks(response.data.id)
    }

    dialogVisible.value = false
  } catch (err: unknown) {
    ElMessage.error(getErrorMessage(err, '保存监控任务失败'))
  } finally {
    saving.value = false
  }
}

async function handleToggle(task: XianyuMonitorTask) {
  try {
    const response = await toggleXianyuMonitorTask(task.id)
    const nextTask = response.data
    tasks.value = tasks.value.map((item) => (item.id === nextTask.id ? nextTask : item))
    if (activeTaskId.value === nextTask.id) {
      activeHits.value = nextTask.latest_hits || activeHits.value
    }
    ElMessage.success(nextTask.enabled ? '监控已启用' : '监控已暂停')
  } catch (err: unknown) {
    ElMessage.error(getErrorMessage(err, '切换监控状态失败'))
  }
}

async function handleRun(task: XianyuMonitorTask) {
  if (runningTaskIds.value.includes(task.id)) return

  runningTaskIds.value = [...runningTaskIds.value, task.id]
  try {
    const response = await runXianyuMonitorTask(task.id)
    const nextTask = response.data
    tasks.value = tasks.value.map((item) => (item.id === nextTask.id ? nextTask : item))
    if (activeTaskId.value === nextTask.id) {
      activeHits.value = nextTask.latest_hits || []
    }
    ElMessage.success(`手动执行完成，新增 ${nextTask.latest_hits.length} 条最近命中`)
  } catch (err: unknown) {
    ElMessage.error(getErrorMessage(err, '执行监控任务失败'))
  } finally {
    runningTaskIds.value = runningTaskIds.value.filter((item) => item !== task.id)
  }
}

async function handleDelete(task: XianyuMonitorTask) {
  try {
    await ElMessageBox.confirm(`确认删除监控任务"${task.name}"吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })

    await deleteXianyuMonitorTask(task.id)
    ElMessage.success('监控任务已删除')
    await loadTasks(activeTaskId.value === task.id ? '' : activeTaskId.value)
  } catch (err: unknown) {
    if (err === 'cancel' || err === 'close') return
    ElMessage.error(getErrorMessage(err, '删除监控任务失败'))
  }
}

onMounted(async () => {
  await loadTasks()
})
</script>

<template>
  <section class="mp">
    <header class="mp-header">
      <div class="mp-header__left">
        <div class="mp-header__badge">
          <el-icon :size="14"><Bell /></el-icon>
          <span>关键词监控</span>
        </div>
        <h2 class="mp-header__title">持续轮询关键词，自动沉淀命中商品</h2>
        <p class="mp-header__desc">复用搜索关键词、排序和筛选条件，支持手动触发与后台定时轮询</p>
      </div>

      <div class="mp-header__actions">
        <el-button
          type="primary"
          @click="openCreateDialog"
        >
          <el-icon><Plus /></el-icon>
          新建监控
        </el-button>
        <el-button
          :disabled="!canUseSearchPreset"
          @click="openDialogWithSearchPreset"
        >
          从搜索创建
        </el-button>
        <el-button
          :loading="loading"
          @click="loadTasks(activeTaskId)"
        >
          <el-icon><RefreshRight /></el-icon>
          刷新
        </el-button>
      </div>
    </header>

    <div class="mp-stats">
      <div
        v-for="stat in monitorStats"
        :key="stat.label"
        class="mp-stat"
        :class="{ 'mp-stat--accent': stat.accent }"
      >
        <span class="mp-stat__label">{{ stat.label }}</span>
        <div class="mp-stat__value-row">
          <strong class="mp-stat__value">{{ stat.value }}</strong>
          <span
            v-if="stat.unit"
            class="mp-stat__unit"
          >{{ stat.unit }}</span>
        </div>
      </div>
    </div>

    <div class="mp-body mp-body--balanced">
      <aside class="mp-sidebar mp-panel--stretch">
        <div class="mp-sidebar__head">
          <strong>任务列表</strong>
          <span class="mp-sidebar__count">{{ tasks.length }} 个</span>
        </div>

        <div
          v-if="tasks.length"
          class="mp-task-list mp-task-list--fill mp-task-list--compact"
        >
          <button
            v-for="task in tasks"
            :key="task.id"
            type="button"
            class="mp-task mp-task--framed mp-task--compact"
            :class="{
              'mp-task--active': activeTaskId === task.id,
              'mp-task--running': task.enabled,
              'mp-task--error': task.last_status === 'error'
            }"
            @click="activeTaskId = task.id"
          >
            <div class="mp-task__top">
              <div class="mp-task__name-row">
                <span
                  class="mp-task__dot"
                  :class="{
                    'mp-task__dot--on': task.enabled && task.last_status !== 'error',
                    'mp-task__dot--err': task.last_status === 'error'
                  }"
                />
                <strong
                  class="mp-task__name"
                  :class="{ 'mp-task__name--active': activeTaskId === task.id }"
                >{{ task.name }}</strong>
              </div>
              <span class="mp-task__status">
                {{ task.last_status === 'error' ? '异常' : task.enabled ? '运行中' : '已暂停' }}
              </span>
            </div>

            <p class="mp-task__keyword">{{ task.keyword }}</p>

            <div
              v-if="formatPropValues(task.prop_values).length"
              class="mp-task__chips"
            >
              <span
                v-for="item in formatPropValues(task.prop_values)"
                :key="item"
              >{{ item }}</span>
            </div>

            <div class="mp-task__footer">
              <span>{{ formatTimestamp(task.last_run_at) }}</span>
              <span>{{ task.latest_hits.length }} 命中</span>
            </div>
          </button>
        </div>

        <el-empty
          v-else-if="!loading"
          description="还没有监控任务"
        />
      </aside>

      <section class="mp-detail mp-panel--stretch mp-detail--compact">
        <template v-if="activeTask">
          <div class="mp-detail__head">
            <div class="mp-detail__summary-head">
              <div class="mp-detail__identity">
                <div class="mp-detail__summary-main">
                  <div class="mp-detail__title-row">
                    <span
                      class="mp-detail__dot"
                      :class="{
                        'mp-detail__dot--on': activeTask.enabled && activeTask.last_status !== 'error',
                        'mp-detail__dot--err': activeTask.last_status === 'error'
                      }"
                    />
                    <h3>{{ activeTask.name }}</h3>
                    <span
                      class="mp-detail__state"
                      :class="{
                        'mp-detail__state--on': activeTask.enabled && activeTask.last_status !== 'error',
                        'mp-detail__state--err': activeTask.last_status === 'error'
                      }"
                    >
                      {{ activeTask.last_status === 'error' ? '异常' : activeTask.enabled ? '启用中' : '已停用' }}
                    </span>
                  </div>
                  <p class="mp-detail__summary">{{ buildTaskSummary(activeTask) }}</p>
                </div>

                <div class="mp-detail__action-group">
                  <el-button
                    type="primary"
                    :loading="runningTaskIds.includes(activeTask.id)"
                    @click="handleRun(activeTask)"
                  >
                    <el-icon><VideoPlay /></el-icon>
                    立即执行
                  </el-button>
                  <el-button @click="handleToggle(activeTask)">
                    <el-icon><SwitchButton /></el-icon>
                    {{ activeTask.enabled ? '暂停' : '启用' }}
                  </el-button>
                  <el-button @click="openEditDialog(activeTask)">
                    <el-icon><EditPen /></el-icon>
                    编辑
                  </el-button>
                  <el-button
                    type="danger"
                    plain
                    @click="handleDelete(activeTask)"
                  >
                    <el-icon><Delete /></el-icon>
                    删除
                  </el-button>
                </div>
              </div>

              <div class="mp-detail__meta-pills">
                <span class="mp-detail__meta-pill">关键词 {{ activeTask.keyword }}</span>
                <span class="mp-detail__meta-pill">轮询 {{ formatInterval(activeTask.interval_seconds) }}</span>
                <span class="mp-detail__meta-pill">{{ buildTaskPriceRange(activeTask) }}</span>
                <span class="mp-detail__meta-pill">最近执行 {{ formatTimestamp(activeTask.last_run_at) }}</span>
              </div>

              <div class="mp-detail__notes-row">
                <span class="mp-detail__note">更新时间 {{ formatTimestamp(activeTask.updated_at) }}</span>
                <span class="mp-detail__note">已见商品 {{ activeTask.seen_item_ids.length }}</span>
                <span
                  v-if="activeTask.webhook_url"
                  class="mp-detail__action-badge mp-detail__action-badge--webhook"
                >
                  Webhook
                </span>
                <span
                  v-if="activeTask.contact_seller_enabled"
                  class="mp-detail__action-badge mp-detail__action-badge--contact"
                >
                  自动联系
                </span>
              </div>
            </div>
          </div>

          <div
            v-if="activeTask.last_error"
            class="mp-detail__error"
          >
            {{ activeTask.last_error }}
          </div>

          <div class="mp-hits mp-hits--compact">
            <div class="mp-hits__head">
              <div class="mp-hits__title-block">
                <div class="mp-hits__title-row">
                  <strong>最近命中</strong>
                  <span class="mp-hits__count">{{ activeHits.length }} 条</span>
                </div>
                <p class="mp-hits__helper">默认折叠，按需展开预览当前任务的命中商品</p>
              </div>
              <el-button
                text
                :loading="hitsLoading"
                @click="loadHits(activeTask.id)"
              >
                刷新
              </el-button>
            </div>

            <div class="mp-hits__preview">
              <div class="mp-hits__preview-main">
                <strong>{{ activeHits.length }} 条命中</strong>
                <span class="mp-hits__latest">{{ activeHits[0]?.title || '暂无最近命中' }}</span>
              </div>
              <button
                type="button"
                class="mp-hits__toggle"
                @click="toggleHitsPreview"
              >
                <span class="mp-hits__toggle-text">{{ hitsExpanded ? '收起预览' : '展开预览' }}</span>
                <el-icon
                  class="mp-hits__toggle-icon"
                  :class="{ 'mp-hits__toggle-icon--expanded': hitsExpanded }"
                >
                  <ArrowDown />
                </el-icon>
              </button>
            </div>

            <div v-if="hitsExpanded">
              <div
                v-if="activeHits.length"
                class="mp-hit-grid"
              >
                <article
                  v-for="hit in activeHits"
                  :key="`${activeTask.id}-${hit.item_id}`"
                  class="mp-hit"
                >
                  <div class="mp-hit__cover">
                    <img
                      v-if="hit.image"
                      :src="hit.image"
                      :alt="hit.title"
                      class="mp-hit__img"
                    >
                    <span
                      v-else
                      class="mp-hit__placeholder"
                    >{{ hit.title.slice(0, 1) || '闲' }}</span>
                  </div>

                  <div class="mp-hit__body">
                    <strong class="mp-hit__title">{{ hit.title || `商品 ${hit.item_id}` }}</strong>
                    <span class="mp-hit__price">{{ hit.price || '面议' }}</span>
                    <p class="mp-hit__meta">ID {{ hit.item_id }} · {{ formatTimestamp(hit.discovered_at) }}</p>
                    <el-button
                      v-if="hit.detail_url"
                      text
                      type="primary"
                      size="small"
                      @click.stop="openHitDetail(hit.detail_url)"
                    >
                      打开详情
                    </el-button>
                  </div>
                </article>
              </div>

              <el-empty
                v-else-if="!hitsLoading"
                description="当前任务还没有最近命中"
              />
            </div>
          </div>
        </template>

        <div
          v-else
          class="mp-detail__empty"
        >
          <el-empty description="请选择左侧任务，或先新建一个监控" />
        </div>
      </section>
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="720px"
      append-to-body
    >
      <el-form
        label-position="top"
        class="mp-form"
      >
        <div class="mp-form__section">
          <div class="mp-form__section-title">基本信息</div>
          <div class="mp-form__row">
            <el-form-item
              label="任务名称"
              class="mp-form__field"
            >
              <el-input
                v-model="formState.name"
                maxlength="50"
                placeholder="例如：4060 显卡低价监控"
                show-word-limit
              />
            </el-form-item>

            <el-form-item
              label="关键词"
              class="mp-form__field"
            >
              <el-input
                v-model="formState.keyword"
                placeholder="输入闲鱼搜索关键词"
              />
            </el-form-item>
          </div>
        </div>

        <div class="mp-form__section">
          <div class="mp-form__section-title">搜索参数</div>
          <div class="mp-form__row">
            <el-form-item
              label="轮询间隔（秒）"
              class="mp-form__field"
            >
              <el-input-number
                v-model="formState.interval_seconds"
                :min="30"
                :step="30"
                controls-position="right"
              />
            </el-form-item>

            <el-form-item
              label="每页数量"
              class="mp-form__field"
            >
              <el-input-number
                v-model="formState.page_size"
                :min="1"
                :max="50"
                controls-position="right"
              />
            </el-form-item>

            <el-form-item
              label="页码"
              class="mp-form__field"
            >
              <el-input-number
                v-model="formState.page"
                :min="1"
                controls-position="right"
              />
            </el-form-item>

            <el-form-item
              label="排序"
              class="mp-form__field"
            >
              <el-select
                :model-value="`${formState.sort_field}:${formState.sort_value}`"
                placeholder="请选择排序方式"
                @update:model-value="handleSortValueChange"
              >
                <el-option
                  label="综合排序"
                  value=":"
                />
                <el-option
                  label="价格升序"
                  value="price:asc"
                />
                <el-option
                  label="价格降序"
                  value="price:desc"
                />
              </el-select>
            </el-form-item>
          </div>
        </div>

        <div class="mp-form__section">
          <div class="mp-form__section-title">价格筛选</div>
          <div class="mp-form__row">
            <el-form-item
              label="最低价"
              class="mp-form__field"
            >
              <el-input-number
                v-model="formState.min_price"
                :min="0"
                :precision="2"
                controls-position="right"
                placeholder="可选"
              />
            </el-form-item>

            <el-form-item
              label="最高价"
              class="mp-form__field"
            >
              <el-input-number
                v-model="formState.max_price"
                :min="0"
                :precision="2"
                controls-position="right"
                placeholder="可选"
              />
            </el-form-item>
          </div>
        </div>

        <div class="mp-form__section">
          <div class="mp-form__section-title">触发条件</div>
          <div class="mp-form__row">
            <el-form-item
              label="发布时间限制（小时）"
              class="mp-form__field"
            >
              <el-input-number
                v-model="formState.published_within_hours"
                :min="1"
                controls-position="right"
                placeholder="不限"
              />
            </el-form-item>

            <el-form-item
              label="最大命中数"
              class="mp-form__field"
            >
              <el-input-number
                v-model="formState.max_hits"
                :min="1"
                controls-position="right"
                placeholder="不限"
              />
            </el-form-item>
          </div>
        </div>

        <div class="mp-form__section">
          <div class="mp-form__section-title">执行动作</div>
          <div class="mp-form__row">
            <el-form-item
              label="Webhook 通知地址"
              class="mp-form__field mp-form__field--full"
            >
              <el-input
                v-model="formState.webhook_url"
                placeholder="https://example.com/webhook"
                clearable
              />
            </el-form-item>
          </div>
          <div class="mp-form__row">
            <el-form-item label="自动联系卖家">
              <el-switch
                v-model="formState.contact_seller_enabled"
                active-text="开启"
                inactive-text="关闭"
              />
              <div class="mp-form__hint">
                命中后自动向卖家发送消息（需先登录闲鱼）
              </div>
            </el-form-item>
          </div>
        </div>

        <div class="mp-form__section">
          <div class="mp-form__section-title">高级筛选</div>
          <el-form-item label="筛选属性 JSON">
            <el-input
              v-model="formState.prop_values_text"
              type="textarea"
              :rows="4"
              placeholder="{&#10;  &quot;p1&quot;: &quot;v1&quot;&#10;}"
            />
          </el-form-item>
        </div>
      </el-form>

      <template #footer>
        <div class="mp-form__footer">
          <el-button @click="dialogVisible = false">
            取消
          </el-button>
          <el-button
            type="primary"
            :loading="saving"
            @click="handleSubmit"
          >
            保存任务
          </el-button>
        </div>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.mp {
  display: grid;
  gap: 20px;
  padding: 20px;
}

.mp-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 24px;
  padding: 24px 28px;
  border-radius: 16px;
  border: 1px solid rgba(var(--app-border-rgb), 0.4);
  background:
    radial-gradient(ellipse at 0 0, rgba(var(--app-accent-rgb), 0.1), transparent 50%),
    linear-gradient(135deg, rgba(var(--app-surface-rgb), 0.96), rgba(var(--app-surface-alt-rgb), 0.92));
}

.mp-header__badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border-radius: 6px;
  background: rgba(var(--app-accent-rgb), 0.1);
  color: rgb(var(--app-accent-rgb));
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.mp-header__title {
  margin: 10px 0 4px;
  font-size: 22px;
  font-weight: 700;
  line-height: 1.3;
  color: rgb(var(--app-text-strong-rgb));
}

.mp-header__desc {
  margin: 0;
  font-size: 14px;
  color: rgb(var(--app-text-subtle-rgb));
  line-height: 1.6;
}

.mp-header__actions {
  display: flex;
  flex-shrink: 0;
  flex-wrap: wrap;
  gap: 8px;
  align-items: flex-start;
}

.mp-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.mp-stat {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 16px 18px;
  border-radius: 12px;
  border: 1px solid rgba(var(--app-border-rgb), 0.36);
  background: rgba(var(--app-surface-alt-rgb), 0.5);
}

.mp-stat--accent {
  border-color: rgba(34, 197, 94, 0.24);
  background: rgba(34, 197, 94, 0.06);
}

.mp-stat__label {
  font-size: 12px;
  font-weight: 500;
  color: rgb(var(--app-text-subtle-rgb));
  letter-spacing: 0.01em;
}

.mp-stat__value-row {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.mp-stat__value {
  font-size: 24px;
  font-weight: 700;
  line-height: 1.1;
  color: rgb(var(--app-text-strong-rgb));
  font-variant-numeric: tabular-nums;
}

.mp-stat--accent .mp-stat__value {
  color: rgb(22, 163, 74);
}

.mp-stat__unit {
  font-size: 13px;
  color: rgb(var(--app-text-subtle-rgb));
}

.mp-body {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.mp-body--balanced {
  align-items: stretch;
}

.mp-panel--stretch {
  min-height: 100%;
  height: 100%;
}

.mp-sidebar {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: 12px;
  align-content: start;
  padding: 16px;
  border-radius: 12px;
  border: 1px solid rgba(var(--app-border-rgb), 0.36);
  background: rgba(var(--app-surface-alt-rgb), 0.4);
}

.mp-sidebar__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(var(--app-border-rgb), 0.2);
}

.mp-sidebar__head strong {
  font-size: 14px;
  font-weight: 600;
  color: rgb(var(--app-text-strong-rgb));
}

.mp-sidebar__count {
  font-size: 12px;
  color: rgb(var(--app-text-subtle-rgb));
}

.mp-task-list {
  display: grid;
  gap: 8px;
}

.mp-task-list--fill {
  align-content: start;
}

.mp-task-list--compact {
  gap: 6px;
}

.mp-task {
  display: grid;
  gap: 8px;
  padding: 13px 14px;
  border-radius: 12px;
  border: 1px solid rgba(var(--app-border-rgb), 0.3);
  background: rgba(var(--app-surface-rgb), 0.6);
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
}

.mp-task--framed {
  border-color: rgba(var(--app-border-rgb), 0.42);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.04);
}

.mp-task--compact {
  gap: 6px;
  padding: 11px 12px;
}

.mp-task:hover {
  border-color: rgba(var(--app-accent-rgb), 0.36);
  background: rgba(var(--app-surface-rgb), 0.85);
  box-shadow: 0 6px 16px rgba(var(--app-shadow-rgb), 0.07);
}

.mp-task--active {
  border-color: rgba(var(--app-accent-rgb), 0.42);
  background: rgba(var(--app-accent-rgb), 0.08);
  box-shadow: inset 3px 0 0 rgba(var(--app-accent-rgb), 0.9), 0 8px 18px rgba(var(--app-shadow-rgb), 0.08);
}

.mp-task__top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.mp-task__name-row {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.mp-task__name {
  font-size: 15px;
  font-weight: 700;
  line-height: 1.35;
  letter-spacing: 0.01em;
  color: rgb(var(--app-text-strong-rgb));
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: color 0.15s ease;
}

.mp-task__name--active {
  color: rgb(var(--app-accent-rgb));
}

.mp-task__dot {
  flex-shrink: 0;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: rgb(var(--app-text-subtle-rgb));
}

.mp-task__dot--on {
  background: rgb(34, 197, 94);
  box-shadow: 0 0 6px rgba(34, 197, 94, 0.4);
  animation: mp-pulse 2s ease-in-out infinite;
}

.mp-task__dot--err {
  background: rgb(239, 68, 68);
  box-shadow: 0 0 6px rgba(239, 68, 68, 0.4);
  animation: mp-pulse-err 1.5s ease-in-out infinite;
}

@keyframes mp-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

@keyframes mp-pulse-err {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.mp-task__status {
  flex-shrink: 0;
  align-self: flex-start;
  padding: 2px 8px;
  border-radius: 4px;
  background: rgba(var(--app-text-subtle-rgb), 0.1);
  color: rgb(var(--app-text-subtle-rgb));
  font-size: 11px;
  font-weight: 600;
}

.mp-task--running .mp-task__status {
  background: rgba(34, 197, 94, 0.1);
  color: rgb(22, 163, 74);
}

.mp-task--error .mp-task__status {
  background: rgba(239, 68, 68, 0.1);
  color: rgb(220, 38, 38);
}

.mp-task__keyword {
  margin: 0;
  font-size: 13px;
  font-weight: 500;
  color: rgb(var(--app-text-rgb));
  opacity: 0.82;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mp-task__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.mp-task__chips span {
  padding: 2px 8px;
  border-radius: 4px;
  background: rgba(var(--app-accent-rgb), 0.08);
  border: 1px solid rgba(var(--app-accent-rgb), 0.15);
  font-size: 11px;
  color: rgb(var(--app-accent-rgb));
}

.mp-task__footer {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin-top: 2px;
  font-size: 11px;
  color: rgb(var(--app-text-subtle-rgb));
}

.mp-detail {
  display: grid;
  gap: 16px;
  align-content: start;
  padding: 20px;
  border-radius: 12px;
  border: 1px solid rgba(var(--app-border-rgb), 0.36);
  background: rgba(var(--app-surface-alt-rgb), 0.4);
}

.mp-detail--compact {
  gap: 14px;
  padding: 18px;
}

.mp-detail__head {
  display: grid;
  gap: 14px;
  padding-bottom: 14px;
  border-bottom: 1px solid rgba(var(--app-border-rgb), 0.2);
}

.mp-detail__summary-head {
  display: grid;
  gap: 12px;
  min-width: 0;
}

.mp-detail__identity {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.mp-detail__summary-main {
  display: grid;
  gap: 8px;
  min-width: 0;
  flex: 1;
}

.mp-detail__title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.mp-detail__dot {
  flex-shrink: 0;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: rgb(var(--app-text-subtle-rgb));
}

.mp-detail__dot--on {
  background: rgb(34, 197, 94);
  box-shadow: 0 0 8px rgba(34, 197, 94, 0.4);
  animation: mp-pulse 2s ease-in-out infinite;
}

.mp-detail__dot--err {
  background: rgb(239, 68, 68);
  box-shadow: 0 0 8px rgba(239, 68, 68, 0.4);
  animation: mp-pulse-err 1.5s ease-in-out infinite;
}

.mp-detail__title-row h3 {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: rgb(var(--app-text-strong-rgb));
}

.mp-detail__state {
  padding: 3px 10px;
  border-radius: 999px;
  background: rgba(var(--app-border-rgb), 0.14);
  font-size: 12px;
  font-weight: 600;
  color: rgb(var(--app-text-subtle-rgb));
}

.mp-detail__state--on {
  background: rgba(34, 197, 94, 0.12);
  color: rgb(22, 163, 74);
}

.mp-detail__state--err {
  background: rgba(239, 68, 68, 0.12);
  color: rgb(220, 38, 38);
}

.mp-detail__summary {
  margin: 0;
  font-size: 13px;
  color: rgb(var(--app-text-subtle-rgb));
  line-height: 1.6;
}

.mp-detail__meta-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.mp-detail__meta-pill {
  display: inline-flex;
  align-items: center;
  padding: 5px 10px;
  border-radius: 999px;
  font-size: 12px;
  background: rgba(var(--app-border-rgb), 0.12);
  color: rgb(var(--app-text-subtle-rgb));
}

.mp-detail__notes-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.mp-detail__note {
  font-size: 12px;
  color: rgb(var(--app-text-subtle-rgb));
}

.mp-detail__action-badge {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}

.mp-detail__action-badge--webhook {
  background: rgba(59, 130, 246, 0.1);
  color: rgb(37, 99, 235);
}

.mp-detail__action-badge--contact {
  background: rgba(168, 85, 247, 0.1);
  color: rgb(147, 51, 234);
}

.mp-detail__action-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
  flex-shrink: 0;
}

.mp-detail__error {
  padding: 12px 16px;
  border-radius: 8px;
  background: rgba(239, 68, 68, 0.06);
  border: 1px solid rgba(239, 68, 68, 0.15);
  color: rgb(185, 28, 28);
  font-size: 13px;
  line-height: 1.6;
}

.mp-hits {
  display: grid;
  gap: 12px;
}

.mp-hits--compact {
  gap: 10px;
}

.mp-hits__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.mp-hits__title-block {
  display: grid;
  gap: 6px;
}

.mp-hits__preview {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid rgba(var(--app-border-rgb), 0.28);
  background: rgba(var(--app-surface-rgb), 0.72);
}

.mp-hits__preview-main {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.mp-hits__preview-main strong {
  font-size: 14px;
  font-weight: 700;
  color: rgb(var(--app-text-strong-rgb));
}

.mp-hits__latest {
  font-size: 12px;
  color: rgb(var(--app-text-subtle-rgb));
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mp-hits__toggle {
  border: none;
  background: transparent;
  padding: 6px 10px;
  border-radius: 8px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: rgb(var(--app-accent-rgb));
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.mp-hits__toggle:hover {
  background: rgba(var(--app-accent-rgb), 0.08);
}

.mp-hits__toggle-text {
  line-height: 1;
}

.mp-hits__toggle-icon {
  font-size: 12px;
  transition: transform 0.18s ease;
}

.mp-hits__toggle-icon--expanded {
  transform: rotate(180deg);
}

.mp-hits__title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.mp-hits__title-row strong {
  font-size: 15px;
  font-weight: 600;
  color: rgb(var(--app-text-strong-rgb));
}

.mp-hits__helper {
  margin: 0;
  font-size: 12px;
  color: rgb(var(--app-text-subtle-rgb));
  line-height: 1.5;
}

.mp-hits__count {
  padding: 1px 8px;
  border-radius: 4px;
  background: rgba(var(--app-accent-rgb), 0.1);
  font-size: 12px;
  font-weight: 600;
  color: rgb(var(--app-accent-rgb));
}

.mp-hit-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}

.mp-hit {
  overflow: hidden;
  border-radius: 10px;
  border: 1px solid rgba(var(--app-border-rgb), 0.3);
  background: rgba(var(--app-surface-rgb), 0.7);
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.mp-hit:hover {
  border-color: rgba(var(--app-accent-rgb), 0.3);
  box-shadow: 0 4px 12px rgba(var(--app-shadow-rgb), 0.08);
}

.mp-hit__cover {
  width: 100%;
  height: 160px;
  overflow: hidden;
  background: rgba(var(--app-surface-alt-rgb), 0.6);
}

.mp-hit__img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.mp-hit__placeholder {
  display: grid;
  place-items: center;
  width: 100%;
  height: 100%;
  font-size: 28px;
  font-weight: 700;
  color: rgb(var(--app-text-subtle-rgb));
  background: rgba(var(--app-surface-alt-rgb), 0.8);
}

.mp-hit__body {
  display: grid;
  gap: 4px;
  padding: 12px;
}

.mp-hit__title {
  font-size: 14px;
  font-weight: 600;
  line-height: 1.5;
  color: rgb(var(--app-text-strong-rgb));
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.mp-hit__price {
  font-size: 16px;
  font-weight: 700;
  color: rgb(var(--app-accent-rgb));
}

.mp-hit__meta {
  margin: 0;
  font-size: 12px;
  color: rgb(var(--app-text-subtle-rgb));
  line-height: 1.5;
}

.mp-detail__empty {
  display: grid;
  min-height: 320px;
  place-items: center;
}

.mp-form {
  padding-top: 4px;
}

.mp-form__section {
  margin-bottom: 20px;
}

.mp-form__section:last-child {
  margin-bottom: 0;
}

.mp-form__section-title {
  margin-bottom: 12px;
  padding-bottom: 6px;
  font-size: 13px;
  font-weight: 600;
  color: rgb(var(--app-text-subtle-rgb));
  letter-spacing: 0.02em;
  border-bottom: 1px solid rgba(var(--app-border-rgb), 0.2);
}

.mp-form__row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 16px;
}

.mp-form__field--full {
  grid-column: 1 / -1;
}

.mp-form__hint {
  margin-top: 4px;
  font-size: 12px;
  color: rgb(var(--app-text-subtle-rgb));
  line-height: 1.5;
}

.mp-form__footer {
  display: flex;
  justify-content: end;
  gap: 8px;
}

@media (max-width: 1200px) {
  .mp-body {
    grid-template-columns: 1fr;
  }

  .mp-header {
    flex-direction: column;
  }

  .mp-detail__head {
    flex-direction: column;
  }

  .mp-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .mp {
    padding: 12px;
    gap: 12px;
  }

  .mp-header {
    padding: 16px;
  }

  .mp-sidebar,
  .mp-detail {
    padding: 14px;
  }

  .mp-stats {
    grid-template-columns: 1fr 1fr;
  }

  .mp-form__row {
    grid-template-columns: 1fr;
  }

  .mp-hit-grid {
    grid-template-columns: 1fr;
  }
}

@media (prefers-reduced-motion: reduce) {
  .mp-task__dot--on,
  .mp-task__dot--err,
  .mp-detail__dot--on,
  .mp-detail__dot--err {
    animation: none;
  }
}
</style>
