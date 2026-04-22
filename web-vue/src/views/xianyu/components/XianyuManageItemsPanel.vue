<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, EditPen, RefreshRight } from '@element-plus/icons-vue'
import {
  deleteXianyuManageItem,
  listXianyuManageItems,
  setXianyuManageItemMultiQuantityDelivery,
  syncXianyuManageItemsAll,
  syncXianyuManageItemsPage,
  updateXianyuManageItem,
  type XianyuManageItem,
} from '@/api/modules/xianyu'

const loading = ref(false)
const syncLoading = ref(false)
const items = ref<XianyuManageItem[]>([])
const editVisible = ref(false)
const editingItemId = ref('')
const editDetail = ref('')
const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0,
  hasMore: false,
})

const stats = computed(() => [
  { label: '商品总数', value: `${pagination.total}`, unit: '个', accent: false },
  { label: '当前页', value: `${pagination.page}`, unit: `/${Math.max(1, Math.ceil(pagination.total / pagination.pageSize))}`, accent: false },
  { label: '每页数量', value: `${pagination.pageSize}`, unit: '条', accent: false },
  { label: '更多数据', value: pagination.hasMore ? '有' : '无', unit: '', accent: pagination.hasMore },
])

function hasPrice(price: string) {
  return Boolean(String(price || '').trim())
}

function formatPrice(price: string) {
  const raw = String(price || '').trim()
  if (!raw) return '未设置价格'
  return raw.startsWith('¥') ? raw : `¥${raw}`
}

function itemStatusLabel(status: string) {
  if (status === 'onsale') return '在售'
  if (status === 'offline') return '已下架'
  return status || '未知状态'
}

function formatItemTime(value: number) {
  if (!value) return '未知时间'
  const date = new Date(value * 1000)
  if (Number.isNaN(date.getTime())) return '未知时间'
  return `${date.getMonth() + 1}/${date.getDate()} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

async function loadItems(page = pagination.page) {
  loading.value = true
  try {
    const response = await listXianyuManageItems({ page, page_size: pagination.pageSize })
    const data = response.data
    items.value = data.items || []
    pagination.page = data.page || page
    pagination.pageSize = data.page_size || pagination.pageSize
    pagination.total = data.total || 0
    pagination.hasMore = Boolean(data.has_more)
  } catch (error: any) {
    ElMessage.error(error?.message || '加载商品列表失败')
  } finally {
    loading.value = false
  }
}

async function syncCurrentPage() {
  syncLoading.value = true
  try {
    await syncXianyuManageItemsPage({ page: pagination.page, page_size: pagination.pageSize })
    await loadItems(pagination.page)
    ElMessage.success('当前页商品已同步')
  } catch (error: any) {
    ElMessage.error(error?.message || '同步当前页失败')
  } finally {
    syncLoading.value = false
  }
}

async function syncAll() {
  syncLoading.value = true
  try {
    await syncXianyuManageItemsAll()
    await loadItems(1)
    ElMessage.success('全部商品同步完成')
  } catch (error: any) {
    ElMessage.error(error?.message || '同步全部商品失败')
  } finally {
    syncLoading.value = false
  }
}

function openEdit(item: XianyuManageItem) {
  editingItemId.value = item.item_id
  editDetail.value = item.item_detail || ''
  editVisible.value = true
}

async function saveEdit() {
  try {
    await updateXianyuManageItem(editingItemId.value, { item_detail: editDetail.value })
    await loadItems(pagination.page)
    editVisible.value = false
    ElMessage.success('商品详情已更新')
  } catch (error: any) {
    ElMessage.error(error?.message || '更新商品详情失败')
  }
}

async function toggleMultiQuantity(item: XianyuManageItem, enabled: boolean) {
  try {
    await setXianyuManageItemMultiQuantityDelivery(item.item_id, enabled)
    item.multi_quantity_delivery = enabled
    ElMessage.success('多数量发货设置已更新')
  } catch (error: any) {
    item.multi_quantity_delivery = !enabled
    ElMessage.error(error?.message || '更新多数量发货设置失败')
  }
}

async function removeItem(item: XianyuManageItem) {
  try {
    await ElMessageBox.confirm(
      `确定删除商品「${item.item_title || item.item_id}」的本地缓存吗？`,
      '删除商品',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
    await deleteXianyuManageItem(item.item_id)
    const nextPage = items.value.length <= 1 && pagination.page > 1 ? pagination.page - 1 : pagination.page
    await loadItems(nextPage)
    ElMessage.success('商品缓存已删除')
  } catch (error: any) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(error?.message || '删除商品缓存失败')
  }
}

async function handlePageChange(page: number) {
  if (!page || page === pagination.page) return
  await loadItems(page)
}

onMounted(() => {
  void loadItems(1)
})
</script>

<template>
  <section class="mg-section">
    <div class="mg-section__head">
      <div class="mg-section__info">
        <h3>商品管理</h3>
        <p>同步本地商品缓存、编辑商品详情并维护多数量发货开关</p>
      </div>
      <div class="mg-section__actions">
        <el-button :loading="syncLoading" @click="syncCurrentPage">
          <el-icon><RefreshRight /></el-icon>
          同步当前页
        </el-button>
        <el-button type="primary" :loading="syncLoading" @click="syncAll">
          同步全部
        </el-button>
      </div>
    </div>

    <div class="mg-section__toolbar">
      <div class="mg-stats">
        <div
          v-for="stat in stats"
          :key="stat.label"
          class="mg-stat"
          :class="{ 'mg-stat--accent': stat.accent }"
        >
          <span class="mg-stat__label">{{ stat.label }}</span>
          <div class="mg-stat__value-row">
            <strong class="mg-stat__value">{{ stat.value }}</strong>
            <span v-if="stat.unit" class="mg-stat__unit">{{ stat.unit }}</span>
          </div>
        </div>
      </div>
    </div>

    <div v-if="loading" class="mg-section__empty">正在加载商品列表...</div>
    <el-empty v-else-if="!items.length" description="暂无商品数据" />

    <div v-else class="mg-items-shell">
      <div class="mg-item-list">
        <article
          v-for="item in items"
          :key="item.item_id"
          class="mg-item"
        >
          <div class="mg-item__media">
            <img
              v-if="item.item_image"
              :src="item.item_image"
              :alt="item.item_title || item.item_id"
              class="mg-item__cover-image"
              loading="lazy"
            />
            <div v-else class="mg-item__cover-placeholder">
              <span>暂无封面</span>
            </div>
          </div>

          <div class="mg-item__body">
            <div class="mg-item__header">
              <div class="mg-item__title-wrap">
                <strong>{{ item.item_title || item.item_id }}</strong>
                <span class="mg-item__id">ID {{ item.item_id }}</span>
              </div>
              <div class="mg-item__price-block">
                <span class="mg-item__price-label">价格</span>
                <span
                  class="mg-item__price-pill"
                  :class="{ 'mg-item__price-pill--muted': !hasPrice(item.item_price) }"
                >
                  {{ formatPrice(item.item_price) }}
                </span>
              </div>
            </div>
            <div class="mg-item__meta">
              <span class="mg-item__status">{{ itemStatusLabel(item.item_status) }}</span>
              <span>更新 {{ formatItemTime(item.updated_at) }}</span>
              <span>同步 {{ formatItemTime(item.synced_at) }}</span>
            </div>
            <p class="mg-item__detail mg-item__detail--clamp">{{ item.item_detail || '暂无商品详情' }}</p>
          </div>

          <div class="mg-item__actions">
            <div class="mg-item__primary-action">
              <span class="mg-item__primary-label">多数量发货</span>
              <el-switch
                :model-value="item.multi_quantity_delivery"
                active-text="多数量发货"
                @change="toggleMultiQuantity(item, Boolean($event))"
              />
            </div>
            <div class="mg-item__btns">
              <el-button size="small" @click="openEdit(item)">
                <el-icon><EditPen /></el-icon>
                编辑
              </el-button>
              <el-button size="small" type="danger" plain @click="removeItem(item)">
                <el-icon><Delete /></el-icon>
                删除
              </el-button>
            </div>
          </div>
        </article>
      </div>

      <aside class="mg-items-aside">
        <div class="mg-items-aside__card">
          <strong>当前页说明</strong>
          <p>统一展示封面、标题、价格和详情摘要，减少长文对列表节奏的破坏。</p>
        </div>
        <div class="mg-items-aside__card">
          <strong>同步提示</strong>
          <p>优先同步当前页，确认内容后再执行全量同步，降低误操作成本。</p>
        </div>
      </aside>
    </div>

    <el-pagination
      v-if="pagination.total > pagination.pageSize"
      class="mg-pagination"
      layout="prev, pager, next"
      :current-page="pagination.page"
      :page-size="pagination.pageSize"
      :total="pagination.total"
      @current-change="handlePageChange"
    />

    <el-dialog v-model="editVisible" title="编辑商品详情" width="560px" append-to-body>
      <el-input
        v-model="editDetail"
        type="textarea"
        :rows="6"
        placeholder="请输入商品详情文本"
      />
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>
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
  border-bottom: 1px solid rgba(var(--app-border-rgb), 0.2);
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

.mg-section__toolbar {
  display: grid;
  gap: 12px;
}

.mg-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.mg-stat {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 14px 16px;
  border-radius: 10px;
  border: 1px solid rgba(var(--app-border-rgb), 0.36);
  background: rgba(var(--app-surface-alt-rgb), 0.5);
}

.mg-stat--accent {
  border-color: rgba(var(--app-accent-rgb), 0.24);
  background: rgba(var(--app-accent-rgb), 0.06);
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
  color: rgb(var(--app-accent-rgb));
}

.mg-stat__unit {
  font-size: 13px;
  color: rgb(var(--app-text-subtle-rgb));
}

.mg-items-shell {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 260px;
  gap: 16px;
  align-items: start;
}

.mg-item-list {
  display: grid;
  gap: 10px;
}

.mg-items-aside {
  display: grid;
  gap: 12px;
}

.mg-items-aside__card {
  display: grid;
  gap: 6px;
  padding: 14px 16px;
  border-radius: 12px;
  border: 1px solid rgba(var(--app-border-rgb), 0.3);
  background: rgba(var(--app-surface-alt-rgb), 0.5);
}

.mg-items-aside__card strong {
  font-size: 14px;
  font-weight: 700;
  color: rgb(var(--app-text-strong-rgb));
}

.mg-items-aside__card p {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  color: rgb(var(--app-text-subtle-rgb));
}

.mg-item {
  display: grid;
  grid-template-columns: 88px minmax(0, 1fr) auto;
  gap: 14px;
  align-items: center;
  padding: 14px 16px;
  border-radius: 12px;
  border: 1px solid rgba(var(--app-border-rgb), 0.3);
  background: rgba(var(--app-surface-rgb), 0.6);
  transition: border-color 0.15s ease, background 0.15s ease;
}

.mg-item:hover {
  border-color: rgba(var(--app-accent-rgb), 0.3);
  background: rgba(var(--app-surface-rgb), 0.85);
}

.mg-item__media {
  width: 88px;
  height: 88px;
  border-radius: 12px;
  overflow: hidden;
  background: rgba(var(--app-surface-alt-rgb), 0.8);
  border: 1px solid rgba(var(--app-border-rgb), 0.22);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
}

.mg-item__cover-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.mg-item__cover-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px;
  text-align: center;
  font-size: 11px;
  line-height: 1.4;
  color: rgb(var(--app-text-subtle-rgb));
  background: linear-gradient(135deg, rgba(var(--app-surface-alt-rgb), 0.95), rgba(var(--app-border-rgb), 0.1));
}

.mg-item__body {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.mg-item__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.mg-item__title-wrap {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.mg-item__title-wrap strong {
  font-size: 14px;
  font-weight: 700;
  line-height: 1.45;
  color: rgb(var(--app-text-strong-rgb));
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.mg-item__id {
  width: fit-content;
  max-width: 100%;
  padding: 1px 8px;
  border-radius: 999px;
  background: rgba(var(--app-text-subtle-rgb), 0.1);
  font-size: 11px;
  color: rgb(var(--app-text-subtle-rgb));
  font-family: monospace;
}

.mg-item__price-block {
  display: grid;
  justify-items: end;
  gap: 4px;
  flex-shrink: 0;
}

.mg-item__price-label {
  font-size: 11px;
  color: rgb(var(--app-text-subtle-rgb));
}

.mg-item__price-pill {
  flex-shrink: 0;
  padding: 7px 12px;
  border-radius: 999px;
  font-size: 16px;
  font-weight: 800;
  line-height: 1;
  color: rgb(194 65 12);
  background: linear-gradient(135deg, rgb(255 237 213), rgb(255 247 237));
  box-shadow: 0 8px 20px rgba(234, 88, 12, 0.12);
  font-variant-numeric: tabular-nums;
}

.mg-item__price-pill--muted {
  color: rgb(var(--app-text-subtle-rgb));
  background: rgba(var(--app-surface-alt-rgb), 0.82);
  box-shadow: none;
  font-size: 12px;
  font-weight: 600;
}

.mg-item__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  font-size: 12px;
  color: rgb(var(--app-text-subtle-rgb));
}

.mg-item__status {
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(34, 197, 94, 0.12);
  color: rgb(22, 163, 74);
  font-weight: 600;
}

.mg-item__detail {
  margin: 0;
  font-size: 13px;
  color: rgb(var(--app-text-subtle-rgb));
  line-height: 1.6;
}

.mg-item__detail--clamp {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.mg-item__actions {
  display: grid;
  gap: 10px;
  align-content: center;
  justify-items: end;
}

.mg-item__primary-action {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  width: 100%;
}

.mg-item__primary-label {
  font-size: 12px;
  color: rgb(var(--app-text-subtle-rgb));
}

.mg-item__btns {
  display: flex;
  gap: 6px;
}

.mg-pagination {
  justify-content: flex-end;
}

.mg-section__empty {
  padding: 32px 0;
  text-align: center;
  color: rgb(var(--app-text-subtle-rgb));
}

@media (max-width: 768px) {
  .mg-items-shell {
    grid-template-columns: 1fr;
  }

  .mg-stats {
    grid-template-columns: 1fr 1fr;
  }

  .mg-item {
    grid-template-columns: 72px minmax(0, 1fr);
    align-items: start;
  }

  .mg-item__media {
    width: 72px;
    height: 72px;
  }

  .mg-item__header {
    flex-direction: column;
    align-items: stretch;
  }

  .mg-item__price-block {
    justify-items: start;
  }

  .mg-item__price-pill {
    align-self: flex-start;
  }

  .mg-item__actions {
    grid-column: 1 / -1;
    justify-items: start;
    margin-top: 4px;
  }
}
</style>
