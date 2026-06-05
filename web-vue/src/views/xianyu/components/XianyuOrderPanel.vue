<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Box, Promotion, RefreshRight, Search, Van } from '@element-plus/icons-vue'
import {
  listXianyuOrders,
  shipXianyuOrder,
  type XianyuOrder,
  type XianyuOrderPage,
  type XianyuUserProfile,
} from '@/api/modules/xianyu'

defineProps<{
  currentUser?: XianyuUserProfile | null
}>()

interface StatusTab {
  key: string
  label: string
  apiValue: string
}

const statusTabs: StatusTab[] = [
  { key: 'all', label: '全部', apiValue: 'ALL' },
  { key: 'pending_ship', label: '待发货', apiValue: 'WAIT_SELLER_SEND_GOODS' },
  { key: 'shipped', label: '已发货', apiValue: 'WAIT_BUYER_CONFIRM_GOODS' },
  { key: 'completed', label: '已完成', apiValue: 'TRADE_SUCCESS' },
  { key: 'refunding', label: '退款中', apiValue: 'REFUNDING' },
  { key: 'cancelled', label: '已关闭', apiValue: 'TRADE_CLOSED' },
]

const loading = ref(false)
const shipping = ref(false)
const activeTabKey = ref('all')
const currentPage = ref(1)
const pageSize = ref(20)
const orderIdQuery = ref('')
const orders = ref<XianyuOrder[]>([])
const pageMeta = ref<Pick<XianyuOrderPage, 'total' | 'has_more'>>({ total: 0, has_more: false })
const errorMessage = ref('')

const shipDialogVisible = ref(false)
const shipForm = reactive({
  orderId: '',
  itemTitle: '',
  tradeText: '',
})

const activeStatus = computed(
  () => statusTabs.find((t) => t.key === activeTabKey.value) || statusTabs[0],
)

const stats = computed(() => [
  { label: '订单总数', value: String(pageMeta.value.total || orders.value.length) },
  { label: '当前状态', value: activeStatus.value.label },
  { label: '当前页', value: String(currentPage.value) },
  { label: '每页', value: String(pageSize.value) },
])

function showXianyuAuthHint(message: string) {
  if (message.includes('未配置')) {
    ElMessage.error(message)
    return
  }
  if (message.includes('过期') || message.includes('Cookie') || message.includes('FAIL_SYS_USER_VALIDATE')) {
    ElMessage.warning('闲鱼登录已过期，请前往设置页重新配置 Cookie')
  }
}

async function loadOrders(page = currentPage.value) {
  loading.value = true
  errorMessage.value = ''
  try {
    const response = await listXianyuOrders({
      page,
      page_size: pageSize.value,
      status: activeStatus.value.apiValue,
      order_id: orderIdQuery.value.trim(),
    })
    const data = response.data
    orders.value = data.orders || []
    pageMeta.value = { total: data.total || 0, has_more: !!data.has_more }
    currentPage.value = data.page || page
  } catch (err: any) {
    const msg = err?.message || '获取订单列表失败'
    errorMessage.value = msg
    orders.value = []
    pageMeta.value = { total: 0, has_more: false }
    showXianyuAuthHint(msg)
  } finally {
    loading.value = false
  }
}

async function handleTabChange(key: string) {
  if (loading.value || key === activeTabKey.value) return
  activeTabKey.value = key
  currentPage.value = 1
  await loadOrders(1)
}

async function handleSearch() {
  if (loading.value) return
  currentPage.value = 1
  await loadOrders(1)
}

async function handlePageChange(page: number) {
  if (loading.value || page === currentPage.value) return
  await loadOrders(page)
}

async function handlePageSizeChange(size: number) {
  if (loading.value || size === pageSize.value) return
  pageSize.value = size
  currentPage.value = 1
  await loadOrders(1)
}

function openShipDialog(order: XianyuOrder) {
  shipForm.orderId = order.order_id
  shipForm.itemTitle = order.item_title
  shipForm.tradeText = ''
  shipDialogVisible.value = true
}

async function confirmShip() {
  const orderId = shipForm.orderId
  if (!orderId) {
    ElMessage.warning('订单号为空')
    return
  }
  shipping.value = true
  try {
    const response = await shipXianyuOrder(orderId, shipForm.tradeText.trim())
    if (response.success) {
      ElMessage.success(response.data?.message || '虚拟发货成功')
      shipDialogVisible.value = false
      await loadOrders(currentPage.value)
    } else {
      ElMessage.error(response.error || '虚拟发货失败')
    }
  } catch (err: any) {
    ElMessage.error(err?.message || '虚拟发货失败')
  } finally {
    shipping.value = false
  }
}

function handleQuickShip(order: XianyuOrder) {
  ElMessageBox.confirm(
    `确认对订单 ${order.order_id} 发起虚拟发货？将使用空发货说明，如需填写卡密请点击"发货"`,
    '快速发货',
    { confirmButtonText: '确认', cancelButtonText: '取消', type: 'info' },
  )
    .then(async () => {
      try {
        const response = await shipXianyuOrder(order.order_id, '')
        if (response.success) {
          ElMessage.success('虚拟发货成功')
          await loadOrders(currentPage.value)
        } else {
          ElMessage.error(response.error || '虚拟发货失败')
        }
      } catch (err: any) {
        ElMessage.error(err?.message || '虚拟发货失败')
      }
    })
    .catch(() => void 0)
}

function statusClass(group: string) {
  switch (group) {
    case 'pending_ship': return 'om-status om-status--pending'
    case 'shipped': return 'om-status om-status--shipped'
    case 'completed': return 'om-status om-status--done'
    case 'refunding': return 'om-status om-status--refund'
    case 'cancelled': return 'om-status om-status--cancel'
    default: return 'om-status'
  }
}

onMounted(() => {
  void loadOrders(1)
})
</script>

<template>
  <section class="om-panel theme-surface-card">
    <header class="om-header">
      <div class="om-header__title">
        <el-icon class="om-header__icon"><Box /></el-icon>
        <div>
          <h2>订单管理</h2>
          <p>查看本账号所有订单，支持筛选、搜索与虚拟商品一键发货</p>
        </div>
      </div>

      <div class="om-header__actions">
        <el-button
          :loading="loading"
          :icon="RefreshRight"
          @click="loadOrders(currentPage)"
        >
          刷新
        </el-button>
      </div>
    </header>

    <div class="om-stats">
      <div
        v-for="stat in stats"
        :key="stat.label"
        class="om-stat theme-surface-soft"
      >
        <span>{{ stat.label }}</span>
        <strong>{{ stat.value }}</strong>
      </div>
    </div>

    <nav class="om-tabs">
      <button
        v-for="tab in statusTabs"
        :key="tab.key"
        type="button"
        class="om-tab"
        :class="{ 'om-tab--active': activeTabKey === tab.key }"
        :disabled="loading"
        @click="handleTabChange(tab.key)"
      >
        {{ tab.label }}
      </button>
    </nav>

    <div class="om-search theme-surface-soft">
      <el-input
        v-model="orderIdQuery"
        clearable
        class="om-search__input"
        placeholder="按订单号搜索"
        @keyup.enter="handleSearch"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      <el-button
        type="primary"
        :loading="loading"
        @click="handleSearch"
      >
        查询
      </el-button>
    </div>

    <div
      v-if="errorMessage"
      class="om-error"
    >
      {{ errorMessage }}
    </div>

    <div
      v-if="loading && !orders.length"
      class="om-empty"
    >
      正在加载订单...
    </div>

    <el-empty
      v-else-if="!orders.length && !errorMessage"
      description="当前筛选条件下暂无订单"
    />

    <div
      v-else
      class="om-order-list"
    >
      <article
        v-for="order in orders"
        :key="order.order_id"
        class="om-order theme-surface-soft"
      >
        <div class="om-order__media">
          <img
            v-if="order.item_image"
            :src="order.item_image"
            :alt="order.item_title"
            class="om-order__img"
          >
          <div
            v-else
            class="om-order__img om-order__img--empty"
          >
            无图
          </div>
        </div>

        <div class="om-order__main">
          <div class="om-order__title-row">
            <h3 class="om-order__title">
              {{ order.item_title || '（无标题）' }}
            </h3>
            <span :class="statusClass(order.status_group)">{{ order.status_text || '未知' }}</span>
          </div>

          <div class="om-order__meta">
            <span>订单号 {{ order.order_id }}</span>
            <span v-if="order.item_id">宝贝 {{ order.item_id }}</span>
            <span v-if="order.quantity > 1">数量 ×{{ order.quantity }}</span>
            <span v-if="order.is_dummy">虚拟商品</span>
          </div>

          <div class="om-order__buyer">
            <img
              v-if="order.buyer_avatar"
              :src="order.buyer_avatar"
              :alt="order.buyer_nick"
              class="om-order__buyer-avatar"
            >
            <span class="om-order__buyer-nick">{{ order.buyer_nick || '匿名买家' }}</span>
            <span
              v-if="order.remark"
              class="om-order__remark"
            >"{{ order.remark }}"</span>
          </div>

          <div class="om-order__footer">
            <div class="om-order__time">
              <span v-if="order.paid_at">付款 {{ order.paid_at }}</span>
              <span v-else-if="order.created_at">下单 {{ order.created_at }}</span>
              <span v-if="order.finished_at">完成 {{ order.finished_at }}</span>
            </div>
            <div class="om-order__price">
              <strong>￥{{ order.amount || '--' }}</strong>
            </div>
          </div>
        </div>

        <div class="om-order__actions">
          <template v-if="order.status_group === 'pending_ship'">
            <el-button
              type="primary"
              size="small"
              :icon="Van"
              @click="openShipDialog(order)"
            >
              发货
            </el-button>
            <el-button
              size="small"
              :icon="Promotion"
              @click="handleQuickShip(order)"
            >
              快速发货
            </el-button>
          </template>
          <span
            v-else
            class="om-order__hint"
          >
            {{
              order.status_group === 'shipped' ? '已发货，等待买家确认'
              : order.status_group === 'completed' ? '订单已完成'
              : order.status_group === 'refunding' ? '售后处理中'
              : order.status_group === 'cancelled' ? '订单已关闭'
              : '暂无操作'
            }}
          </span>
        </div>
      </article>
    </div>

    <div
      v-if="orders.length"
      class="om-pagination"
    >
      <el-pagination
        background
        layout="sizes, prev, pager, next, jumper, ->, total"
        :current-page="currentPage"
        :page-size="pageSize"
        :page-sizes="[10, 20, 30, 50]"
        :total="pageMeta.total"
        :disabled="loading"
        @current-change="handlePageChange"
        @size-change="handlePageSizeChange"
      />
    </div>

    <el-dialog
      v-model="shipDialogVisible"
      title="虚拟商品发货"
      width="520px"
      append-to-body
    >
      <div class="om-ship-dialog">
        <div class="om-ship-dialog__item">
          <span>订单号</span>
          <strong>{{ shipForm.orderId }}</strong>
        </div>
        <div class="om-ship-dialog__item">
          <span>商品</span>
          <strong>{{ shipForm.itemTitle || '未知商品' }}</strong>
        </div>
        <div class="om-ship-dialog__field">
          <label>发货说明 / 卡密</label>
          <el-input
            v-model="shipForm.tradeText"
            type="textarea"
            :rows="4"
            placeholder="可选：输入卡密、兑换码或其他发货说明，留空则提交空确认"
          />
        </div>
        <div class="om-ship-dialog__tip">
          此功能调用闲鱼"免物流确认发货"接口（mtop.taobao.idle.logistic.consign.dummy），仅适用于虚拟商品。请确认订单是否为虚拟类目后再提交。
        </div>
      </div>

      <template #footer>
        <el-button @click="shipDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="shipping"
          @click="confirmShip"
        >
          确认发货
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.om-panel {
  display: grid;
  gap: 18px;
  padding: 24px;
  border-radius: 20px;
  border: 1px solid rgba(var(--app-border-rgb) / 0.46);
  background:
    linear-gradient(135deg, rgba(var(--app-surface-rgb) / 0.92), rgba(var(--app-surface-alt-rgb) / 0.86));
  box-shadow: 0 14px 36px rgba(var(--app-shadow-rgb) / 0.08);
}

.om-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.om-header__title {
  display: flex;
  align-items: center;
  gap: 14px;
}

.om-header__icon {
  width: 44px;
  height: 44px;
  display: grid;
  place-items: center;
  border-radius: 14px;
  font-size: 22px;
  color: rgb(var(--utility-white-rgb));
  background: linear-gradient(135deg, rgba(var(--primary-color-rgb) / 0.94), rgba(var(--app-accent-alt-rgb) / 0.88));
  box-shadow: 0 10px 24px rgba(var(--primary-color-rgb) / 0.2);
}

.om-header__title h2 {
  margin: 0;
  color: rgb(var(--app-text-strong-rgb));
  font-size: 20px;
  line-height: 1.2;
}

.om-header__title p {
  margin: 4px 0 0;
  color: rgb(var(--app-text-muted-rgb));
  font-size: 12px;
  line-height: 1.4;
}

.om-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.om-stat {
  display: grid;
  gap: 4px;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid rgba(var(--app-border-rgb) / 0.42);
}

.om-stat span {
  color: rgb(var(--app-text-subtle-rgb));
  font-size: 12px;
}

.om-stat strong {
  color: rgb(var(--app-text-strong-rgb));
  font-size: 16px;
  line-height: 1.2;
}

.om-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.om-tab {
  border: 1px solid rgba(var(--app-border-rgb) / 0.42);
  background: rgba(var(--app-surface-rgb) / 0.86);
  color: rgb(var(--app-text-rgb));
  border-radius: 999px;
  padding: 8px 16px;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.2s ease, color 0.2s ease, transform 0.2s ease;
}

.om-tab:hover:not(:disabled) {
  background: rgba(var(--app-surface-alt-rgb) / 0.76);
}

.om-tab--active {
  color: rgb(var(--utility-white-rgb));
  background: linear-gradient(135deg, rgba(var(--primary-color-rgb) / 0.94), rgba(var(--app-accent-alt-rgb) / 0.88));
  border-color: transparent;
  box-shadow: 0 10px 20px rgba(var(--primary-color-rgb) / 0.18);
}

.om-tab:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.om-search {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
  padding: 12px;
  border-radius: 16px;
  border: 1px solid rgba(var(--app-border-rgb) / 0.42);
}

.om-search__input :deep(.el-input__wrapper) {
  min-height: 40px;
  border-radius: 999px;
}

.om-error {
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.18);
  color: rgb(var(--app-text-strong-rgb));
  line-height: 1.6;
}

.om-empty {
  padding: 60px 20px;
  text-align: center;
  color: rgb(var(--app-text-muted-rgb));
}

.om-order-list {
  display: grid;
  gap: 12px;
}

.om-order {
  display: grid;
  grid-template-columns: 100px minmax(0, 1fr) auto;
  gap: 16px;
  padding: 14px;
  border-radius: 16px;
  border: 1px solid rgba(var(--app-border-rgb) / 0.42);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.om-order:hover {
  transform: translateY(-1px);
  box-shadow: 0 10px 22px rgba(var(--app-shadow-rgb) / 0.08);
}

.om-order__media {
  width: 100px;
  height: 100px;
  border-radius: 12px;
  overflow: hidden;
  background: rgba(var(--app-surface-alt-rgb) / 0.6);
}

.om-order__img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.om-order__img--empty {
  display: grid;
  place-items: center;
  color: rgb(var(--app-text-subtle-rgb));
  font-size: 12px;
}

.om-order__main {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.om-order__title-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.om-order__title {
  margin: 0;
  color: rgb(var(--app-text-strong-rgb));
  font-size: 15px;
  line-height: 1.4;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.om-status {
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
  color: rgb(var(--app-text-muted-rgb));
  background: rgba(var(--app-surface-alt-rgb) / 0.8);
}

.om-status--pending { color: rgb(var(--utility-white-rgb)); background: #f59e0b; }
.om-status--shipped { color: rgb(var(--utility-white-rgb)); background: #3b82f6; }
.om-status--done { color: rgb(var(--utility-white-rgb)); background: #10b981; }
.om-status--refund { color: rgb(var(--utility-white-rgb)); background: #ef4444; }
.om-status--cancel { color: rgb(var(--app-text-muted-rgb)); background: rgba(var(--app-surface-alt-rgb) / 0.8); }

.om-order__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  color: rgb(var(--app-text-subtle-rgb));
  font-size: 12px;
}

.om-order__buyer {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.om-order__buyer-avatar {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  object-fit: cover;
}

.om-order__buyer-nick {
  color: rgb(var(--app-text-rgb));
  font-size: 13px;
}

.om-order__remark {
  color: rgb(var(--app-text-muted-rgb));
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.om-order__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.om-order__time {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  color: rgb(var(--app-text-subtle-rgb));
  font-size: 12px;
}

.om-order__price strong {
  color: rgb(var(--primary-color-rgb));
  font-size: 18px;
  font-weight: 700;
}

.om-order__actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: flex-end;
  justify-content: center;
}

.om-order__hint {
  color: rgb(var(--app-text-subtle-rgb));
  font-size: 12px;
  text-align: right;
}

.om-pagination {
  display: flex;
  justify-content: center;
  padding-top: 8px;
}

.om-ship-dialog {
  display: grid;
  gap: 14px;
}

.om-ship-dialog__item {
  display: flex;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(var(--app-surface-alt-rgb) / 0.6);
}

.om-ship-dialog__item span {
  color: rgb(var(--app-text-subtle-rgb));
  font-size: 13px;
  min-width: 60px;
}

.om-ship-dialog__item strong {
  color: rgb(var(--app-text-strong-rgb));
  font-size: 13px;
  word-break: break-all;
}

.om-ship-dialog__field {
  display: grid;
  gap: 6px;
}

.om-ship-dialog__field label {
  color: rgb(var(--app-text-muted-rgb));
  font-size: 13px;
}

.om-ship-dialog__tip {
  padding: 10px 12px;
  border-radius: 10px;
  font-size: 12px;
  line-height: 1.6;
  color: rgb(var(--app-text-muted-rgb));
  background: rgba(245, 158, 11, 0.08);
  border: 1px solid rgba(245, 158, 11, 0.18);
}

@media (max-width: 840px) {
  .om-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .om-order { grid-template-columns: 80px minmax(0, 1fr); }
  .om-order__media { width: 80px; height: 80px; }
  .om-order__actions {
    grid-column: 1 / -1;
    flex-direction: row;
    justify-content: flex-start;
  }
}
</style>
