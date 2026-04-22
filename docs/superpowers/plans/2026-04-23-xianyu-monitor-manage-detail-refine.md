# 咸鱼监控页与管理页第二轮细节精修 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改接口与业务能力的前提下，对咸鱼监控页与管理页做第二轮统一细节精修，提升摘要区、操作区、主内容区与辅助区的扫读效率和视觉一致性。

**Architecture:** 继续沿用现有 `web-vue/src/views/xianyu/components/` 组件边界，不新增业务组件层，不改 API 模块；通过模板层级微调、样式类重组和少量 computed 文案收敛，分别在监控页、管理中心壳层、商品管理、自动发货、运行状态内完成信息分层。测试层继续使用现有 Vitest 组件测试，对新增视觉结构锚点和保留交互逻辑做回归验证。

**Tech Stack:** Vue 3 + `<script setup lang="ts">`、Element Plus、Vitest、Vite、pnpm

---

## 文件结构与责任边界

### 现有文件

- `web-vue/src/views/xianyu/components/XianyuMonitorPanel.vue`
  - 负责监控任务列表、当前任务详情、命中商品预览与相关操作
- `web-vue/src/views/xianyu/components/XianyuManagePanel.vue`
  - 负责管理中心壳层、概览区和三个模块入口卡
- `web-vue/src/views/xianyu/components/XianyuManageItemsPanel.vue`
  - 负责商品缓存列表、同步操作、编辑详情、多数量发货开关
- `web-vue/src/views/xianyu/components/XianyuManageDeliveryPanel.vue`
  - 负责自动发货规则列表、规则编辑、启停、复制文本
- `web-vue/src/views/xianyu/components/XianyuManageRuntimePanel.vue`
  - 负责运行状态摘要、时间信息和最近执行记录
- `web-vue/src/views/xianyu/components/XianyuMonitorPanel.spec.ts`
  - 监控页交互与结构锚点测试
- `web-vue/src/views/xianyu/components/XianyuManagePanel.spec.ts`
  - 管理中心壳层测试
- `web-vue/src/views/xianyu/components/XianyuManageItemsPanel.spec.ts`
  - 商品管理列表、价格、辅助区、分页删除等测试
- `web-vue/src/views/xianyu/components/XianyuManageDeliveryPanel.spec.ts`
  - 自动发货规则表单、删除、复制、结构锚点测试
- `web-vue/src/views/xianyu/components/XianyuManageRuntimePanel.spec.ts`
  - 运行状态摘要、自动刷新和执行记录测试

### 本轮不新增文件

本轮只修改上述现有组件与测试文件，并新增这份计划文档；不引入新的 API、store、composable 或通用 UI 组件。

---

### Task 1: 监控页摘要区与命中预览细化

**Files:**
- Modify: `web-vue/src/views/xianyu/components/XianyuMonitorPanel.vue`
- Test: `web-vue/src/views/xianyu/components/XianyuMonitorPanel.spec.ts`

- [ ] **Step 1: 先写失败测试，锁定新的摘要层级与预览条结构**

```ts
it('renders compact task identity row, meta strip and hit preview summary row', async () => {
  const wrapper = buildWrapper()
  await flushPromises()

  expect(wrapper.find('.mp-detail__identity').exists()).toBe(true)
  expect(wrapper.find('.mp-detail__action-group').exists()).toBe(true)
  expect(wrapper.findAll('.mp-detail__meta-pill')).toHaveLength(4)
  expect(wrapper.find('.mp-hits__preview').exists()).toBe(true)
  expect(wrapper.find('.mp-hits__latest').text()).toContain('4060 显卡')
})
```

- [ ] **Step 2: 运行单测，确认它先失败**

Run:
```bash
cd web-vue
pnpm exec vitest run src/views/xianyu/components/XianyuMonitorPanel.spec.ts
```

Expected: FAIL，提示 `.mp-detail__identity`、`.mp-detail__action-group` 或 `.mp-hits__preview` 尚不存在。

- [ ] **Step 3: 在组件中做最小实现，重排摘要头与预览条**

```vue
<div class="mp-detail__summary-head">
  <div class="mp-detail__identity">
    <div class="mp-detail__title-block">
      <h3 class="mp-detail__title">{{ activeTask.name }}</h3>
      <span class="mp-detail__state" :class="{ 'mp-detail__state--on': activeTask.enabled }">
        {{ activeTask.enabled ? '启用中' : '已停用' }}
      </span>
    </div>
    <div class="mp-detail__action-group">
      <el-button type="primary" size="small" @click="handleRun(activeTask)">立即执行</el-button>
      <el-button size="small" @click="handleToggle(activeTask)">{{ activeTask.enabled ? '暂停' : '启用' }}</el-button>
      <el-button size="small" @click="openEditDialog(activeTask)">编辑</el-button>
      <el-button size="small" type="danger" plain @click="handleDelete(activeTask)">删除</el-button>
    </div>
  </div>
  <div class="mp-detail__meta-row">
    <span class="mp-detail__meta-pill">关键词 {{ activeTask.keyword }}</span>
    <span class="mp-detail__meta-pill">{{ formatInterval(activeTask.interval_seconds) }}</span>
    <span class="mp-detail__meta-pill">{{ buildTaskPriceRange(activeTask) }}</span>
    <span class="mp-detail__meta-pill">最近执行 {{ formatTimestamp(activeTask.last_run_at) }}</span>
  </div>
</div>

<div class="mp-hits__preview">
  <div class="mp-hits__preview-main">
    <strong>{{ activeHits.length }} 条命中</strong>
    <span class="mp-hits__latest">{{ activeHits[0]?.title || '暂无最近命中' }}</span>
  </div>
  <button type="button" class="mp-hits__toggle" @click="toggleHitsPreview">
    {{ hitsExpanded ? '收起预览' : '展开预览' }}
  </button>
</div>
```

```ts
function buildTaskPriceRange(task: Pick<XianyuMonitorTask, 'min_price' | 'max_price'>) {
  if (task.min_price != null && task.max_price != null) return `价格 ¥${task.min_price} - ¥${task.max_price}`
  if (task.min_price != null) return `最低 ¥${task.min_price}`
  if (task.max_price != null) return `最高 ¥${task.max_price}`
  return '价格不限'
}
```

```css
.mp-detail__identity {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.mp-detail__action-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.mp-hits__preview {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid rgba(var(--app-border-rgb), 0.28);
  background: rgba(var(--app-surface-rgb), 0.72);
}
```

- [ ] **Step 4: 重跑监控页测试，确认通过且保留折叠逻辑**

Run:
```bash
cd web-vue
pnpm exec vitest run src/views/xianyu/components/XianyuMonitorPanel.spec.ts
```

Expected: PASS，原有“默认折叠 / 展开 / 切换任务自动折叠”断言仍通过，并新增摘要层级断言通过。

- [ ] **Step 5: 提交监控页任务**

```bash
git add web-vue/src/views/xianyu/components/XianyuMonitorPanel.vue web-vue/src/views/xianyu/components/XianyuMonitorPanel.spec.ts
git commit -m "feat: refine xianyu monitor summary rhythm"
```

### Task 2: 管理中心壳层与模块入口卡收紧

**Files:**
- Modify: `web-vue/src/views/xianyu/components/XianyuManagePanel.vue`
- Test: `web-vue/src/views/xianyu/components/XianyuManagePanel.spec.ts`

- [ ] **Step 1: 先补失败测试，锁定概览区与模块卡的新壳层锚点**

```ts
it('renders overview summary line and active module intro block', () => {
  const wrapper = shallowMount(XianyuManagePanel, {
    props: { currentUser: { display_name: '会飞的猪' } },
    global: { stubs: { XianyuManageItemsPanel: true, XianyuManageDeliveryPanel: true, XianyuManageRuntimePanel: true, 'el-icon': true } },
  })

  expect(wrapper.find('.mg-overview__headline').exists()).toBe(true)
  expect(wrapper.find('.mg-tabs-shell__intro').exists()).toBe(true)
  expect(wrapper.find('.mg-tab--active .mg-tab__hint').text()).toContain('默认工作区')
})
```

- [ ] **Step 2: 运行壳层测试，确认当前代码还不满足**

Run:
```bash
cd web-vue
pnpm exec vitest run src/views/xianyu/components/XianyuManagePanel.spec.ts
```

Expected: FAIL，提示 `.mg-overview__headline`、`.mg-tabs-shell__intro` 或 `.mg-tab__hint` 缺失。

- [ ] **Step 3: 实现概览 headline、入口卡 hint 与当前焦点说明**

```ts
const activeTabMeta = computed(() => tabs.value.find((tab) => tab.key === activeTab.value) || tabs.value[0])
```

```vue
<div class="mg-overview__headline">
  <strong>管理中心</strong>
  <span>统一查看当前账号、默认入口与当前焦点</span>
</div>

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

<div class="mg-tab__text">
  <strong>{{ tab.label }}</strong>
  <span>{{ tab.hint }}</span>
  <small class="mg-tab__hint">{{ activeTab === tab.key ? '默认工作区节奏' : '点击切换模块' }}</small>
</div>
```

```css
.mg-overview__headline {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.mg-tabs-shell__intro {
  display: grid;
  gap: 2px;
  justify-items: end;
  text-align: right;
}

.mg-tab__hint {
  font-size: 12px;
  color: rgb(var(--app-text-subtle-rgb));
}
```

- [ ] **Step 4: 重跑壳层测试，确认默认 active 逻辑仍正确**

Run:
```bash
cd web-vue
pnpm exec vitest run src/views/xianyu/components/XianyuManagePanel.spec.ts
```

Expected: PASS，仍然默认激活“商品管理”，并且新的概览 headline / intro 块存在。

- [ ] **Step 5: 提交管理壳层任务**

```bash
git add web-vue/src/views/xianyu/components/XianyuManagePanel.vue web-vue/src/views/xianyu/components/XianyuManagePanel.spec.ts
git commit -m "feat: tighten xianyu manage shell hierarchy"
```

### Task 3: 商品管理列表扫读节奏精修

**Files:**
- Modify: `web-vue/src/views/xianyu/components/XianyuManageItemsPanel.vue`
- Test: `web-vue/src/views/xianyu/components/XianyuManageItemsPanel.spec.ts`

- [ ] **Step 1: 先加失败测试，锁定商品元信息与操作层级锚点**

```ts
it('renders item meta strip, highlighted price block and primary action row', async () => {
  const wrapper = buildWrapper()
  await flushPromises()

  expect(wrapper.find('.mg-item__meta').exists()).toBe(true)
  expect(wrapper.find('.mg-item__price-block').exists()).toBe(true)
  expect(wrapper.find('.mg-item__status').text()).toContain('在售')
  expect(wrapper.find('.mg-item__primary-action').text()).toContain('多数量发货')
})
```

- [ ] **Step 2: 运行商品管理测试，确认新结构尚未存在**

Run:
```bash
cd web-vue
pnpm exec vitest run src/views/xianyu/components/XianyuManageItemsPanel.spec.ts
```

Expected: FAIL，提示 `.mg-item__meta`、`.mg-item__price-block` 或 `.mg-item__primary-action` 缺失。

- [ ] **Step 3: 在商品卡片中实现状态元信息、价格块和主次操作区**

```ts
function itemStatusLabel(status: string) {
  if (status === 'onsale') return '在售'
  if (status === 'offline') return '已下架'
  return status || '未知状态'
}

function formatItemTime(value: number) {
  if (!value) return '未知时间'
  const date = new Date(value * 1000)
  return `${date.getMonth() + 1}/${date.getDate()} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}
```

```vue
<div class="mg-item__body">
  <div class="mg-item__header">
    <div class="mg-item__title-wrap">
      <strong>{{ item.item_title || item.item_id }}</strong>
      <span class="mg-item__id">ID {{ item.item_id }}</span>
    </div>
    <div class="mg-item__price-block">
      <span class="mg-item__price-label">价格</span>
      <span class="mg-item__price-pill" :class="{ 'mg-item__price-pill--muted': !hasPrice(item.item_price) }">
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
    <el-switch :model-value="item.multi_quantity_delivery" active-text="多数量发货" @change="toggleMultiQuantity(item, Boolean($event))" />
  </div>
  <div class="mg-item__btns">
    <el-button size="small" @click="openEdit(item)">编辑</el-button>
    <el-button size="small" type="danger" plain @click="removeItem(item)">删除</el-button>
  </div>
</div>
```

```css
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

.mg-item__price-block {
  display: grid;
  justify-items: end;
  gap: 4px;
}
```

- [ ] **Step 4: 重跑商品管理测试，确认封面 / 价格 / 删除 / 分页仍然通过**

Run:
```bash
cd web-vue
pnpm exec vitest run src/views/xianyu/components/XianyuManageItemsPanel.spec.ts
```

Expected: PASS，既有封面、占位、价格、分页删除测试不回退，新元信息结构断言通过。

- [ ] **Step 5: 提交商品管理任务**

```bash
git add web-vue/src/views/xianyu/components/XianyuManageItemsPanel.vue web-vue/src/views/xianyu/components/XianyuManageItemsPanel.spec.ts
git commit -m "feat: polish xianyu manage items readability"
```

### Task 4: 自动发货与运行状态的统一工作区节奏

**Files:**
- Modify: `web-vue/src/views/xianyu/components/XianyuManageDeliveryPanel.vue`
- Modify: `web-vue/src/views/xianyu/components/XianyuManageRuntimePanel.vue`
- Test: `web-vue/src/views/xianyu/components/XianyuManageDeliveryPanel.spec.ts`
- Test: `web-vue/src/views/xianyu/components/XianyuManageRuntimePanel.spec.ts`

- [ ] **Step 1: 先写失败测试，覆盖规则卡摘要区和执行记录关键信息区**

```ts
it('renders delivery rule meta strip and primary action cluster', async () => {
  mocks.listXianyuDeliveryRules.mockResolvedValue({
    data: [{ id: 'rule-1', name: '现货卡密', enabled: true, match_mode: 'item_id', match_value: '1001', delivery_text: '复制这段卡密', send_chat_text: true, send_dummy_ship: true, created_at: 1, updated_at: 1 }],
  })
  const wrapper = buildWrapper()
  await flushPromises()

  expect(wrapper.find('.mg-rule__meta').exists()).toBe(true)
  expect(wrapper.find('.mg-rule__primary-actions').exists()).toBe(true)
})
```

```ts
it('renders runtime focus summary and execution reason text', async () => {
  const wrapper = mount(XianyuManageRuntimePanel, { global: { stubs: { 'el-button': { template: '<button @click="$emit(\'click\')"><slot /></button>' }, 'el-icon': true, 'el-empty': true } } })
  await flushPromises()

  expect(wrapper.find('.mg-runtime-summary__focus').exists()).toBe(true)
  expect(wrapper.find('.mg-exec__reason').text()).toContain('delivered')
})
```

- [ ] **Step 2: 分别运行两个测试文件，确认新结构先失败**

Run:
```bash
cd web-vue
pnpm exec vitest run src/views/xianyu/components/XianyuManageDeliveryPanel.spec.ts src/views/xianyu/components/XianyuManageRuntimePanel.spec.ts
```

Expected: FAIL，提示 `.mg-rule__meta`、`.mg-rule__primary-actions`、`.mg-runtime-summary__focus` 或 `.mg-exec__reason` 缺失。

- [ ] **Step 3: 实现规则卡 meta 条、主操作簇和执行记录原因文本**

```vue
<div class="mg-rule__header">
  <div class="mg-rule__title">
    <div class="mg-rule__name-row">
      <span class="mg-rule__dot" :class="{ 'mg-rule__dot--on': rule.enabled }" />
      <strong>{{ rule.name }}</strong>
      <span class="mg-rule__mode">{{ matchModeLabel(rule.match_mode) }}</span>
    </div>
    <div class="mg-rule__meta">
      <span class="mg-rule__summary-text">匹配 {{ rule.match_value }}</span>
      <span class="mg-rule__summary-text">{{ rule.enabled ? '规则启用中' : '规则已停用' }}</span>
    </div>
  </div>
  <div class="mg-rule__primary-actions">
    <el-button size="small" @click="handleToggle(rule)">{{ rule.enabled ? '停用' : '启用' }}</el-button>
    <el-button size="small" @click="openEditDialog(rule)">编辑</el-button>
    <el-button size="small" type="danger" plain @click="handleDelete(rule)">删除</el-button>
  </div>
</div>
```

```vue
<div v-if="status" class="mg-runtime-summary">
  <div class="mg-stats">...</div>
  <div class="mg-runtime-summary__focus">
    <span class="mg-runtime-summary__focus-label">当前观察重点</span>
    <strong>{{ status.last_error ? '优先处理最近异常' : '运行正常，关注最新执行' }}</strong>
  </div>
  <div v-if="timeInfo.length" class="mg-time-info">...</div>
</div>

<div class="mg-exec__info">
  <strong>{{ exec.rule_name }}</strong>
  <p>{{ exec.item_id }}</p>
  <span class="mg-exec__reason">{{ exec.message || '无附加说明' }}</span>
</div>
```

```css
.mg-rule__meta,
.mg-rule__primary-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.mg-runtime-summary__focus {
  display: grid;
  gap: 4px;
  padding: 12px 16px;
  border-radius: 12px;
  border: 1px solid rgba(var(--app-border-rgb), 0.3);
  background: rgba(var(--app-surface-rgb), 0.68);
}

.mg-exec__reason {
  font-size: 12px;
  line-height: 1.5;
  color: rgb(var(--app-text-subtle-rgb));
}
```

- [ ] **Step 4: 重跑两个测试文件，确认原有规则/状态逻辑仍通过**

Run:
```bash
cd web-vue
pnpm exec vitest run src/views/xianyu/components/XianyuManageDeliveryPanel.spec.ts src/views/xianyu/components/XianyuManageRuntimePanel.spec.ts
```

Expected: PASS，规则创建/校验/删除/复制逻辑和运行状态自动刷新逻辑都保持可用，新结构断言通过。

- [ ] **Step 5: 提交发货与运行状态任务**

```bash
git add web-vue/src/views/xianyu/components/XianyuManageDeliveryPanel.vue web-vue/src/views/xianyu/components/XianyuManageRuntimePanel.vue web-vue/src/views/xianyu/components/XianyuManageDeliveryPanel.spec.ts web-vue/src/views/xianyu/components/XianyuManageRuntimePanel.spec.ts
git commit -m "feat: unify xianyu delivery runtime polish"
```

### Task 5: 全量回归与构建验证

**Files:**
- Modify: 如回归中发现结构锚点名称不一致，再回修对应组件 / spec
- Test: `web-vue/src/views/xianyu/index.spec.ts`
- Test: `web-vue/src/views/xianyu/components/XianyuManagePanel.spec.ts`
- Test: `web-vue/src/views/xianyu/components/XianyuManageItemsPanel.spec.ts`
- Test: `web-vue/src/views/xianyu/components/XianyuManageDeliveryPanel.spec.ts`
- Test: `web-vue/src/views/xianyu/components/XianyuManageRuntimePanel.spec.ts`
- Test: `web-vue/src/views/xianyu/components/XianyuMonitorPanel.spec.ts`

- [ ] **Step 1: 如有需要，补一条集成级断言，确保监控页与管理页壳层仍可同时挂载**

```ts
it('keeps xianyu monitor and manage entry shells mountable after detail refine', async () => {
  const wrapper = mount(XianyuIndex, {
    global: {
      stubs: {
        XianyuMonitorPanel: { template: '<div class="monitor-stub" />' },
        XianyuManagePanel: { template: '<div class="manage-stub" />' },
      },
    },
  })

  expect(wrapper.find('.monitor-stub').exists() || wrapper.find('.manage-stub').exists()).toBe(true)
})
```

- [ ] **Step 2: 跑完整目标测试集，确认全部通过**

Run:
```bash
cd web-vue
pnpm exec vitest run src/views/xianyu/index.spec.ts src/views/xianyu/components/XianyuManagePanel.spec.ts src/views/xianyu/components/XianyuManageItemsPanel.spec.ts src/views/xianyu/components/XianyuManageDeliveryPanel.spec.ts src/views/xianyu/components/XianyuManageRuntimePanel.spec.ts src/views/xianyu/components/XianyuMonitorPanel.spec.ts
```

Expected: PASS，6 个测试文件全部通过。

- [ ] **Step 3: 跑构建，确认纯前端结构调整没有破坏生产构建**

Run:
```bash
cd web-vue
pnpm exec vite build
```

Expected: build success；允许保留 Sass deprecation warning，但不能有 build error。

- [ ] **Step 4: 若某个组件在回归或构建中失败，做最小修复后重复上面两条命令**

```bash
cd web-vue
pnpm exec vitest run src/views/xianyu/index.spec.ts src/views/xianyu/components/XianyuManagePanel.spec.ts src/views/xianyu/components/XianyuManageItemsPanel.spec.ts src/views/xianyu/components/XianyuManageDeliveryPanel.spec.ts src/views/xianyu/components/XianyuManageRuntimePanel.spec.ts src/views/xianyu/components/XianyuMonitorPanel.spec.ts
pnpm exec vite build
```

Expected: 两条命令最终都通过，再进入提交。

- [ ] **Step 5: 提交回归结果**

```bash
git add web-vue/src/views/xianyu/index.spec.ts web-vue/src/views/xianyu/components/XianyuMonitorPanel.vue web-vue/src/views/xianyu/components/XianyuMonitorPanel.spec.ts web-vue/src/views/xianyu/components/XianyuManagePanel.vue web-vue/src/views/xianyu/components/XianyuManagePanel.spec.ts web-vue/src/views/xianyu/components/XianyuManageItemsPanel.vue web-vue/src/views/xianyu/components/XianyuManageItemsPanel.spec.ts web-vue/src/views/xianyu/components/XianyuManageDeliveryPanel.vue web-vue/src/views/xianyu/components/XianyuManageDeliveryPanel.spec.ts web-vue/src/views/xianyu/components/XianyuManageRuntimePanel.vue web-vue/src/views/xianyu/components/XianyuManageRuntimePanel.spec.ts
git commit -m "test: verify xianyu detail refine regression"
```

---

## 自检

### Spec coverage

- 监控页两层摘要、标题 / 关键词分层、命中预览条、按钮主次：由 **Task 1** 覆盖。
- 管理中心概览与模块入口卡继续收紧：由 **Task 2** 覆盖。
- 商品管理的封面 / 标题 / 价格 / 状态 / 更新时间与辅助区职责：由 **Task 3** 覆盖。
- 自动发货规则卡的状态判断、长文本弱化、操作区统一：由 **Task 4** 的 delivery 部分覆盖。
- 运行状态的顶层摘要、观察重点、执行记录原因与异常扫读：由 **Task 4** 的 runtime 部分覆盖。
- 组件测试、构建验证和最终回归：由 **Task 5** 覆盖。

### Placeholder scan

已检查本计划，不包含 `TODO`、`TBD`、“稍后实现”、“写测试”这类空泛占位；每个任务都给出了目标文件、命令、预期结果和实现片段。

### Type consistency

- 监控页新增 helper 名称统一使用 `buildTaskPriceRange`、`.mp-detail__identity`、`.mp-detail__action-group`、`.mp-hits__preview`。
- 商品管理新增 helper 名称统一使用 `itemStatusLabel`、`formatItemTime`、`.mg-item__meta`、`.mg-item__price-block`、`.mg-item__primary-action`。
- 自动发货与运行状态新增结构统一使用 `.mg-rule__meta`、`.mg-rule__primary-actions`、`.mg-runtime-summary__focus`、`.mg-exec__reason`。

