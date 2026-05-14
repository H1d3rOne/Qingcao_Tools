<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { CopyDocument, Delete, EditPen, Plus, SwitchButton } from '@element-plus/icons-vue'
import {
  createXianyuDeliveryRule,
  deleteXianyuDeliveryRule,
  listXianyuDeliveryRules,
  toggleXianyuDeliveryRule,
  updateXianyuDeliveryRule,
  type XianyuDeliveryRule,
} from '@/api/modules/xianyu'

interface DeliveryFormState {
  name: string
  match_mode: 'item_id' | 'keyword'
  match_value: string
  delivery_text: string
  send_chat_text: boolean
  send_dummy_ship: boolean
}

const loading = ref(false)
const saving = ref(false)
const rules = ref<XianyuDeliveryRule[]>([])
const dialogVisible = ref(false)
const editingRuleId = ref('')
const formState = reactive<DeliveryFormState>({
  name: '',
  match_mode: 'keyword',
  match_value: '',
  delivery_text: '',
  send_chat_text: true,
  send_dummy_ship: true,
})

const enabledCount = computed(() => rules.value.filter((r) => r.enabled).length)
const stats = computed(() => [
  { label: '规则总数', value: `${rules.value.length}`, unit: '条', accent: false },
  { label: '已启用', value: `${enabledCount.value}`, unit: '条', accent: enabledCount.value > 0 },
  { label: '已停用', value: `${rules.value.length - enabledCount.value}`, unit: '条', accent: false },
])

const dialogTitle = computed(() => (editingRuleId.value ? '编辑发货规则' : '新建发货规则'))

function resetForm() {
  formState.name = ''
  formState.match_mode = 'keyword'
  formState.match_value = ''
  formState.delivery_text = ''
  formState.send_chat_text = true
  formState.send_dummy_ship = true
  editingRuleId.value = ''
}

function openCreateDialog() {
  resetForm()
  dialogVisible.value = true
}

function openEditDialog(rule: XianyuDeliveryRule) {
  editingRuleId.value = rule.id
  formState.name = rule.name
  formState.match_mode = rule.match_mode
  formState.match_value = rule.match_value
  formState.delivery_text = rule.delivery_text
  formState.send_chat_text = rule.send_chat_text
  formState.send_dummy_ship = rule.send_dummy_ship
  dialogVisible.value = true
}

async function loadRules() {
  loading.value = true
  try {
    const response = await listXianyuDeliveryRules()
    rules.value = response.data || []
  } catch (error: any) {
    ElMessage.error(error?.message || '加载发货规则失败')
  } finally {
    loading.value = false
  }
}

async function handleSubmit() {
  const name = formState.name.trim()
  const matchValue = formState.match_value.trim()
  const deliveryText = formState.delivery_text.trim()

  if (!name) {
    ElMessage.warning('请输入规则名称')
    return
  }
  if (!matchValue) {
    ElMessage.warning('请输入匹配值')
    return
  }
  if (!deliveryText) {
    ElMessage.warning('请输入发货文本')
    return
  }

  saving.value = true
  try {
    const payload = {
      name,
      match_mode: formState.match_mode,
      match_value: matchValue,
      delivery_text: deliveryText,
      send_chat_text: formState.send_chat_text,
      send_dummy_ship: formState.send_dummy_ship,
    }

    if (editingRuleId.value) {
      await updateXianyuDeliveryRule(editingRuleId.value, payload)
      ElMessage.success('发货规则已更新')
    } else {
      await createXianyuDeliveryRule(payload)
      ElMessage.success('发货规则已创建')
    }

    dialogVisible.value = false
    await loadRules()
  } catch (error: any) {
    ElMessage.error(error?.message || '保存发货规则失败')
  } finally {
    saving.value = false
  }
}

async function handleToggle(rule: XianyuDeliveryRule) {
  try {
    await toggleXianyuDeliveryRule(rule.id)
    rule.enabled = !rule.enabled
    ElMessage.success(rule.enabled ? '规则已启用' : '规则已停用')
  } catch (error: any) {
    ElMessage.error(error?.message || '切换规则状态失败')
  }
}

async function handleDelete(rule: XianyuDeliveryRule) {
  try {
    await ElMessageBox.confirm(
      `确定删除规则「${rule.name}」吗？`,
      '删除规则',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
    await deleteXianyuDeliveryRule(rule.id)
    ElMessage.success('发货规则已删除')
    await loadRules()
  } catch (error: any) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(error?.message || '删除发货规则失败')
  }
}

function copyText(text: string) {
  navigator.clipboard.writeText(text).then(
    () => ElMessage.success('已复制到剪贴板'),
    () => ElMessage.warning('复制失败，请手动复制'),
  )
}

function matchModeLabel(mode: string) {
  return mode === 'item_id' ? '商品 ID' : '关键字'
}

onMounted(() => {
  void loadRules()
})
</script>

<template>
  <section class="mg-section">
    <div class="mg-section__head">
      <div class="mg-section__info">
        <h3>自动发货</h3>
        <p>配置发货规则，按商品 ID 或关键字匹配并自动发货</p>
      </div>
      <div class="mg-section__actions">
        <el-button type="primary" @click="openCreateDialog">
          <el-icon><Plus /></el-icon>
          新建规则
        </el-button>
      </div>
    </div>

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

    <el-empty v-if="!loading && !rules.length" description="暂无发货规则" />

    <div v-else class="mg-rule-list">
      <article
        v-for="rule in rules"
        :key="rule.id"
        class="mg-rule"
        :class="{ 'mg-rule--disabled': !rule.enabled }"
      >
        <div class="mg-rule__header">
          <div class="mg-rule__title">
            <div class="mg-rule__name-row">
              <span
                class="mg-rule__dot"
                :class="{ 'mg-rule__dot--on': rule.enabled }"
              />
              <strong>{{ rule.name }}</strong>
              <span class="mg-rule__mode">{{ matchModeLabel(rule.match_mode) }}</span>
            </div>
            <div class="mg-rule__summary">
              <span class="mg-rule__summary-text">匹配 {{ rule.match_value }}</span>
            </div>
            <div class="mg-rule__meta">
              <span class="mg-rule__summary-text">{{ rule.enabled ? '规则启用中' : '规则已停用' }}</span>
              <span class="mg-rule__summary-text">{{ rule.send_chat_text ? '发送聊天' : '不发聊天' }}</span>
            </div>
          </div>
          <div class="mg-rule__primary-actions">
            <el-button size="small" @click="handleToggle(rule)">
              <el-icon><SwitchButton /></el-icon>
              {{ rule.enabled ? '停用' : '启用' }}
            </el-button>
            <el-button size="small" @click="openEditDialog(rule)">
              <el-icon><EditPen /></el-icon>
              编辑
            </el-button>
            <el-button size="small" type="danger" plain @click="handleDelete(rule)">
              <el-icon><Delete /></el-icon>
              删除
            </el-button>
          </div>
        </div>

        <div class="mg-rule__body">
          <div class="mg-rule__body-grid">
            <div class="mg-rule__match">
              <span class="mg-rule__match-label">匹配值</span>
              <code>{{ rule.match_value }}</code>
            </div>
            <div class="mg-rule__delivery">
              <span class="mg-rule__match-label">发货文本</span>
              <span class="mg-rule__delivery-text">{{ rule.delivery_text }}</span>
              <el-button text size="small" type="primary" @click="copyText(rule.delivery_text)">
                <el-icon><CopyDocument /></el-icon>
                复制文本
              </el-button>
            </div>
          </div>
          <div class="mg-rule__flags">
            <span v-if="rule.send_chat_text" class="mg-rule__flag mg-rule__flag--chat">发送聊天</span>
            <span v-if="rule.send_dummy_ship" class="mg-rule__flag mg-rule__flag--virtual">虚拟发货</span>
          </div>
        </div>
      </article>
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="600px"
      append-to-body
    >
      <el-form label-position="top" class="mg-form">
        <div class="mg-form__section">
          <div class="mg-form__section-title">基本信息</div>
          <div class="mg-form__row">
            <el-form-item label="规则名称" class="mg-form__field">
              <el-input v-model="formState.name" maxlength="50" placeholder="例如：卡密自动发货" show-word-limit />
            </el-form-item>
            <el-form-item label="匹配模式" class="mg-form__field">
              <el-select v-model="formState.match_mode">
                <el-option label="按商品 ID 精确匹配" value="item_id" />
                <el-option label="按关键字模糊匹配" value="keyword" />
              </el-select>
            </el-form-item>
          </div>
          <el-form-item label="匹配值">
            <el-input v-model="formState.match_value" placeholder="输入商品 ID 或关键字" />
          </el-form-item>
        </div>

        <div class="mg-form__section">
          <div class="mg-form__section-title">发货配置</div>
          <el-form-item label="发货文本">
            <el-input v-model="formState.delivery_text" type="textarea" :rows="4" placeholder="输入发货内容（如卡密、下载链接等）" />
          </el-form-item>
          <div class="mg-form__row">
            <el-form-item label="发送聊天文本">
              <el-switch v-model="formState.send_chat_text" active-text="开启" inactive-text="关闭" />
            </el-form-item>
            <el-form-item label="调用虚拟发货">
              <el-switch v-model="formState.send_dummy_ship" active-text="开启" inactive-text="关闭" />
            </el-form-item>
          </div>
        </div>
      </el-form>

      <template #footer>
        <div class="mg-form__footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="saving" @click="handleSubmit">保存规则</el-button>
        </div>
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
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
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
  color: rgb(22, 163, 74);
}

.mg-stat__unit {
  font-size: 13px;
  color: rgb(var(--app-text-subtle-rgb));
}

.mg-rule-list {
  display: grid;
  gap: 10px;
}

.mg-rule {
  display: grid;
  gap: 10px;
  padding: 14px 16px;
  border-radius: 10px;
  border: 1px solid rgba(var(--app-border-rgb) / 0.3);
  background: rgba(var(--app-surface-rgb) / 0.6);
  transition: border-color 0.15s ease, background 0.15s ease;
}

.mg-rule:hover {
  border-color: rgba(var(--app-accent-rgb) / 0.3);
  background: rgba(var(--app-surface-rgb) / 0.85);
}

.mg-rule--disabled {
  opacity: 0.6;
}

.mg-rule__header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.mg-rule__title {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.mg-rule__name-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.mg-rule__dot {
  flex-shrink: 0;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: rgb(var(--app-text-subtle-rgb));
}

.mg-rule__dot--on {
  background: rgb(34, 197, 94);
  box-shadow: 0 0 6px rgba(34, 197, 94, 0.4);
}

.mg-rule__name-row strong {
  font-size: 14px;
  font-weight: 600;
  color: rgb(var(--app-text-strong-rgb));
}

.mg-rule__mode {
  padding: 1px 8px;
  border-radius: 4px;
  background: rgba(var(--app-accent-rgb) / 0.08);
  border: 1px solid rgba(var(--app-accent-rgb) / 0.15);
  font-size: 11px;
  font-weight: 500;
  color: rgb(var(--app-accent-rgb));
}

.mg-rule__primary-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.mg-rule__summary,
.mg-rule__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding-left: 15px;
}

.mg-rule__summary-text {
  font-size: 12px;
  color: rgb(var(--app-text-subtle-rgb));
}

.mg-rule__body {
  display: grid;
  gap: 8px;
  padding-left: 15px;
}

.mg-rule__body-grid {
  display: grid;
  gap: 8px;
}

.mg-rule__match,
.mg-rule__delivery {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.mg-rule__match-label {
  font-size: 12px;
  color: rgb(var(--app-text-subtle-rgb));
  flex-shrink: 0;
}

.mg-rule__match code {
  padding: 2px 8px;
  border-radius: 4px;
  background: rgba(var(--app-surface-alt-rgb) / 0.8);
  font-size: 12px;
  font-family: monospace;
  color: rgb(var(--app-text-strong-rgb));
}

.mg-rule__delivery-text {
  font-size: 13px;
  color: rgb(var(--app-text-strong-rgb));
  max-width: 400px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mg-rule__flags {
  display: flex;
  gap: 6px;
}

.mg-rule__flag {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}

.mg-rule__flag--chat {
  background: rgba(59, 130, 246, 0.1);
  color: rgb(37, 99, 235);
}

.mg-rule__flag--virtual {
  background: rgba(168, 85, 247, 0.1);
  color: rgb(147, 51, 234);
}

.mg-form {
  padding-top: 4px;
}

.mg-form__section {
  margin-bottom: 20px;
}

.mg-form__section:last-child {
  margin-bottom: 0;
}

.mg-form__section-title {
  margin-bottom: 12px;
  padding-bottom: 6px;
  font-size: 13px;
  font-weight: 600;
  color: rgb(var(--app-text-subtle-rgb));
  letter-spacing: 0.02em;
  border-bottom: 1px solid rgba(var(--app-border-rgb) / 0.2);
}

.mg-form__row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 16px;
}

.mg-form__footer {
  display: flex;
  justify-content: end;
  gap: 8px;
}

@media (max-width: 768px) {
  .mg-stats {
    grid-template-columns: 1fr 1fr 1fr;
  }

  .mg-rule__header {
    flex-direction: column;
    align-items: flex-start;
  }

  .mg-form__row {
    grid-template-columns: 1fr;
  }
}
</style>
