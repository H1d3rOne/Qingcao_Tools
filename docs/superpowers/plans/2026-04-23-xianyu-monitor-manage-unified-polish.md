# Xianyu Monitor Manage Unified Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改接口的前提下，用中等强度前端重排统一咸鱼监控页与管理页的视觉语言、信息层级与操作节奏。

**Architecture:** 以现有 `XianyuMonitorPanel.vue`、`XianyuManagePanel.vue` 及其子面板为基础做局部结构重排和样式统一，不调整 API 调用路径与业务流程。实现顺序先定管理页壳层，再收紧监控页详情层级，然后分别精修商品管理、自动发货、运行状态，最后做集成回归验证。

**Tech Stack:** Vue 3 `<script setup>`, Element Plus, Vitest, Vue Test Utils, Vite, Git

---

## File Map

- Modify: `web-vue/src/views/xianyu/components/XianyuManagePanel.vue`
  - 负责管理页头部概览、模块入口卡、分区运营型壳层
- Modify: `web-vue/src/views/xianyu/components/XianyuManagePanel.spec.ts`
  - 负责管理页壳层与默认模块的结构回归
- Modify: `web-vue/src/views/xianyu/components/XianyuMonitorPanel.vue`
  - 负责监控页双栏层级、当前任务摘要头部、最近命中区统一语言
- Modify: `web-vue/src/views/xianyu/components/XianyuMonitorPanel.spec.ts`
  - 负责监控页折叠逻辑不回归与新增摘要结构断言
- Modify: `web-vue/src/views/xianyu/components/XianyuManageItemsPanel.vue`
  - 负责商品管理列表、辅助侧区、工具栏和统计区精修
- Modify: `web-vue/src/views/xianyu/components/XianyuManageItemsPanel.spec.ts`
  - 负责商品管理新结构的稳定断言
- Modify: `web-vue/src/views/xianyu/components/XianyuManageDeliveryPanel.vue`
  - 负责自动发货区的规则卡分层、头部摘要、按钮主次统一
- Modify: `web-vue/src/views/xianyu/components/XianyuManageDeliveryPanel.spec.ts`
  - 负责自动发货区结构和交互回归
- Modify: `web-vue/src/views/xianyu/components/XianyuManageRuntimePanel.vue`
  - 负责运行状态摘要、最近记录区层级统一
- Modify: `web-vue/src/views/xianyu/components/XianyuManageRuntimePanel.spec.ts`
  - 负责运行状态区摘要与自动刷新回归
- Test: `web-vue/src/views/xianyu/index.spec.ts`
  - 负责底部 tab 与管理页集成入口回归

> **Scope check:** 监控页与管理页虽然包含多个子面板，但都服务于同一轮“统一视觉语言 + 信息层级 + 操作效率”的前端改造，而且共享同一入口、同一页面语气和同一验收目标，因此保持为一个实现计划是合理的，不再拆成多份 plan。

---

### Task 1: 先统一管理页壳层与概览结构

**Files:**
- Modify: `web-vue/src/views/xianyu/components/XianyuManagePanel.vue`
- Modify: `web-vue/src/views/xianyu/components/XianyuManagePanel.spec.ts`
- Test: `web-vue/src/views/xianyu/components/XianyuManagePanel.spec.ts`

- [ ] **Step 1: 先给管理页壳层补失败测试，锁定“分区运营型”结构**

在 `web-vue/src/views/xianyu/components/XianyuManagePanel.spec.ts` 中，把当前仅断言“商品管理”文案的测试扩成对头部概览、模块入口卡和默认激活态的断言：

```ts
import { shallowMount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import XianyuManagePanel from './XianyuManagePanel.vue'

describe('XianyuManagePanel', () => {
  it('renders unified overview shell and keeps 商品管理 active by default', () => {
    const wrapper = shallowMount(XianyuManagePanel, {
      props: {
        currentUser: { display_name: '会飞的猪' },
      },
      global: {
        stubs: {
          XianyuManageItemsPanel: true,
          XianyuManageDeliveryPanel: true,
          XianyuManageRuntimePanel: true,
          'el-button': true,
          'el-icon': true,
        },
      },
    })

    expect(wrapper.find('.mg-overview').exists()).toBe(true)
    expect(wrapper.findAll('.mg-overview__stat')).toHaveLength(4)
    expect(wrapper.findAll('.mg-tab')).toHaveLength(3)
    expect(wrapper.find('.mg-tab--active .mg-tab__text').text()).toContain('商品管理')
    expect(wrapper.text()).toContain('会飞的猪')
  })
})
```

- [ ] **Step 2: 跑测试，确认先红灯**

Run:
```bash
cd web-vue
pnpm exec vitest run src/views/xianyu/components/XianyuManagePanel.spec.ts
```

Expected:
- FAIL
- 失败点聚焦在 `.mg-overview` 或概览统计结构不存在

- [ ] **Step 3: 在管理页组件里加“头部 + 概览 + 模块卡”壳层，不动子面板接口**

在 `web-vue/src/views/xianyu/components/XianyuManagePanel.vue` 中：

1. 新增概览统计计算属性，使用现有 tab 信息生成四个摘要块：

```ts
const overviewStats = computed(() => [
  { label: '当前账号', value: currentUser?.display_name || '沿用登录态', hint: '管理中心' },
  { label: '模块数量', value: '3', hint: '商品 / 发货 / 状态' },
  { label: '默认入口', value: '商品管理', hint: '同步与编辑' },
  { label: '当前焦点', value: tabs.value.find((tab) => tab.key === activeTab.value)?.label || '商品管理', hint: '统一操作节奏' },
])
```

2. 在 header 后插入概览块：

```vue
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
```

3. 保留现有三个 `mg-tab`，但给 tab 区增加更像模块卡的标题容器：

```vue
<div class="mg-tabs-shell">
  <div class="mg-tabs-shell__head">
    <div>
      <strong>管理模块</strong>
      <p>统一管理商品缓存、发货规则与运行状态</p>
    </div>
  </div>
  <nav class="mg-tabs">
    <!-- 保留现有 v-for tab 按钮 -->
  </nav>
</div>
```
```

4. 增加对应样式类：`.mg-overview`、`.mg-overview__stat`、`.mg-tabs-shell`、`.mg-tabs-shell__head`，并延续现有圆角、边框、surface 风格。

- [ ] **Step 4: 回跑管理页壳层测试，确认转绿**

Run:
```bash
cd web-vue
pnpm exec vitest run src/views/xianyu/components/XianyuManagePanel.spec.ts
```

Expected:
- PASS
- 默认激活仍为“商品管理”
- 概览结构断言通过

- [ ] **Step 5: Commit**

```bash
git add web-vue/src/views/xianyu/components/XianyuManagePanel.vue web-vue/src/views/xianyu/components/XianyuManagePanel.spec.ts
git commit -m "feat: unify xianyu manage center shell"
```

---

### Task 2: 精修监控页当前任务摘要头部与命中区层级

**Files:**
- Modify: `web-vue/src/views/xianyu/components/XianyuMonitorPanel.vue`
- Modify: `web-vue/src/views/xianyu/components/XianyuMonitorPanel.spec.ts`
- Test: `web-vue/src/views/xianyu/components/XianyuMonitorPanel.spec.ts`

- [ ] **Step 1: 先补监控页新结构测试，锁定摘要头部与命中说明区**

在 `web-vue/src/views/xianyu/components/XianyuMonitorPanel.spec.ts` 追加一个用例，要求当前任务详情区存在统一摘要头部和命中说明：

```ts
it('renders unified task summary head and keeps hit preview helper hierarchy', async () => {
  const wrapper = buildWrapper()
  await flushPromises()

  expect(wrapper.find('.mp-detail__summary-head').exists()).toBe(true)
  expect(wrapper.findAll('.mp-detail__meta-pill').length).toBeGreaterThan(1)
  expect(wrapper.find('.mp-hits__helper').text()).toContain('默认折叠')
  expect(wrapper.find('.mp-hits__toggle-icon').exists()).toBe(true)
})
```

- [ ] **Step 2: 跑监控页组件测试，确认先红灯**

Run:
```bash
cd web-vue
pnpm exec vitest run src/views/xianyu/components/XianyuMonitorPanel.spec.ts
```

Expected:
- FAIL
- 缺少 `.mp-detail__summary-head`、`.mp-detail__meta-pill` 或 `.mp-hits__helper`

- [ ] **Step 3: 在监控页实现统一摘要头部与命中说明，不改折叠逻辑**

在 `web-vue/src/views/xianyu/components/XianyuMonitorPanel.vue` 中：

1. 把当前详情头部信息包进新的摘要容器：

```vue
<div class="mp-detail__summary-head">
  <div class="mp-detail__summary-main">
    <div class="mp-detail__title-row">
      <span class="mp-detail__dot" :class="{ 'mp-detail__dot--on': activeTask.enabled && activeTask.last_status !== 'error', 'mp-detail__dot--err': activeTask.last_status === 'error' }" />
      <h3>{{ activeTask.name }}</h3>
      <span class="mp-detail__keyword">{{ activeTask.keyword }}</span>
    </div>
    <p class="mp-detail__summary">{{ buildTaskSummary(activeTask) }}</p>
    <div class="mp-detail__meta-pills">
      <span class="mp-detail__meta-pill">最近执行 {{ formatTimestamp(activeTask.last_run_at) }}</span>
      <span class="mp-detail__meta-pill">更新时间 {{ formatTimestamp(activeTask.updated_at) }}</span>
      <span class="mp-detail__meta-pill">已见商品 {{ activeTask.seen_item_ids.length }}</span>
    </div>
  </div>
  <div class="mp-detail__actions">
    <!-- 保留现有按钮组 -->
  </div>
</div>
```

2. 命中区标题旁补一条 helper 说明：

```vue
<div class="mp-hits__title-block">
  <div class="mp-hits__title-row">
    <strong>最近命中</strong>
    <span class="mp-hits__count">{{ activeHits.length }} 条</span>
  </div>
  <p class="mp-hits__helper">默认折叠，按需展开预览当前任务的命中商品</p>
</div>
```

3. 对应调整样式：`.mp-detail__summary-head`、`.mp-detail__summary-main`、`.mp-detail__meta-pills`、`.mp-detail__meta-pill`、`.mp-hits__title-block`、`.mp-hits__helper`。

4. 保持已有 `hitsExpanded`、箭头旋转、切换任务重置逻辑原样。

- [ ] **Step 4: 回跑监控页测试，确认新结构与旧交互一起通过**

Run:
```bash
cd web-vue
pnpm exec vitest run src/views/xianyu/components/XianyuMonitorPanel.spec.ts
```

Expected:
- PASS
- 既有折叠/展开/切换任务逻辑仍通过
- 新增摘要头部结构断言通过

- [ ] **Step 5: Commit**

```bash
git add web-vue/src/views/xianyu/components/XianyuMonitorPanel.vue web-vue/src/views/xianyu/components/XianyuMonitorPanel.spec.ts
git commit -m "feat: refine xianyu monitor detail hierarchy"
```

---

### Task 3: 精修商品管理列表与辅助信息区

**Files:**
- Modify: `web-vue/src/views/xianyu/components/XianyuManageItemsPanel.vue`
- Modify: `web-vue/src/views/xianyu/components/XianyuManageItemsPanel.spec.ts`
- Test: `web-vue/src/views/xianyu/components/XianyuManageItemsPanel.spec.ts`

- [ ] **Step 1: 给商品管理区补失败测试，锁定辅助区与摘要截断结构**

在 `web-vue/src/views/xianyu/components/XianyuManageItemsPanel.spec.ts` 追加：

```ts
it('renders unified toolbar and helper aside for item operations', async () => {
  const wrapper = buildWrapper()
  await flushPromises()

  expect(wrapper.find('.mg-section__toolbar').exists()).toBe(true)
  expect(wrapper.find('.mg-items-shell').exists()).toBe(true)
  expect(wrapper.find('.mg-items-aside').exists()).toBe(true)
  expect(wrapper.find('.mg-item__detail').classes()).toContain('mg-item__detail--clamp')
})
```

- [ ] **Step 2: 跑商品管理测试，确认先红灯**

Run:
```bash
cd web-vue
pnpm exec vitest run src/views/xianyu/components/XianyuManageItemsPanel.spec.ts
```

Expected:
- FAIL
- 新增壳层类名不存在

- [ ] **Step 3: 在商品管理区加入工具栏壳层、列表主区和辅助侧区**

在 `web-vue/src/views/xianyu/components/XianyuManageItemsPanel.vue` 中：

1. 把统计区和同步按钮包成统一工具栏：

```vue
<div class="mg-section__toolbar">
  <div class="mg-stats">
    <!-- 保留现有 stats 渲染 -->
  </div>
  <div class="mg-section__actions">
    <!-- 保留同步当前页 / 同步全部 -->
  </div>
</div>
```

2. 把商品区改成主列表 + 辅助侧区：

```vue
<div v-else class="mg-items-shell">
  <div class="mg-item-list">
    <!-- 保留现有 v-for 商品卡片 -->
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
```

3. 给详情摘要增加固定类，保证两行截断：

```vue
<p class="mg-item__detail mg-item__detail--clamp">{{ item.item_detail || '暂无商品详情' }}</p>
```

4. 增加样式：`.mg-section__toolbar`、`.mg-items-shell`、`.mg-items-aside`、`.mg-items-aside__card`、`.mg-item__detail--clamp`，其中截断样式使用：

```css
.mg-item__detail--clamp {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
```

- [ ] **Step 4: 回跑商品管理测试，确认新结构和既有交互都通过**

Run:
```bash
cd web-vue
pnpm exec vitest run src/views/xianyu/components/XianyuManageItemsPanel.spec.ts
```

Expected:
- PASS
- 分页、删除、封面与价格断言仍通过
- 新增辅助区结构断言通过

- [ ] **Step 5: Commit**

```bash
git add web-vue/src/views/xianyu/components/XianyuManageItemsPanel.vue web-vue/src/views/xianyu/components/XianyuManageItemsPanel.spec.ts
git commit -m "feat: polish xianyu manage item workspace"
```

---

### Task 4: 统一自动发货区的规则卡层级与按钮主次

**Files:**
- Modify: `web-vue/src/views/xianyu/components/XianyuManageDeliveryPanel.vue`
- Modify: `web-vue/src/views/xianyu/components/XianyuManageDeliveryPanel.spec.ts`
- Test: `web-vue/src/views/xianyu/components/XianyuManageDeliveryPanel.spec.ts`

- [ ] **Step 1: 先补自动发货区结构测试，锁定规则卡摘要与 flag 区**

在 `web-vue/src/views/xianyu/components/XianyuManageDeliveryPanel.spec.ts` 增加：

```ts
it('renders rule summary shell and action hierarchy for delivery rules', async () => {
  mocks.listXianyuDeliveryRules.mockResolvedValue({
    data: [
      {
        id: 'rule-1',
        name: '现货卡密',
        enabled: true,
        match_mode: 'item_id',
        match_value: '1001',
        delivery_text: '复制这段卡密',
        send_chat_text: true,
        send_dummy_ship: true,
        created_at: 1,
        updated_at: 1,
      },
    ],
  })

  const wrapper = buildWrapper()
  await flushPromises()

  expect(wrapper.find('.mg-rule__summary').exists()).toBe(true)
  expect(wrapper.find('.mg-rule__body-grid').exists()).toBe(true)
  expect(wrapper.findAll('.mg-rule__flag')).toHaveLength(2)
})
```

- [ ] **Step 2: 跑自动发货区测试，确认先红灯**

Run:
```bash
cd web-vue
pnpm exec vitest run src/views/xianyu/components/XianyuManageDeliveryPanel.spec.ts
```

Expected:
- FAIL
- `.mg-rule__summary` 或 `.mg-rule__body-grid` 不存在

- [ ] **Step 3: 重排自动发货区规则卡，不改接口与表单提交流程**

在 `web-vue/src/views/xianyu/components/XianyuManageDeliveryPanel.vue` 中：

1. 在规则卡头部增加摘要区：

```vue
<div class="mg-rule__summary">
  <span class="mg-rule__mode">{{ matchModeLabel(rule.match_mode) }}</span>
  <span class="mg-rule__summary-text">匹配 {{ rule.match_value }}</span>
</div>
```

2. 把正文改成更清楚的两段栅格：

```vue
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
```

3. 保留 `.mg-rule__flags`，但让 flag 统一跟在正文之后。

4. 调整样式：`.mg-rule__summary`、`.mg-rule__summary-text`、`.mg-rule__body-grid`，并让“启用/停用”作为最靠前的操作按钮，编辑次之，删除最弱。

> 注意：如果当前文件里存在 `listXianyuManageDeliveryRules()` 这类与 import 不一致的调用，修正为已导入的 `listXianyuDeliveryRules()`，不扩散到接口层。

- [ ] **Step 4: 回跑自动发货区测试，确认交互与新结构都通过**

Run:
```bash
cd web-vue
pnpm exec vitest run src/views/xianyu/components/XianyuManageDeliveryPanel.spec.ts
```

Expected:
- PASS
- 新建/校验/复制/删除逻辑仍通过
- 新结构断言通过

- [ ] **Step 5: Commit**

```bash
git add web-vue/src/views/xianyu/components/XianyuManageDeliveryPanel.vue web-vue/src/views/xianyu/components/XianyuManageDeliveryPanel.spec.ts
git commit -m "feat: unify xianyu delivery rule cards"
```

---

### Task 5: 统一运行状态区的摘要与最近记录层级

**Files:**
- Modify: `web-vue/src/views/xianyu/components/XianyuManageRuntimePanel.vue`
- Modify: `web-vue/src/views/xianyu/components/XianyuManageRuntimePanel.spec.ts`
- Test: `web-vue/src/views/xianyu/components/XianyuManageRuntimePanel.spec.ts`

- [ ] **Step 1: 先补运行状态区测试，锁定摘要头部和最近记录辅助说明**

在 `web-vue/src/views/xianyu/components/XianyuManageRuntimePanel.spec.ts` 中新增断言：

```ts
it('renders runtime summary shell and keeps recent execution list readable', async () => {
  const wrapper = mount(XianyuManageRuntimePanel, {
    global: {
      stubs: {
        'el-button': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
        'el-empty': { template: '<div>empty</div>' },
      },
    },
  })

  await flushPromises()

  expect(wrapper.find('.mg-runtime-summary').exists()).toBe(true)
  expect(wrapper.findAll('.mg-time-info__item')).toHaveLength(3)
  expect(wrapper.find('.mg-exec__helper').text()).toContain('最近 20 条')
})
```

- [ ] **Step 2: 跑运行状态区测试，确认先红灯**

Run:
```bash
cd web-vue
pnpm exec vitest run src/views/xianyu/components/XianyuManageRuntimePanel.spec.ts
```

Expected:
- FAIL
- `.mg-runtime-summary` 或 `.mg-exec__helper` 不存在

- [ ] **Step 3: 在运行状态区加入摘要区与记录说明，保留自动刷新逻辑**

在 `web-vue/src/views/xianyu/components/XianyuManageRuntimePanel.vue` 中：

1. 用统一摘要容器包住统计 + 时间信息：

```vue
<div class="mg-runtime-summary">
  <div class="mg-stats">
    <!-- 保留现有 stats -->
  </div>
  <div v-if="timeInfo.length" class="mg-time-info">
    <!-- 保留现有 timeInfo 渲染 -->
  </div>
</div>
```

2. 在最近执行记录头部加 helper：

```vue
<div class="mg-exec__head">
  <div>
    <strong>最近执行记录</strong>
    <p class="mg-exec__helper">最近 20 条执行结果，自动刷新用于快速判断是否需要回到规则区处理</p>
  </div>
  <span class="mg-exec__count">{{ executions.length }} 条</span>
</div>
```

3. 样式上让时间信息与统计卡形成上下分组，而不是散落展示。

4. 保持 `setInterval` 自动刷新、错误展示和状态类逻辑不变。

- [ ] **Step 4: 回跑运行状态区测试，确认结构与轮询都通过**

Run:
```bash
cd web-vue
pnpm exec vitest run src/views/xianyu/components/XianyuManageRuntimePanel.spec.ts
```

Expected:
- PASS
- 自动刷新次数仍符合预期
- 新摘要壳层与 helper 断言通过

- [ ] **Step 5: Commit**

```bash
git add web-vue/src/views/xianyu/components/XianyuManageRuntimePanel.vue web-vue/src/views/xianyu/components/XianyuManageRuntimePanel.spec.ts
git commit -m "feat: polish xianyu runtime summary"
```

---

### Task 6: 做管理页与监控页集成回归验证

**Files:**
- Test: `web-vue/src/views/xianyu/index.spec.ts`
- Test: `web-vue/src/views/xianyu/components/XianyuManagePanel.spec.ts`
- Test: `web-vue/src/views/xianyu/components/XianyuManageItemsPanel.spec.ts`
- Test: `web-vue/src/views/xianyu/components/XianyuManageDeliveryPanel.spec.ts`
- Test: `web-vue/src/views/xianyu/components/XianyuManageRuntimePanel.spec.ts`
- Test: `web-vue/src/views/xianyu/components/XianyuMonitorPanel.spec.ts`

- [ ] **Step 1: 如有必要，补一条 index 层回归，确认底部“管理”入口仍能加载管理页组件**

如果 `web-vue/src/views/xianyu/index.spec.ts` 目前只断言“管理”文案存在，则将用例扩成：

```ts
it('shows 管理 tab and keeps manage panel entry wired in xianyu page', () => {
  const wrapper = shallowMount(XianyuPage, {
    global: {
      stubs: {
        XianyuChatPanel: true,
        XianyuMonitorPanel: true,
        XianyuManagePanel: true,
        'el-button': true,
        'el-input': true,
        'el-select': true,
        'el-option': true,
        'el-empty': true,
        'el-pagination': true,
        'el-dialog': true,
        'el-icon': true,
      },
    },
  })

  expect(wrapper.text()).toContain('管理')
  expect(wrapper.findComponent({ name: 'XianyuManagePanel' }).exists()).toBe(true)
})
```

- [ ] **Step 2: 跑咸鱼工具相关测试组合**

Run:
```bash
cd web-vue
pnpm exec vitest run \
  src/views/xianyu/index.spec.ts \
  src/views/xianyu/components/XianyuManagePanel.spec.ts \
  src/views/xianyu/components/XianyuManageItemsPanel.spec.ts \
  src/views/xianyu/components/XianyuManageDeliveryPanel.spec.ts \
  src/views/xianyu/components/XianyuManageRuntimePanel.spec.ts \
  src/views/xianyu/components/XianyuMonitorPanel.spec.ts
```

Expected:
- PASS
- 所有与本轮统一优化相关的组件测试通过

- [ ] **Step 3: 跑前端构建，确认模板和样式无回归**

Run:
```bash
cd web-vue
pnpm exec vite build
```

Expected:
- build success
- 允许存在 Sass deprecation warning，但不允许构建失败

- [ ] **Step 4: 手动验证监控页和管理页的统一视觉**

打开 `http://localhost:3000/xianyu`，至少确认：

```text
- 监控页左侧任务列表层级更稳
- 监控页当前任务摘要区更聚焦
- 最近命中区默认折叠与箭头切换不回归
- 管理页出现概览统计与模块卡壳层
- 商品管理有主区 + 辅助区，价格与封面节奏更统一
- 自动发货与运行状态区的标题、摘要、状态表达更一致
```

如果登录态已失效，可沿用前一轮做法：在浏览器中对 `/api/v1/xianyu/auth/status`、`/api/v1/xianyu/user/profile` 及对应管理接口做本地 mock，只用于真实前端页面的视觉检查，不改代码。

- [ ] **Step 5: Commit 最终集成验证**

```bash
git add web-vue/src/views/xianyu/index.spec.ts \
  web-vue/src/views/xianyu/components/XianyuManagePanel.spec.ts \
  web-vue/src/views/xianyu/components/XianyuManageItemsPanel.spec.ts \
  web-vue/src/views/xianyu/components/XianyuManageDeliveryPanel.spec.ts \
  web-vue/src/views/xianyu/components/XianyuManageRuntimePanel.spec.ts \
  web-vue/src/views/xianyu/components/XianyuMonitorPanel.spec.ts

git commit -m "test: verify xianyu unified polish regression"
```

---

## Self-Review

### Spec coverage

- 监控页双栏与当前任务摘要：Task 2
- 管理页分区运营型壳层：Task 1
- 商品管理封面/价格/辅助区统一：Task 3
- 自动发货规则卡与按钮主次：Task 4
- 运行状态摘要与最近记录：Task 5
- 统一回归与构建验证：Task 6

无明显 spec 漏项。

### Placeholder scan

- 未使用 TBD / TODO / “自行补充” 类占位
- 每个代码步骤都给了实际类名、结构或命令
- 每个任务都包含明确验证与 commit

### Type consistency

- 管理页：`overviewStats`、`mg-overview*` 命名统一
- 监控页：`mp-detail__summary-head`、`mp-detail__meta-pill`、`mp-hits__helper` 命名统一
- 商品管理：`mg-items-shell`、`mg-items-aside`、`mg-item__detail--clamp` 命名统一
- 自动发货：`mg-rule__summary`、`mg-rule__body-grid` 命名统一
- 运行状态：`mg-runtime-summary`、`mg-exec__helper` 命名统一

