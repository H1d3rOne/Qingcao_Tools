<script setup lang="ts">
import { computed, onMounted, ref, watch, type CSSProperties } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Bell, ChatDotRound, Link, Search, Setting } from '@element-plus/icons-vue'
import {
  createXianyuMonitorTask,
  getXianyuItemDetail,
  getXianyuUserProfile,
  openXianyuChatSession,
  searchXianyuItems,
  type XianyuFilterGroup,
  type XianyuItemDetail,
  type XianyuSearchItem,
  type XianyuSearchResult,
  type XianyuUserProfile
} from '@/api/modules/xianyu'
import { useXianyuUserStore } from '@/stores'
import XianyuChatPanel from './components/XianyuChatPanel.vue'
import XianyuManagePanel from './components/XianyuManagePanel.vue'
import XianyuMonitorPanel from './components/XianyuMonitorPanel.vue'

const router = useRouter()
const xianyuStore = useXianyuUserStore()
const searchKeyword = ref('')
const searching = ref(false)
const hasSearched = ref(false)
const searchError = ref('')
const searchResult = ref<XianyuSearchResult | null>(null)
const searchItems = ref<XianyuSearchItem[]>([])
const searchFilters = ref<XianyuFilterGroup[]>([])
// 基准筛选项（首次搜索拿到的完整筛选维度，后续翻页/加筛选不覆盖）
const baselineFilters = ref<XianyuFilterGroup[]>([])
// 记录基准对应的关键词，关键词变化时重置基准
const baselineKeyword = ref('')
const selectedPropValues = ref<Record<string, string>>({})
const selectedSortKey = ref('default')
const minPriceInput = ref('')
const maxPriceInput = ref('')
const currentPage = ref(1)
const currentPageSize = ref(20)
const activeBottomTab = ref('search')
const newlyCreatedTaskId = ref('')
const xianyuUser = ref<XianyuUserProfile | null>(null)
const xianyuUserLoading = ref(false)
const detailVisible = ref(false)
const detailLoading = ref(false)
const detailError = ref('')
const detailData = ref<XianyuItemDetail | null>(null)
const currentDetailItemId = ref('')
const activeDetailImageIndex = ref(0)
const preferredChatCid = ref('')
const openingChatSession = ref(false)

const sortOptions = [
  { label: '综合排序', value: 'default', sortField: '', sortValue: '' },
  { label: '价格从低到高', value: 'price_asc', sortField: 'price', sortValue: 'asc' },
  { label: '价格从高到低', value: 'price_desc', sortField: 'price', sortValue: 'desc' }
]
const pageSizeOptions = [20, 30, 50]
const bottomTabs = [
  { key: 'search', label: '搜索', hint: '真实搜索', icon: Search },
  { key: 'monitor', label: '监控', hint: '动态提醒', icon: Bell },
  { key: 'manage', label: '管理', hint: '商品与发货', icon: Setting },
  { key: 'chat', label: '聊天', hint: '会话消息', icon: ChatDotRound }
]

const activeBottomTabInfo = computed(() => bottomTabs.find((tab) => tab.key === activeBottomTab.value) || bottomTabs[0])
const selectedSortOption = computed(() => {
  return sortOptions.find((item) => item.value === selectedSortKey.value) || sortOptions[0]
})
const monitorPreset = computed(() => ({
  name: `${searchKeyword.value.trim() || '闲鱼'}监控`,
  keyword: searchKeyword.value.trim(),
  page: currentPage.value,
  page_size: currentPageSize.value,
  sort_field: selectedSortOption.value.sortField,
  sort_value: selectedSortOption.value.sortValue,
  prop_values: { ...selectedPropValues.value },
  min_price: normalizedPriceRange.value.min,
  max_price: normalizedPriceRange.value.max,
  interval_seconds: 180
}))

const totalPages = computed(() => {
  const total = searchResult.value?.total || searchItems.value.length
  const size = searchResult.value?.page_size || currentPageSize.value

  if (!total || !size) return 0
  return Math.max(1, Math.ceil(total / size))
})

const searchSummaryText = computed(() => {
  if (!searchResult.value) return ''

  const parts = [
    `共 ${searchResult.value.total.toLocaleString()} 条`,
    totalPages.value ? `第 ${currentPage.value} / ${totalPages.value} 页` : `第 ${currentPage.value} 页`,
    `每页 ${currentPageSize.value} 条`
  ]

  if (searchResult.value.location) {
    parts.push(searchResult.value.location)
  }

  return parts.join(' · ')
})

const activeFilterCount = computed(() => Object.keys(selectedPropValues.value).length)
const searchDashboardStats = computed(() => [
  {
    label: '账号状态',
    value: xianyuUserLoading.value ? '读取中' : xianyuUser.value ? '已登录' : '未登录'
  },
  {
    label: '搜索结果',
    value: searchResult.value?.total ? `${formatCompactCount(searchResult.value.total)} 条` : '等待搜索'
  },
  {
    label: '筛选条件',
    value: activeFilterCount.value ? `${activeFilterCount.value} 个` : '未启用'
  },
  {
    label: '分页进度',
    value: totalPages.value ? `${currentPage.value} / ${totalPages.value}` : '未开始'
  }
])

const normalizedPriceRange = computed(() => {
  const min = Number(minPriceInput.value)
  const max = Number(maxPriceInput.value)

  const hasMin = Number.isFinite(min) && min >= 0 && minPriceInput.value !== ''
  const hasMax = Number.isFinite(max) && max >= 0 && maxPriceInput.value !== ''

  if (!hasMin && !hasMax) {
    return { min: null, max: null }
  }

  if (hasMin && hasMax && min > max) {
    return { min: max, max: min }
  }

  return {
    min: hasMin ? min : null,
    max: hasMax ? max : null
  }
})

const displayItems = computed(() => {
  const { min, max } = normalizedPriceRange.value
  const filtered = searchItems.value.filter((item) => {
    const price = extractPriceNumber(item.price)

    if (min !== null && (price === null || price < min)) {
      return false
    }

    if (max !== null && (price === null || price > max)) {
      return false
    }

    return true
  })

  if (selectedSortKey.value === 'price_asc') {
    return [...filtered].sort((a, b) => comparePrice(extractPriceNumber(a.price), extractPriceNumber(b.price), 'asc'))
  }

  if (selectedSortKey.value === 'price_desc') {
    return [...filtered].sort((a, b) => comparePrice(extractPriceNumber(a.price), extractPriceNumber(b.price), 'desc'))
  }

  return filtered
})

const userDisplayStats = computed(() => {
  if (!xianyuUser.value) return []

  return [
    { label: '卖出', value: formatCompactCount(xianyuUser.value.sold_count || 0) },
    { label: '买到', value: formatCompactCount(xianyuUser.value.purchase_count || 0) },
    { label: '收藏', value: formatCompactCount(xianyuUser.value.collection_count || 0) }
  ]
})

const activeDetailImage = computed(() => {
  if (!detailData.value?.images.length) return ''
  return detailData.value.images[activeDetailImageIndex.value] || detailData.value.images[0]
})

function buildItemSummary(item: XianyuSearchItem) {
  const parts = [item.area, item.seller, ...item.tags.slice(0, 2)].filter(Boolean)
  return parts.join(' · ') || '闲鱼真实搜索结果'
}

function extractPriceNumber(priceText: string) {
  const match = priceText.match(/\d+(?:\.\d+)?/)
  return match ? Number(match[0]) : null
}

function comparePrice(a: number | null, b: number | null, direction: 'asc' | 'desc') {
  if (a === null && b === null) return 0
  if (a === null) return 1
  if (b === null) return -1
  return direction === 'asc' ? a - b : b - a
}

function normalizePriceInput(value: string) {
  return value.replace(/[^\d.]/g, '').replace(/(\..*)\./g, '$1')
}

// 价格区间变化后，自动刷新搜索结果（防抖 500ms，重置到第 1 页）
let priceFilterTimer: number | null = null
watch([minPriceInput, maxPriceInput], () => {
  if (!hasSearched.value || !searchKeyword.value.trim()) return
  if (priceFilterTimer) {
    clearTimeout(priceFilterTimer)
  }
  priceFilterTimer = window.setTimeout(() => {
    currentPage.value = 1
    void runSearch(1)
  }, 500)
})

function formatCompactCount(value: number) {
  if (value >= 10000) {
    return `${(value / 10000).toFixed(value >= 100000 ? 0 : 1)}万`
  }
  return String(value)
}

function getBottomTabButtonStyle(tabKey: string): CSSProperties {
  const isActive = activeBottomTab.value === tabKey

  return {
    color: isActive ? 'rgb(22, 59, 40)' : 'rgb(75, 115, 90)',
    background: isActive
      ? 'linear-gradient(135deg, rgba(187, 247, 208, 0.62), rgba(167, 243, 208, 0.58))'
      : 'transparent',
    boxShadow: isActive ? '0 14px 28px rgba(110, 231, 183, 0.1)' : 'none',
  }
}

function getBottomTabLabelStyle(tabKey: string): CSSProperties {
  const isActive = activeBottomTab.value === tabKey

  return {
    display: 'block',
    opacity: '1',
    visibility: 'visible',
    color: isActive ? 'rgb(22, 59, 40)' : 'rgb(var(--app-text-rgb))',
    WebkitTextFillColor: isActive ? 'rgb(22, 59, 40)' : 'rgb(var(--app-text-rgb))',
  }
}

function getBottomTabHintStyle(tabKey: string): CSSProperties {
  const isActive = activeBottomTab.value === tabKey

  return {
    display: 'block',
    opacity: '1',
    visibility: 'visible',
    color: isActive ? 'rgba(22, 59, 40, 0.78)' : 'rgb(var(--app-text-muted-rgb))',
    WebkitTextFillColor: isActive ? 'rgba(22, 59, 40, 0.78)' : 'rgb(var(--app-text-muted-rgb))',
  }
}

async function fetchXianyuUserProfile() {
  xianyuUserLoading.value = true
  try {
    const response = await getXianyuUserProfile()
    xianyuUser.value = response.data
  } catch {
    xianyuUser.value = null
  } finally {
    xianyuUserLoading.value = false
  }
}

async function handleLogout() {
  await xianyuStore.logout()
  ElMessage.success('已退出闲鱼登录')
  router.push('/xianyu/login')
}

async function openItemDetail(itemId: string) {
  currentDetailItemId.value = itemId
  detailVisible.value = true
  detailLoading.value = true
  detailError.value = ''
  detailData.value = null
  activeDetailImageIndex.value = 0

  try {
    const response = await getXianyuItemDetail(itemId)
    detailData.value = response.data
  } catch (err: any) {
    const msg = err?.message || '获取宝贝详情失败'
    detailError.value = msg
    if (msg.includes('过期') || msg.includes('FAIL_SYS_USER_VALIDATE') || msg.includes('Cookie')) {
      ElMessage.warning('闲鱼登录已过期，请前往设置页重新配置 Cookie')
    }
  } finally {
    detailLoading.value = false
  }
}

async function handleSearch() {
  const keyword = searchKeyword.value.trim()
  if (!keyword) {
    ElMessage.warning('请输入关键词或闲鱼链接')
    return
  }

  if (searchResult.value?.keyword !== keyword) {
    selectedPropValues.value = {}
  }

  currentPage.value = 1
  await runSearch(1)
}

function handlePaste() {
  if (typeof navigator === 'undefined' || !navigator.clipboard?.readText) {
    ElMessage.warning('当前环境无法读取剪贴板')
    return
  }

  navigator.clipboard.readText()
    .then((text) => {
      searchKeyword.value = text
      ElMessage.success('已粘贴到搜索框')
    })
    .catch(() => {
      ElMessage.warning('当前环境无法读取剪贴板')
    })
}

// 合并基准筛选项与最新返回：以基准为骨架（保证所有筛选维度始终在 UI 上），
// 同名 pid 的 options 优先用最新返回（保证选项随上下文动态更新），
// 最新返回中存在但基准没有的新 pid 也追加到末尾
function mergeFilters(baseline: XianyuFilterGroup[], latest: XianyuFilterGroup[]): XianyuFilterGroup[] {
  const latestMap = new Map(latest.map((g) => [g.pid, g]))
  const merged = baseline.map((g) => {
    const fresh = latestMap.get(g.pid)
    return fresh ? { ...g, options: fresh.options } : g
  })
  const baselinePids = new Set(baseline.map((g) => g.pid))
  for (const g of latest) {
    if (!baselinePids.has(g.pid)) {
      merged.push(g)
    }
  }
  return merged
}

async function runSearch(page: number) {
  const keyword = searchKeyword.value.trim()
  if (!keyword) return

  searching.value = true
  searchError.value = ''

  try {
    const response = await searchXianyuItems({
      keyword,
      page,
      page_size: currentPageSize.value,
      sort_field: sortOptions.find((item) => item.value === selectedSortKey.value)?.sortField || '',
      sort_value: sortOptions.find((item) => item.value === selectedSortKey.value)?.sortValue || '',
      prop_values: selectedPropValues.value
    })
    const data = response.data

    hasSearched.value = true
    searchResult.value = data
    currentPage.value = data.page || page
    currentPageSize.value = data.page_size || currentPageSize.value
    // 关键词变化时重置基准筛选项
    if (baselineKeyword.value !== keyword) {
      baselineKeyword.value = keyword
      baselineFilters.value = data.filters || []
      searchFilters.value = data.filters || []
    } else {
      // 同一关键词的后续搜索：以基准为准，合并 API 返回的最新 options
      searchFilters.value = mergeFilters(baselineFilters.value, data.filters || [])
    }
    searchItems.value = data.items || []
    searchError.value = ''
  } catch (err: any) {
    hasSearched.value = true
    const msg = err?.message || '闲鱼搜索失败'
    searchError.value = msg

    searchResult.value = null
    searchItems.value = []
    searchFilters.value = []

    if (msg.includes('过期') || msg.includes('FAIL_SYS_USER_VALIDATE') || msg.includes('Cookie')) {
      ElMessage.warning('闲鱼登录已过期，请前往设置页重新配置 Cookie')
    }
  } finally {
    searching.value = false
  }
}

function resetSearch() {
  hasSearched.value = false
  searchError.value = ''
  searchResult.value = null
  searchItems.value = []
  searchFilters.value = []
  baselineFilters.value = []
  baselineKeyword.value = ''
  selectedPropValues.value = {}
  selectedSortKey.value = 'default'
  minPriceInput.value = ''
  maxPriceInput.value = ''
  currentPage.value = 1
  currentPageSize.value = pageSizeOptions[0]
}

async function handleFilterChange(pid: string, value?: string) {
  if (searching.value) return

  const next = { ...selectedPropValues.value }
  if (!value) {
    delete next[pid]
  } else {
    next[pid] = value
  }

  selectedPropValues.value = next
  currentPage.value = 1
  await runSearch(1)
}

async function handleSortChange() {
  if (!hasSearched.value || !searchKeyword.value.trim()) return
  currentPage.value = 1
  await runSearch(1)
}

async function openMonitorFromCurrentSearch() {
  if (!searchKeyword.value.trim()) {
    ElMessage.warning('请先输入闲鱼关键词')
    return
  }
  try {
    const preset = monitorPreset.value
    const response = await createXianyuMonitorTask({
      name: preset.name || `${searchKeyword.value.trim()}监控`,
      keyword: searchKeyword.value.trim(),
      page: currentPage.value,
      page_size: currentPageSize.value,
      sort_field: selectedSortOption.value.sortField,
      sort_value: selectedSortOption.value.sortValue,
      prop_values: { ...selectedPropValues.value },
      min_price: normalizedPriceRange.value.min,
      max_price: normalizedPriceRange.value.max,
      interval_seconds: 180,
      enabled: false,
    })
    newlyCreatedTaskId.value = response.data?.id || ''
    activeBottomTab.value = 'monitor'
    ElMessage.success('监控任务已创建，请编辑条件后启用')
  } catch (err: any) {
    ElMessage.error(err.message || '创建监控任务失败')
  }
}

async function handlePageChange(page: number) {
  if (searching.value || page === currentPage.value) return
  await runSearch(page)
}

async function handlePageSizeChange(size: number) {
  if (searching.value || size === currentPageSize.value) return
  currentPageSize.value = size
  currentPage.value = 1
  await runSearch(1)
}

function selectDetailImage(index: number) {
  activeDetailImageIndex.value = index
}

function openDetailInNewTab() {
  if (!detailData.value?.detail_url) {
    ElMessage.warning('暂无原站详情链接')
    return
  }
  window.open(detailData.value.detail_url, '_blank', 'noopener,noreferrer')
}

async function contactSeller() {
  if (!detailData.value?.item_id || !detailData.value?.seller_user_id) {
    ElMessage.error('商品或卖家信息不完整，无法打开聊天')
    return
  }

  openingChatSession.value = true

  try {
    const response = await openXianyuChatSession({
      item_id: detailData.value.item_id,
      peer_user_id: detailData.value.seller_user_id,
    })
    if (!response.success || !response.cid) {
      ElMessage.error(response.message || '打开会话失败')
      return
    }

    preferredChatCid.value = response.cid
    detailVisible.value = false
    activeBottomTab.value = 'chat'
    ElMessage.success(response.message || '已打开会话')
  } catch {
    // 请求层已经负责提示错误，这里不重复弹窗
  } finally {
    openingChatSession.value = false
  }
}

onMounted(() => {
  void fetchXianyuUserProfile()
})

watch(activeBottomTab, () => {
  const el = document.getElementById('main-scroll-container')
  if (el) el.scrollTo({ top: 0, behavior: 'smooth' })
})
</script>

<template>
  <div class="xianyu-page">
    <nav class="bottom-nav theme-surface-card">
      <button
        v-for="tab in bottomTabs"
        :key="tab.key"
        type="button"
        class="bottom-nav__item bottom-nav__item--plain"
        :class="{ 'is-active': activeBottomTab === tab.key }"
        :style="getBottomTabButtonStyle(tab.key)"
        @click="activeBottomTab = tab.key"
      >
        <el-icon><component :is="tab.icon" /></el-icon>
        <strong
          class="bottom-nav__label"
          :class="{ 'is-active-label': activeBottomTab === tab.key }"
          :style="getBottomTabLabelStyle(tab.key)"
        >{{ tab.label }}</strong>
        <span
          class="bottom-nav__hint"
          :class="{ 'is-active-hint': activeBottomTab === tab.key }"
          :style="getBottomTabHintStyle(tab.key)"
        >{{ tab.hint }}</span>
      </button>
    </nav>

    <template v-if="activeBottomTab === 'search'">
      <section class="search-panel theme-surface-card">
        <div class="search-hero">
          <div class="search-hero__main">
            <div class="search-hero__stats">
              <div
                v-for="stat in searchDashboardStats"
                :key="stat.label"
                class="search-hero__stat theme-surface-soft"
              >
                <span>{{ stat.label }}</span>
                <strong>{{ stat.value }}</strong>
              </div>
            </div>
          </div>

          <div
            v-if="xianyuUserLoading || xianyuUser"
            class="search-panel__top"
          >
            <div
              v-if="xianyuUser"
              class="user-card theme-surface-soft"
            >
              <img
                :src="xianyuUser.avatar"
                :alt="xianyuUser.display_name"
                class="user-card__avatar"
              >
              <div class="user-card__main">
                <div class="user-card__name-row">
                  <strong>{{ xianyuUser.display_name }}</strong>
                  <span>已登录</span>
                </div>
                <div class="user-card__meta">
                  粉丝 {{ formatCompactCount(xianyuUser.followers || 0) }} · 关注 {{ formatCompactCount(xianyuUser.following || 0) }}
                </div>
                <div class="user-card__stats">
                  <div
                    v-for="stat in userDisplayStats"
                    :key="stat.label"
                    class="user-card__stat"
                  >
                    <strong>{{ stat.value }}</strong>
                    <span>{{ stat.label }}</span>
                  </div>
                </div>
                <div class="user-card__actions">
                  <el-button
                    size="small"
                    @click="handleLogout"
                  >
                    退出登录
                  </el-button>
                </div>
              </div>
            </div>

            <div
              v-else
              class="user-card user-card--loading theme-surface-soft"
            >
              <div class="user-card__avatar user-card__avatar--placeholder" />
              <div class="user-card__main">
                <strong>正在读取闲鱼账号</strong>
                <span class="user-card__meta">请稍候...</span>
              </div>
            </div>
          </div>
        </div>

        <div class="search-bar theme-surface-soft">
          <div class="search-bar__scope">
            闲鱼搜索
          </div>
          <el-input
            v-model="searchKeyword"
            class="search-bar__input"
            placeholder="搜索商品、宠物、数码，或粘贴闲鱼链接"
            @keyup.enter="handleSearch"
          >
            <template #prefix>
              <el-icon><Link /></el-icon>
            </template>
          </el-input>
          <el-button
            type="primary"
            :loading="searching"
            @click="handleSearch"
          >
            <el-icon><Search /></el-icon>
            搜索
          </el-button>
          <el-button @click="handlePaste">
            粘贴
          </el-button>
          <el-button
            :disabled="!searchKeyword.trim()"
            @click="openMonitorFromCurrentSearch"
          >
            添加监控
          </el-button>
        </div>

        <div class="search-note">
          <span>真实接口搜索</span>
          <span>支持接口返回筛选项</span>
          <span>结果列表按规则网格展示</span>
          <span>支持详情弹窗查看</span>
          <span v-if="activeFilterCount">已选 {{ activeFilterCount }} 个筛选</span>
        </div>
      </section>

      <section
        v-if="hasSearched"
        class="result-panel theme-surface-card"
      >
        <div class="result-toolbar">
          <div>
            <h2>“{{ searchResult?.keyword || searchKeyword.trim() }}”</h2>
            <p class="result-summary">
              {{ searchSummaryText || '正在查询...' }}
            </p>
          </div>

          <div class="result-actions">
            <el-button
              size="small"
              :loading="searching"
              @click="runSearch(currentPage)"
            >
              刷新
            </el-button>
            <el-button
              size="small"
              @click="resetSearch"
            >
              清空
            </el-button>
          </div>
        </div>

        <div
          v-if="searchError"
          class="search-error-card"
        >
          {{ searchError }}
        </div>

        <div class="filter-groups">
          <div class="filter-group filter-group--compact">
            <div class="filter-group__title">
              排序
            </div>
            <el-select
              v-model="selectedSortKey"
              class="filter-group__select"
              placeholder="请选择排序"
              @change="handleSortChange"
            >
              <el-option
                v-for="option in sortOptions"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
          </div>

          <div class="filter-group filter-group--price">
            <div class="filter-group__title">
              价格区间
            </div>
            <div class="price-range">
              <el-input
                :model-value="minPriceInput"
                class="price-range__input"
                clearable
                placeholder="最低价"
                @update:model-value="minPriceInput = normalizePriceInput($event || '')"
              />
              <span class="price-range__separator">-</span>
              <el-input
                :model-value="maxPriceInput"
                class="price-range__input"
                clearable
                placeholder="最高价"
                @update:model-value="maxPriceInput = normalizePriceInput($event || '')"
              />
            </div>
          </div>

          <div
            v-for="group in searchFilters"
            :key="group.pid"
            class="filter-group"
          >
            <div class="filter-group__title">
              {{ group.name }}
            </div>
            <el-select
              :model-value="selectedPropValues[group.pid]"
              class="filter-group__select"
              clearable
              filterable
              placeholder="请选择"
              @change="handleFilterChange(group.pid, $event)"
            >
              <el-option
                v-for="option in group.options"
                :key="`${group.pid}-${option.value}`"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
          </div>
        </div>

        <div
          v-if="displayItems.length"
          class="search-grid"
        >
          <article
            v-for="item in displayItems"
            :key="item.item_id"
            class="result-card theme-surface-soft"
            tabindex="0"
            @click="openItemDetail(item.item_id)"
            @keyup.enter="openItemDetail(item.item_id)"
          >
            <div class="result-card__cover">
              <img
                :src="item.image"
                :alt="item.title"
                class="result-card__image"
              >
              <span
                v-if="item.want"
                class="result-card__badge"
              >{{ item.want }}</span>
              <span class="result-card__view">查看详情</span>
            </div>

            <div class="result-card__body">
              <h3 class="result-card__title">
                {{ item.title }}
              </h3>
              <p class="result-card__desc">
                {{ buildItemSummary(item) }}
              </p>

              <div class="result-card__price">
                <strong>{{ item.price || '面议' }}</strong>
                <span>{{ item.area || '闲鱼' }}</span>
              </div>

              <div class="result-card__seller">
                <img
                  v-if="item.seller_avatar"
                  :src="item.seller_avatar"
                  :alt="item.seller || '卖家'"
                  class="result-card__avatar"
                >
                <span class="result-card__seller-name">{{ item.seller || '匿名卖家' }}</span>
              </div>

              <div
                v-if="item.tags.length"
                class="result-card__tags"
              >
                <span
                  v-for="tag in item.tags.slice(0, 2)"
                  :key="tag"
                >{{ tag }}</span>
              </div>
            </div>
          </article>
        </div>

        <el-empty
          v-else-if="!searching && !searchError"
          :description="searchItems.length ? '当前筛选条件下暂无结果' : '暂无搜索结果'"
        />

        <div
          v-if="searchItems.length"
          class="result-footer"
        >
          <span>
            当前页展示 {{ displayItems.length }} 条 · 每页 {{ currentPageSize }} 条 · 共 {{ totalPages || 0 }} 页 / {{ searchResult?.total || 0 }} 条
          </span>
        </div>

        <div
          v-if="totalPages > 1"
          class="pagination-wrap"
        >
          <el-pagination
            background
            layout="sizes, prev, pager, next, jumper, ->, total"
            :current-page="currentPage"
            :page-size="currentPageSize"
            :page-sizes="pageSizeOptions"
            :total="searchResult?.total || 0"
            @size-change="handlePageSizeChange"
            @current-change="handlePageChange"
          />
        </div>
      </section>
    </template>

    <XianyuChatPanel
      v-else-if="activeBottomTab === 'chat'"
      :current-user="xianyuUser"
      :preferred-cid="preferredChatCid"
    />

    <XianyuMonitorPanel
      v-else-if="activeBottomTab === 'monitor'"
      :current-user="xianyuUser"
      :search-preset="monitorPreset"
      :initial-task-id="newlyCreatedTaskId"
    />

    <XianyuManagePanel
      v-else-if="activeBottomTab === 'manage'"
      :current-user="xianyuUser"
    />

    <section
      v-else
      class="placeholder-panel theme-surface-card"
    >
      <div class="placeholder-panel__icon">
        <el-icon><component :is="activeBottomTabInfo.icon" /></el-icon>
      </div>
      <div class="placeholder-panel__content">
        <h2>{{ activeBottomTabInfo.label }}功能区建设中</h2>
        <p>当前已经完成的真实搜索、筛选、分页和宝贝详情能力，全部放在底部“搜索”栏里。</p>
        <div class="placeholder-panel__chips">
          <span>已预留 {{ activeBottomTabInfo.label }} 入口</span>
          <span>后续可继续接入真实接口</span>
          <span>当前搜索功能保持完整可用</span>
        </div>
        <el-button
          type="primary"
          @click="activeBottomTab = 'search'"
        >
          返回搜索
        </el-button>
      </div>
    </section>

    <el-dialog
      v-model="detailVisible"
      class="xianyu-detail-dialog"
      width="960px"
      top="4vh"
      append-to-body
      :show-close="true"
    >
      <template #header>
        <div class="detail-dialog__header">
          <strong>宝贝详情</strong>
          <span>ID {{ detailData?.item_id || currentDetailItemId }}</span>
        </div>
      </template>

      <div
        v-if="detailLoading"
        class="detail-loading-card"
      >
        正在加载宝贝详情...
      </div>

      <div
        v-else-if="detailError"
        class="detail-error-card"
      >
        {{ detailError }}
      </div>

      <div
        v-else-if="detailData"
        class="detail-content"
      >
        <div class="detail-layout">
          <section class="detail-gallery">
            <div class="detail-gallery__main">
              <img
                v-if="activeDetailImage"
                :src="activeDetailImage"
                :alt="detailData.title"
                class="detail-gallery__main-image"
              >
              <div
                v-else
                class="detail-gallery__empty"
              >
                暂无图片
              </div>
            </div>

            <div
              v-if="detailData.images.length > 1"
              class="detail-gallery__thumbs"
            >
              <button
                v-for="(image, index) in detailData.images"
                :key="`${detailData.item_id}-${index}`"
                type="button"
                class="detail-gallery__thumb"
                :class="{ 'is-active': activeDetailImageIndex === index }"
                @click="selectDetailImage(index)"
              >
                <img
                  :src="image"
                  :alt="`${detailData.title}-${index + 1}`"
                >
              </button>
            </div>
          </section>

          <section class="detail-info">
            <div class="detail-seller">
              <img
                v-if="detailData.seller_avatar"
                :src="detailData.seller_avatar"
                :alt="detailData.seller_name"
                class="detail-seller__avatar"
              >
              <div class="detail-seller__main">
                <div class="detail-seller__name-row">
                  <strong>{{ detailData.seller_name || '匿名卖家' }}</strong>
                  <span class="detail-seller__badge">卖家</span>
                </div>
                <div class="detail-seller__meta-row">
                  <span v-if="detailData.seller_city">{{ detailData.seller_city }}</span>
                  <span v-if="detailData.seller_last_visit">{{ detailData.seller_last_visit }}</span>
                  <span>在售 {{ detailData.seller_item_count }} 件</span>
                </div>
              </div>
            </div>

            <div class="detail-price-section">
              <div class="detail-price-row">
                <strong class="detail-price-value">{{ detailData.price || '面议' }}</strong>
                <span
                  v-if="detailData.original_price && detailData.original_price !== detailData.price"
                  class="detail-original-price"
                >{{ detailData.original_price }}</span>
                <span
                  v-if="detailData.transport_fee"
                  class="detail-transport-badge"
                >{{ detailData.transport_fee }}</span>
              </div>
              <div class="detail-stats-row">
                <span>{{ formatCompactCount(detailData.browse_count) }} 浏览</span>
                <span>{{ formatCompactCount(detailData.want_count) }} 想要</span>
                <span>{{ formatCompactCount(detailData.collect_count) }} 收藏</span>
              </div>
            </div>

            <h3 class="detail-title">
              {{ detailData.title }}
            </h3>

            <div
              v-if="detailData.tags.length"
              class="detail-tags"
            >
              <span
                v-for="tag in detailData.tags"
                :key="tag"
              >{{ tag }}</span>
            </div>

            <div class="detail-desc-block theme-surface-soft">
              <div class="detail-desc-block__title">
                宝贝描述
              </div>
              <div class="detail-desc">
                <p>{{ detailData.desc || '暂无描述' }}</p>
              </div>
            </div>

            <div
              v-if="detailData.attributes.length"
              class="detail-attrs"
            >
              <div
                v-for="attribute in detailData.attributes"
                :key="`${attribute.name}-${attribute.value}`"
                class="detail-attr"
              >
                <span class="detail-attr__name">{{ attribute.name }}</span>
                <span class="detail-attr__value">{{ attribute.value }}</span>
              </div>
            </div>

            <div class="detail-meta-list">
              <span v-if="detailData.location">{{ detailData.location }}</span>
              <span v-if="detailData.publish_time">{{ detailData.publish_time }}</span>
              <span v-if="detailData.status">{{ detailData.status }}</span>
            </div>

            <div class="detail-actions">
              <el-button
                type="primary"
                size="large"
                :loading="openingChatSession"
                @click="contactSeller"
              >
                <el-icon><ChatDotRound /></el-icon>
                联系卖家
              </el-button>
              <el-button
                size="large"
                @click="openDetailInNewTab"
              >
                <el-icon><Link /></el-icon>
                打开原站详情
              </el-button>
            </div>
          </section>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.xianyu-page {
  display: grid;
  gap: 16px;
  color: rgb(var(--app-text-rgb));
}

.search-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) auto;
  gap: 18px;
  align-items: stretch;
  margin-bottom: 16px;
}

.search-hero__main {
  display: grid;
  gap: 16px;
}

.search-hero__stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.search-hero__stat {
  display: grid;
  gap: 8px;
  padding: 14px 16px;
  border-radius: 18px;
  border: 1px solid rgba(var(--app-border-rgb) / 0.56);
  background:
    linear-gradient(180deg, rgba(var(--app-surface-rgb) / 0.96), rgba(var(--app-surface-alt-rgb) / 0.88));
  box-shadow:
    0 10px 24px rgba(var(--app-shadow-rgb) / 0.07),
    inset 0 1px 0 rgba(var(--utility-white-rgb) / 0.5);
}

.search-hero__stat span {
  color: rgb(var(--app-text-subtle-rgb));
  font-size: 12px;
}

.search-hero__stat strong {
  color: rgb(var(--app-text-strong-rgb));
  font-size: 18px;
  line-height: 1.2;
}

.search-panel,
.result-panel {
  position: relative;
  overflow: hidden;
  border-radius: 20px;
  padding: 20px;
  border: 1px solid rgba(var(--app-border-rgb) / 0.56);
  box-shadow:
    0 14px 36px rgba(var(--app-shadow-rgb) / 0.09),
    inset 0 1px 0 rgba(var(--utility-white-rgb) / 0.5);
}

.search-panel {
  isolation: isolate;
  background:
    radial-gradient(circle at top left, rgba(var(--primary-color-rgb) / 0.2), transparent 30%),
    radial-gradient(circle at right 15%, rgba(var(--app-accent-alt-rgb) / 0.16), transparent 24%),
    linear-gradient(135deg, rgba(var(--app-surface-rgb) / 0.94), rgba(var(--app-surface-alt-rgb) / 0.88));
}

.search-panel::before,
.search-panel::after {
  content: '';
  position: absolute;
  inset: auto;
  border-radius: 50%;
  filter: blur(28px);
  z-index: -1;
}

.search-panel::before {
  top: -48px;
  left: -24px;
  width: 180px;
  height: 180px;
  background: rgba(var(--primary-color-rgb) / 0.2);
}

.search-panel::after {
  right: -36px;
  bottom: -68px;
  width: 220px;
  height: 220px;
  background: rgba(var(--app-accent-alt-rgb) / 0.14);
}

.result-panel {
  background:
    linear-gradient(180deg, rgba(var(--app-surface-rgb) / 0.92), rgba(var(--app-surface-alt-rgb) / 0.84));
}

.result-toolbar h2 {
  margin: 0;
  color: rgb(var(--app-text-strong-rgb));
  line-height: 1.2;
}

.result-summary,
.result-footer span {
  margin: 10px 0 0;
  color: rgb(var(--app-text-muted-rgb));
  line-height: 1.7;
}

.search-panel__top {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 0;
}

.user-card {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 320px;
  max-width: 420px;
  padding: 14px 16px;
  border-radius: 20px;
  border: 1px solid rgba(var(--app-border-rgb) / 0.52);
  background:
    linear-gradient(135deg, rgba(var(--app-surface-rgb) / 0.92), rgba(var(--app-surface-alt-rgb) / 0.82));
  box-shadow:
    0 12px 28px rgba(var(--app-shadow-rgb) / 0.09),
    inset 0 1px 0 rgba(var(--utility-white-rgb) / 0.5);
}

.user-card__avatar {
  width: 56px;
  height: 56px;
  border-radius: 18px;
  object-fit: cover;
  flex-shrink: 0;
  border: 2px solid rgba(var(--utility-white-rgb) / 0.8);
}

.user-card__avatar--placeholder {
  background:
    linear-gradient(135deg, rgba(var(--primary-color-rgb) / 0.24), rgba(var(--app-accent-alt-rgb) / 0.18));
}

.user-card__main {
  min-width: 0;
  flex: 1;
}

.user-card__name-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.user-card__name-row strong {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: rgb(var(--app-text-strong-rgb));
  font-size: 16px;
}

.user-card__name-row span {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 22px;
  padding: 0 10px;
  border-radius: 999px;
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 700;
  color: rgb(var(--utility-white-rgb));
  background: linear-gradient(135deg, rgba(var(--primary-color-rgb) / 0.92), rgba(var(--app-accent-alt-rgb) / 0.82));
}

.user-card__meta {
  display: block;
  margin-top: 4px;
  color: rgb(var(--app-text-subtle-rgb));
  font-size: 12px;
  line-height: 1.5;
}

.user-card__stats {
  display: flex;
  gap: 10px;
  margin-top: 10px;
}

.user-card__actions {
  margin-top: 10px;
}

.user-card__stat {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.user-card__stat strong {
  color: rgb(var(--app-text-strong-rgb));
  font-size: 14px;
  line-height: 1.1;
}

.user-card__stat span {
  color: rgb(var(--app-text-subtle-rgb));
  font-size: 11px;
}

.user-card--loading {
  min-width: 280px;
}

.search-bar {
  position: relative;
  display: grid;
  grid-template-columns: 112px minmax(0, 1fr) auto auto auto;
  gap: 12px;
  align-items: center;
  padding: 16px;
  border-radius: 24px;
  background:
    linear-gradient(135deg, rgba(var(--app-surface-rgb) / 0.86), rgba(var(--app-surface-alt-rgb) / 0.76));
  border: 1px solid rgba(var(--utility-white-rgb) / 0.24);
  box-shadow:
    0 18px 36px rgba(var(--app-shadow-rgb) / 0.1),
    inset 0 1px 0 rgba(var(--utility-white-rgb) / 0.18);
  backdrop-filter: blur(18px);
}

.search-bar::after {
  content: '';
  position: absolute;
  inset: 1px;
  border-radius: 23px;
  pointer-events: none;
  border: 1px solid rgba(var(--utility-white-rgb) / 0.08);
}

.search-bar__scope {
  height: 48px;
  display: grid;
  place-items: center;
  padding: 0 14px;
  border-radius: 16px;
  font-size: 13px;
  font-weight: 700;
  color: rgb(var(--utility-white-rgb));
  background: linear-gradient(135deg, rgba(var(--primary-color-rgb) / 0.94), rgba(var(--app-accent-alt-rgb) / 0.88));
  box-shadow: 0 10px 24px rgba(var(--primary-color-rgb) / 0.2);
}

.search-bar__input :deep(.el-input__wrapper) {
  min-height: 48px;
  border-radius: 999px;
  padding-inline: 14px;
  background: rgba(var(--app-surface-rgb) / 0.96);
  box-shadow:
    0 10px 24px rgba(var(--app-shadow-rgb) / 0.06),
    0 0 0 1px rgba(var(--app-border-rgb) / 0.54) inset;
}

.search-bar__input :deep(.el-input__inner) {
  color: rgb(var(--app-text-rgb));
}

.search-bar :deep(.el-button) {
  min-height: 48px;
  padding-inline: 18px;
  border-radius: 16px;
}

.search-bar :deep(.el-button--primary) {
  box-shadow: 0 12px 24px rgba(var(--primary-color-rgb) / 0.2);
}

.search-note {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.search-note span,
.result-card__tags span {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 5px 10px;
  font-size: 12px;
  background: rgba(var(--primary-color-rgb) / 0.12);
  color: rgb(var(--app-text-rgb));
  border: 1px solid rgba(var(--app-border-rgb) / 0.45);
}

.result-toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 2px;
}

.result-actions {
  display: flex;
  gap: 8px;
}

.search-error-card {
  margin-top: 16px;
  padding: 14px 16px;
  border-radius: 12px;
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.18);
  color: rgb(var(--app-text-strong-rgb));
  line-height: 1.7;
}

.filter-groups {
  margin-top: 18px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px;
}

.filter-group {
  display: grid;
  gap: 8px;
  padding: 12px;
  border-radius: 16px;
  background: rgba(var(--app-surface-alt-rgb) / 0.78);
  border: 1px solid rgba(var(--app-border-rgb) / 0.52);
  box-shadow: 0 6px 16px rgba(var(--app-shadow-rgb) / 0.05);
}

.filter-group--compact,
.filter-group--price {
  align-content: start;
}

.filter-group__title {
  color: rgb(var(--app-text-strong-rgb));
  font-size: 14px;
  font-weight: 700;
}

.filter-group__select :deep(.el-input__wrapper) {
  min-height: 40px;
  border-radius: 12px;
  background: rgba(var(--app-surface-rgb) / 0.94);
  box-shadow: 0 0 0 1px rgba(var(--app-border-rgb) / 0.55) inset;
}

.price-range {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  gap: 8px;
  align-items: center;
}

.price-range__input :deep(.el-input__wrapper) {
  min-height: 40px;
  border-radius: 12px;
  background: rgba(var(--app-surface-rgb) / 0.94);
  box-shadow: 0 0 0 1px rgba(var(--app-border-rgb) / 0.55) inset;
}

.price-range__separator {
  color: rgb(var(--app-text-subtle-rgb));
  font-size: 13px;
  font-weight: 700;
}

.search-grid {
  margin-top: 18px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  align-items: stretch;
}

.result-card {
  display: grid;
  grid-template-rows: 228px minmax(0, 1fr);
  height: 100%;
  min-height: 430px;
  cursor: pointer;
  border-radius: 16px;
  overflow: hidden;
  border: 1px solid rgba(var(--app-border-rgb) / 0.52);
  box-shadow:
    0 10px 24px rgba(var(--app-shadow-rgb) / 0.09),
    inset 0 1px 0 rgba(var(--utility-white-rgb) / 0.3);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.result-card:focus-visible {
  outline: 2px solid rgba(var(--primary-color-rgb) / 0.7);
  outline-offset: 2px;
}

.result-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 16px 28px rgba(var(--app-shadow-rgb) / 0.12);
}

.result-card__cover {
  position: relative;
  display: block;
  width: 100%;
  height: 228px;
  background: rgba(var(--app-surface-alt-rgb) / 0.8);
}

.result-card__image {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.result-card__badge {
  position: absolute;
  left: 10px;
  top: 10px;
  border-radius: 999px;
  padding: 5px 10px;
  font-size: 11px;
  font-weight: 700;
  color: rgb(var(--utility-white-rgb));
  background: rgba(var(--app-shadow-rgb) / 0.35);
}

.result-card__view {
  position: absolute;
  right: 10px;
  bottom: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 28px;
  padding: 0 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  color: rgb(var(--utility-white-rgb));
  background: rgba(var(--app-shadow-rgb) / 0.42);
  backdrop-filter: blur(10px);
}

.result-card__body {
  display: grid;
  grid-template-rows: 46px 40px 32px 24px 28px;
  gap: 10px;
  padding: 12px;
  min-height: 0;
}

.result-card__title,
.result-card__desc {
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  word-break: break-word;
}

.result-card__title {
  margin: 0;
  color: rgb(var(--app-text-strong-rgb));
  font-size: 15px;
  line-height: 1.5;
  height: 46px;
  -webkit-line-clamp: 2;
}

.result-card__desc {
  margin: 0;
  color: rgb(var(--app-text-muted-rgb));
  font-size: 12px;
  line-height: 1.6;
  height: 40px;
  -webkit-line-clamp: 2;
}

.result-card__price {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.result-card__price strong {
  color: rgb(var(--primary-color-rgb));
  font-size: 20px;
}

.result-card__price span {
  color: rgb(var(--app-text-subtle-rgb));
  font-size: 12px;
  flex-shrink: 0;
  white-space: nowrap;
}

.result-card__seller {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  height: 24px;
}

.result-card__avatar {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
}

.result-card__seller-name {
  display: block;
  color: rgb(var(--app-text-subtle-rgb));
  font-size: 12px;
  line-height: 1.5;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.result-card__tags {
  display: flex;
  flex-wrap: nowrap;
  gap: 6px;
  min-width: 0;
  overflow: hidden;
}

.result-card__tags span {
  max-width: 100%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.result-footer {
  margin-top: 18px;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid rgba(var(--app-border-rgb) / 0.52);
  background: rgba(var(--app-surface-alt-rgb) / 0.78);
  box-shadow: 0 6px 16px rgba(var(--app-shadow-rgb) / 0.05);
}

.result-footer span {
  margin: 0;
}

.pagination-wrap {
  margin-top: 14px;
  display: flex;
  justify-content: center;
  overflow-x: auto;
  padding-bottom: 4px;
}

.pagination-wrap :deep(.el-pagination) {
  width: max-content;
  padding: 10px 12px;
  border-radius: 18px;
  border: 1px solid rgba(var(--app-border-rgb) / 0.42);
  background: rgba(var(--app-surface-alt-rgb) / 0.72);
  box-shadow: 0 10px 24px rgba(var(--app-shadow-rgb) / 0.06);
}

.pagination-wrap :deep(.el-pagination .btn-prev),
.pagination-wrap :deep(.el-pagination .btn-next),
.pagination-wrap :deep(.el-pagination .el-pager li) {
  border-radius: 10px;
}

.pagination-wrap :deep(.el-pagination .el-pagination__total),
.pagination-wrap :deep(.el-pagination .el-pagination__jump) {
  color: rgb(var(--app-text-muted-rgb));
}

.pagination-wrap :deep(.el-pagination .el-select .el-input__wrapper) {
  border-radius: 10px;
}

.placeholder-panel {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 20px;
  align-items: center;
  min-height: 280px;
  padding: 28px;
  border-radius: 24px;
  border: 1px solid rgba(var(--app-border-rgb) / 0.56);
  background:
    radial-gradient(circle at top left, rgba(var(--primary-color-rgb) / 0.16), transparent 28%),
    radial-gradient(circle at right bottom, rgba(var(--app-accent-alt-rgb) / 0.16), transparent 30%),
    linear-gradient(135deg, rgba(var(--app-surface-rgb) / 0.96), rgba(var(--app-surface-alt-rgb) / 0.9));
  box-shadow:
    0 14px 36px rgba(var(--app-shadow-rgb) / 0.09),
    inset 0 1px 0 rgba(var(--utility-white-rgb) / 0.5);
}

.placeholder-panel__icon {
  display: grid;
  place-items: center;
  width: 96px;
  height: 96px;
  border-radius: 28px;
  font-size: 38px;
  color: rgb(var(--utility-white-rgb));
  background: linear-gradient(135deg, rgba(var(--primary-color-rgb) / 0.96), rgba(var(--app-accent-alt-rgb) / 0.88));
  box-shadow: 0 18px 40px rgba(var(--primary-color-rgb) / 0.22);
}

.placeholder-panel__content h2 {
  margin: 0;
  color: rgb(var(--app-text-strong-rgb));
  font-size: 28px;
}

.placeholder-panel__content p {
  margin: 12px 0 0;
  max-width: 700px;
  color: rgb(var(--app-text-muted-rgb));
  line-height: 1.9;
}

.placeholder-panel__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin: 18px 0 20px;
}

.placeholder-panel__chips span {
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  padding: 0 14px;
  border-radius: 999px;
  background: rgba(var(--primary-color-rgb) / 0.1);
  border: 1px solid rgba(var(--app-border-rgb) / 0.42);
  color: rgb(var(--app-text-rgb));
  font-size: 13px;
}

.bottom-nav {
  position: sticky;
  top: 0;
  z-index: 20;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin: 0 -24px 0;
  padding: 10px;
  border-radius: 0 0 24px 24px;
  border: 1px solid rgba(var(--app-border-rgb) / 0.52);
  border-top: none;
  background: rgba(var(--app-surface-rgb) / 0.86);
  box-shadow:
    0 16px 36px rgba(var(--app-shadow-rgb) / 0.15),
    inset 0 1px 0 rgba(var(--utility-white-rgb) / 0.14);
  backdrop-filter: blur(18px);
}

.bottom-nav__item {
  display: grid;
  justify-items: center;
  gap: 4px;
  padding: 14px 12px;
  border: none;
  border-radius: 18px;
  color: rgb(var(--app-text-muted-rgb));
  background: transparent;
  cursor: pointer;
  transition: transform 0.2s ease, background 0.2s ease, color 0.2s ease, box-shadow 0.2s ease;
}

.bottom-nav__item--plain {
  appearance: none;
  -webkit-appearance: none;
  outline: none;
}

.bottom-nav__item:hover {
  transform: translateY(-1px);
  background: rgba(var(--app-surface-alt-rgb) / 0.74);
}

.bottom-nav__item :deep(.el-icon) {
  font-size: 20px;
}

.bottom-nav__item strong {
  color: inherit;
  font-size: 14px;
  line-height: 1.2;
}

.bottom-nav__label,
.bottom-nav__hint {
  display: block;
  color: inherit;
  opacity: 1;
  visibility: visible;
  -webkit-text-fill-color: currentColor;
}

.bottom-nav__item span {
  font-size: 11px;
  line-height: 1.2;
}

.bottom-nav__item.is-active {
  color: rgb(var(--utility-white-rgb));
  background: linear-gradient(135deg, rgba(var(--primary-color-rgb) / 0.94), rgba(var(--app-accent-alt-rgb) / 0.88));
  box-shadow: 0 14px 28px rgba(var(--primary-color-rgb) / 0.24);
}

.bottom-nav__item.is-active .bottom-nav__label,
.bottom-nav__label.is-active-label,
.bottom-nav__item.is-active :deep(.el-icon) {
  color: rgb(var(--utility-white-rgb));
}

.bottom-nav__item.is-active .bottom-nav__hint,
.bottom-nav__hint.is-active-hint {
  color: rgba(var(--utility-white-rgb) / 0.92);
}

.bottom-nav__item.is-active {
  color: rgb(var(--utility-white-rgb));
  background: linear-gradient(135deg, rgba(var(--primary-color-rgb) / 0.94), rgba(var(--app-accent-alt-rgb) / 0.88));
  box-shadow: 0 14px 28px rgba(var(--primary-color-rgb) / 0.24);
}

:deep(.xianyu-detail-dialog) {
  max-width: calc(100vw - 32px);
}

:deep(.xianyu-detail-dialog .el-dialog) {
  border-radius: 16px !important;
  overflow: hidden;
  border: 1px solid rgba(var(--app-border-rgb) / 0.56) !important;
  background: rgb(var(--app-surface-rgb)) !important;
  box-shadow: 0 22px 48px rgba(var(--app-shadow-rgb) / 0.18) !important;
  --el-dialog-bg-color: rgb(var(--app-surface-rgb)) !important;
  --el-bg-color: rgb(var(--app-surface-rgb)) !important;
}

:deep(.xianyu-detail-dialog .el-dialog__header) {
  margin-right: 0;
  padding: 16px 24px 0;
  background: rgb(var(--app-surface-rgb)) !important;
}

:deep(.xianyu-detail-dialog .el-dialog__body) {
  padding: 16px 24px 24px;
  color: rgb(var(--app-text-strong-rgb)) !important;
}

:deep(.xianyu-detail-dialog .el-dialog__headerbtn .el-dialog__close) {
  color: rgb(var(--app-text-rgb));
}

.detail-dialog__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.detail-dialog__header strong {
  color: rgb(var(--app-text-strong-rgb));
  font-size: 16px;
}

.detail-dialog__header span {
  color: rgb(var(--app-text-subtle-rgb));
  font-size: 12px;
}

.detail-loading-card {
  display: grid;
  place-items: center;
  min-height: 320px;
  color: rgb(var(--app-text-muted-rgb));
}

.detail-error-card {
  padding: 14px 16px;
  border-radius: 12px;
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.18);
  color: rgb(var(--app-text-strong-rgb));
  line-height: 1.7;
}

.detail-content {
  display: grid;
}

.detail-layout {
  display: grid;
  grid-template-columns: 420px minmax(0, 1fr);
  gap: 24px;
}

.detail-gallery {
  display: grid;
  gap: 10px;
  align-content: start;
}

.detail-gallery__main {
  overflow: hidden;
  border-radius: 12px;
  aspect-ratio: 1 / 1;
  border: 1px solid rgba(var(--app-border-rgb) / 0.3);
  background: rgba(var(--app-surface-alt-rgb) / 0.6);
}

.detail-gallery__main-image {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.detail-gallery__empty {
  display: grid;
  place-items: center;
  width: 100%;
  height: 100%;
  color: rgb(var(--app-text-muted-rgb)) !important;
}

.detail-gallery__thumbs {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(64px, 1fr));
  gap: 8px;
}

.detail-gallery__thumb {
  border: 2px solid transparent;
  border-radius: 8px;
  padding: 0;
  overflow: hidden;
  background: rgba(var(--app-surface-alt-rgb) / 0.6);
  aspect-ratio: 1 / 1;
  cursor: pointer;
  transition: border-color 0.15s ease;
}

.detail-gallery__thumb.is-active {
  border-color: rgb(var(--primary-color-rgb));
}

.detail-gallery__thumb img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.detail-info {
  display: grid;
  align-content: start;
  gap: 16px;
  min-width: 0;
}

.detail-seller {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid rgba(var(--app-border-rgb) / 0.3);
  background: rgba(var(--app-surface-alt-rgb) / 0.5);
}

.detail-seller__avatar {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
  border: 1px solid rgba(var(--app-border-rgb) / 0.4);
}

.detail-seller__main {
  min-width: 0;
  flex: 1;
}

.detail-seller__name-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.detail-seller__name-row strong {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: rgb(var(--app-text-strong-rgb)) !important;
  font-size: 15px;
}

.detail-seller__badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 20px;
  padding: 0 8px;
  border-radius: 999px;
  flex-shrink: 0;
  color: rgb(var(--utility-white-rgb));
  font-size: 10px;
  font-weight: 700;
  background: linear-gradient(135deg, rgba(var(--primary-color-rgb) / 0.92), rgba(var(--app-accent-alt-rgb) / 0.84));
}

.detail-seller__meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 4px;
}

.detail-seller__meta-row span {
  color: rgb(var(--app-text-muted-rgb)) !important;
  font-size: 12px;
}

.detail-seller__meta-row span + span::before {
  content: '·';
  margin-right: 6px;
  color: rgb(var(--app-text-muted-rgb));
}

.detail-price-section {
  padding: 14px 0;
  border-bottom: 1px solid rgba(var(--app-border-rgb) / 0.2);
}

.detail-price-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
}

.detail-price-value {
  color: rgb(var(--primary-color-rgb));
  font-size: 32px;
  font-weight: 800;
  line-height: 1.1;
}

.detail-original-price {
  color: rgb(var(--app-text-muted-rgb)) !important;
  font-size: 14px;
  text-decoration: line-through;
}

.detail-transport-badge {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  color: rgb(var(--primary-color-rgb));
  background: rgba(var(--primary-color-rgb) / 0.1);
}

.detail-stats-row {
  display: flex;
  gap: 16px;
  margin-top: 8px;
}

.detail-stats-row span {
  color: rgb(var(--app-text-muted-rgb)) !important;
  font-size: 12px;
}

.detail-title {
  margin: 0;
  color: rgb(var(--app-text-strong-rgb)) !important;
  font-size: 18px;
  font-weight: 600;
  line-height: 1.5;
  word-break: break-word;
}

.detail-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.detail-tags span {
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 10px;
  border-radius: 4px;
  font-size: 12px;
  color: rgb(var(--app-text-strong-rgb)) !important;
  background: rgba(var(--app-surface-alt-rgb) / 0.8);
  border: 1px solid rgba(var(--app-border-rgb) / 0.3);
}

.detail-desc {
  color: rgb(var(--app-text-strong-rgb)) !important;
  font-size: 15px;
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-word;
}

.detail-desc p {
  margin: 0;
  color: rgb(var(--app-text-strong-rgb)) !important;
}

.detail-desc-block {
  display: grid;
  gap: 10px;
  padding: 14px 16px;
  border-radius: 12px;
  border: 1px solid rgba(var(--app-border-rgb), 0.56);
  background: rgba(var(--app-surface-alt-rgb), 0.92);
  box-shadow: 0 10px 24px rgba(var(--app-shadow-rgb) / 0.08);
}

.detail-desc-block__title {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: rgb(var(--app-text-muted-rgb)) !important;
}

.detail-attrs {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 0;
  border-radius: 8px;
  border: 1px solid rgba(var(--app-border-rgb) / 0.3);
  overflow: hidden;
}

.detail-attr {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 10px 14px;
  border-bottom: 1px solid rgba(var(--app-border-rgb) / 0.15);
}

.detail-attr:last-child {
  border-bottom: none;
}

.detail-attr__name {
  color: rgb(var(--app-text-muted-rgb)) !important;
  font-size: 13px;
  white-space: nowrap;
  flex-shrink: 0;
  min-width: 72px;
}

.detail-attr__value {
  color: rgb(var(--app-text-strong-rgb)) !important;
  font-size: 13px;
  line-height: 1.5;
  word-break: break-word;
}

.detail-meta-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.detail-meta-list span {
  color: rgb(var(--app-text-muted-rgb)) !important;
  font-size: 12px;
}

.detail-meta-list span + span::before {
  content: '·';
  margin-right: 8px;
  color: rgb(var(--app-text-muted-rgb));
}

.detail-actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 4px;
}

.detail-actions :deep(.el-button) {
  height: 42px;
  border-radius: 10px;
  font-weight: 600;
}

.detail-actions :deep(.el-button:not(.el-button--primary)) {
  color: rgb(var(--app-text-rgb));
  border-color: rgba(var(--app-border-rgb) / 0.5);
  background: rgba(var(--app-surface-alt-rgb) / 0.8);
}

@media (max-width: 1440px) {
  .search-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 1120px) {
  .search-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 840px) {
  .search-hero,
  .placeholder-panel {
    grid-template-columns: 1fr;
  }

  .search-hero__stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .search-panel__top {
    justify-content: stretch;
  }

  .user-card {
    min-width: 0;
    width: 100%;
  }

  .search-bar {
    grid-template-columns: 1fr;
  }

  .filter-groups {
    grid-template-columns: 1fr;
  }

  .result-toolbar,
  .result-footer {
    flex-direction: column;
    align-items: flex-start;
  }

  .result-actions {
    width: 100%;
  }

  .detail-layout {
    grid-template-columns: 1fr;
  }

  .detail-gallery__main {
    max-width: 420px;
  }

  .pagination-wrap {
    justify-content: flex-start;
  }

  .detail-seller {
    flex-direction: row;
  }

  .detail-actions,
  .detail-attrs {
    grid-template-columns: 1fr;
  }

  .bottom-nav {
    gap: 8px;
  }
}

@media (max-width: 640px) {
  .placeholder-panel__content h2 {
    font-size: 24px;
  }

  .search-hero__stats {
    grid-template-columns: 1fr;
  }

  .search-grid {
    grid-template-columns: 1fr;
  }

  .result-actions {
    flex-wrap: wrap;
  }

  .bottom-nav__item {
    padding: 12px 8px;
  }

  .bottom-nav__item span {
    display: none;
  }
}
</style>
