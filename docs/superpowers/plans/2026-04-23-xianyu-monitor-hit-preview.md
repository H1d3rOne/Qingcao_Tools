# Xianyu Monitor Hit Preview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让监控页右侧“最近命中”默认折叠，通过按钮展开预览命中商品，同时强化左侧任务列表标题的高亮层级。

**Architecture:** 仅在 `XianyuMonitorPanel.vue` 内新增前端折叠状态并调整模板与样式，不改后端接口和监控逻辑；先用组件测试锁定默认折叠、展开/收起、任务切换重置折叠、标题高亮四类行为，再做最小实现；最后跑相关测试和真实页面验证。

**Tech Stack:** Vue 3 `<script setup>`, Element Plus, Vitest, Vue Test Utils, Vite

---

## File Map

- Modify: `web-vue/src/views/xianyu/components/XianyuMonitorPanel.vue`
  - 负责监控页任务列表、最近命中折叠状态、样式与交互
- Create: `web-vue/src/views/xianyu/components/XianyuMonitorPanel.spec.ts`
  - 负责默认折叠、展开/收起、任务切换重置、标题高亮等行为测试

---

### Task 1: 为监控页新增失败测试

**Files:**
- Create: `web-vue/src/views/xianyu/components/XianyuMonitorPanel.spec.ts`
- Test: `web-vue/src/views/xianyu/components/XianyuMonitorPanel.spec.ts`

- [ ] **Step 1: 写失败测试，覆盖默认折叠、展开/收起、切换任务重置、标题高亮**

创建 `web-vue/src/views/xianyu/components/XianyuMonitorPanel.spec.ts`，mock 监控相关接口，至少准备 2 个任务和 1 个命中商品。测试需要覆盖：

```ts
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  listXianyuMonitorTasks: vi.fn(),
  getXianyuMonitorHits: vi.fn(),
  createXianyuMonitorTask: vi.fn(),
  updateXianyuMonitorTask: vi.fn(),
  toggleXianyuMonitorTask: vi.fn(),
  runXianyuMonitorTask: vi.fn(),
  deleteXianyuMonitorTask: vi.fn(),
  messageSuccess: vi.fn(),
  messageError: vi.fn(),
  confirmMock: vi.fn(),
}))

vi.mock('@/api/modules/xianyu', () => ({
  listXianyuMonitorTasks: mocks.listXianyuMonitorTasks,
  getXianyuMonitorHits: mocks.getXianyuMonitorHits,
  createXianyuMonitorTask: mocks.createXianyuMonitorTask,
  updateXianyuMonitorTask: mocks.updateXianyuMonitorTask,
  toggleXianyuMonitorTask: mocks.toggleXianyuMonitorTask,
  runXianyuMonitorTask: mocks.runXianyuMonitorTask,
  deleteXianyuMonitorTask: mocks.deleteXianyuMonitorTask,
}))

vi.mock('element-plus', () => ({
  ElMessage: { success: mocks.messageSuccess, error: mocks.messageError },
  ElMessageBox: { confirm: mocks.confirmMock },
}))

import XianyuMonitorPanel from './XianyuMonitorPanel.vue'

function buildWrapper() {
  return mount(XianyuMonitorPanel, {
    props: {
      currentUser: { display_name: '会飞的猪' },
    },
    global: {
      stubs: {
        'el-button': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
        'el-icon': { template: '<span><slot /></span>' },
        'el-empty': { template: '<div class="empty"><slot />empty</div>' },
        'el-dialog': { template: '<div><slot /><slot name="footer" /></div>' },
        'el-form': { template: '<form><slot /></form>' },
        'el-form-item': { template: '<label><slot /></label>' },
        'el-input': { props: ['modelValue'], template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />' },
        'el-input-number': { props: ['modelValue'], template: '<input type="number" :value="modelValue" @input="$emit(\'update:modelValue\', Number($event.target.value))" />' },
        'el-select': { props: ['modelValue'], template: '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>' },
        'el-option': { props: ['value', 'label'], template: '<option :value="value">{{ label }}</option>' },
      },
    },
  })
}

describe('XianyuMonitorPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.listXianyuMonitorTasks.mockResolvedValue({
      data: [
        {
          id: 'task-1',
          name: '4060 监控',
          keyword: '4060',
          page: 1,
          page_size: 20,
          sort_field: '',
          sort_value: '',
          prop_values: {},
          min_price: null,
          max_price: null,
          interval_seconds: 180,
          enabled: true,
          created_at: 1710000000,
          updated_at: 1710000000,
          last_run_at: 1710000000,
          last_status: 'ok',
          last_error: '',
          seen_item_ids: ['1001'],
          latest_hits: [
            {
              item_id: '1001',
              title: '4060 显卡',
              price: '1999',
              image: 'https://example.com/1.jpg',
              detail_url: 'https://example.com/item/1001',
              discovered_at: 1710000000,
            },
          ],
          max_hits: null,
          published_within_hours: null,
          webhook_url: '',
          contact_seller_enabled: false,
        },
        {
          id: 'task-2',
          name: '3070 监控',
          keyword: '3070',
          page: 1,
          page_size: 20,
          sort_field: '',
          sort_value: '',
          prop_values: {},
          min_price: null,
          max_price: null,
          interval_seconds: 180,
          enabled: false,
          created_at: 1710000000,
          updated_at: 1710000000,
          last_run_at: 1710000000,
          last_status: 'idle',
          last_error: '',
          seen_item_ids: [],
          latest_hits: [],
          max_hits: null,
          published_within_hours: null,
          webhook_url: '',
          contact_seller_enabled: false,
        },
      ],
    })
    mocks.getXianyuMonitorHits.mockResolvedValue({
      data: [
        {
          item_id: '1001',
          title: '4060 显卡',
          price: '1999',
          image: 'https://example.com/1.jpg',
          detail_url: 'https://example.com/item/1001',
          discovered_at: 1710000000,
        },
      ],
    })
  })

  it('collapses hit preview by default and toggles preview list', async () => {
    const wrapper = buildWrapper()
    await flushPromises()

    expect(wrapper.text()).toContain('最近命中')
    expect(wrapper.text()).toContain('展开预览')
    expect(wrapper.find('.mp-hit-grid').exists()).toBe(false)

    const toggleButton = wrapper.findAll('button').find((node) => node.text().includes('展开预览'))
    await toggleButton!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('收起预览')
    expect(wrapper.find('.mp-hit-grid').exists()).toBe(true)
    expect(wrapper.text()).toContain('4060 显卡')

    const collapseButton = wrapper.findAll('button').find((node) => node.text().includes('收起预览'))
    await collapseButton!.trigger('click')
    await flushPromises()

    expect(wrapper.find('.mp-hit-grid').exists()).toBe(false)
  })

  it('resets preview to collapsed after switching tasks and highlights active task title', async () => {
    const wrapper = buildWrapper()
    await flushPromises()

    const expandButton = wrapper.findAll('button').find((node) => node.text().includes('展开预览'))
    await expandButton!.trigger('click')
    await flushPromises()
    expect(wrapper.find('.mp-hit-grid').exists()).toBe(true)

    const tasks = wrapper.findAll('.mp-task')
    expect(tasks[0].classes()).toContain('mp-task--active')
    expect(tasks[0].find('.mp-task__name').classes()).toContain('mp-task__name--active')

    await tasks[1].trigger('click')
    await flushPromises()

    expect(wrapper.find('.mp-hit-grid').exists()).toBe(false)
    expect(wrapper.text()).toContain('展开预览')
    expect(tasks[1].classes()).toContain('mp-task--active')
  })
})
```

- [ ] **Step 2: 运行测试，确认先失败**

Run:
```bash
cd web-vue
pnpm exec vitest run src/views/xianyu/components/XianyuMonitorPanel.spec.ts
```

Expected:
- FAIL
- 失败点来自缺少 `展开预览`、`.mp-hit-grid` 控制逻辑或 `.mp-task__name--active` 样式类，而不是 mock 不完整导致的挂载错误

- [ ] **Step 3: 如果挂载报组件解析错误，补最小 stub 后重跑红灯**

如果第一次执行报 `el-switch` / `el-select` / `el-dialog` 等组件解析错误，就在 spec 里补最小 stub，直到失败点聚焦在“预览折叠与标题高亮未实现”。

```ts
'el-dialog': { props: ['modelValue'], template: '<div v-if="modelValue"><slot /><slot name="footer" /></div>' }
```

- [ ] **Step 4: 再跑一次单测，确认红灯失败点正确**

Run:
```bash
cd web-vue
pnpm exec vitest run src/views/xianyu/components/XianyuMonitorPanel.spec.ts
```

Expected:
- FAIL
- 断言明确落在本次待实现行为上

- [ ] **Step 5: Commit**

```bash
git add web-vue/src/views/xianyu/components/XianyuMonitorPanel.spec.ts
git commit -m "test: cover xianyu monitor hit preview states"
```

---

### Task 2: 实现最近命中折叠预览与任务标题高亮

**Files:**
- Modify: `web-vue/src/views/xianyu/components/XianyuMonitorPanel.vue`
- Test: `web-vue/src/views/xianyu/components/XianyuMonitorPanel.spec.ts`

- [ ] **Step 1: 新增折叠状态，并在切换任务时重置为折叠**

在 `XianyuMonitorPanel.vue` 中新增：

```ts
const hitsExpanded = ref(false)
```

然后修改 `watch(activeTaskId, ...)`：

```ts
watch(activeTaskId, async (taskId) => {
  hitsExpanded.value = false

  if (!taskId) {
    activeHits.value = []
    return
  }
  await loadHits(taskId)
})
```

再新增切换方法：

```ts
function toggleHitsPreview() {
  hitsExpanded.value = !hitsExpanded.value
}
```

- [ ] **Step 2: 调整左侧任务标题结构，单独加标题类**

把左侧任务卡片标题区从：

```vue
<div class="mp-task__name-row">
  <span class="mp-task__dot" />
  <strong>{{ task.name }}</strong>
</div>
```

改成：

```vue
<div class="mp-task__name-row">
  <span class="mp-task__dot" />
  <strong
    class="mp-task__name"
    :class="{ 'mp-task__name--active': activeTaskId === task.id }"
  >
    {{ task.name }}
  </strong>
</div>
```

- [ ] **Step 3: 为右侧最近命中区增加折叠按钮和条件渲染**

把“最近命中”头部改成：

```vue
<div class="mp-hits__head">
  <div class="mp-hits__title-row">
    <strong>最近命中</strong>
    <span class="mp-hits__count">{{ activeHits.length }} 条</span>
  </div>
  <div class="mp-hits__controls">
    <el-button
      text
      type="primary"
      @click="toggleHitsPreview"
    >
      {{ hitsExpanded ? '收起预览' : '展开预览' }}
    </el-button>
    <el-button
      text
      :loading="hitsLoading"
      @click="loadHits(activeTask.id)"
    >
      刷新
    </el-button>
  </div>
</div>
```

把列表区改成：

```vue
<div v-if="hitsExpanded">
  <div
    v-if="activeHits.length"
    class="mp-hit-grid"
  >
    <!-- 原命中商品 article 列表保持不变 -->
  </div>

  <el-empty
    v-else-if="!hitsLoading"
    description="当前任务还没有最近命中"
  />
</div>
```

- [ ] **Step 4: 调整样式，让标题高亮、折叠头更清晰**

在同文件 `<style scoped>` 中补充或修改这些类：

```css
.mp-task__name {
  font-size: 15px;
  font-weight: 700;
  line-height: 1.35;
  color: rgb(var(--app-text-strong-rgb));
  transition: color 0.15s ease;
}

.mp-task__name--active {
  color: rgb(var(--app-accent-rgb));
}

.mp-task__keyword {
  color: rgb(var(--app-text-rgb));
  opacity: 0.78;
}

.mp-task__footer {
  color: rgb(var(--app-text-subtle-rgb));
}

.mp-task--active {
  border-color: rgba(var(--app-accent-rgb), 0.34);
  background: rgba(var(--app-accent-rgb), 0.08);
  box-shadow: inset 3px 0 0 rgba(var(--app-accent-rgb), 0.9);
}

.mp-hits__controls {
  display: flex;
  align-items: center;
  gap: 6px;
}
```

如果原样式已存在同名类，则直接合并，避免重复定义冲突。

- [ ] **Step 5: 跑目标单测，确认从红变绿**

Run:
```bash
cd web-vue
pnpm exec vitest run src/views/xianyu/components/XianyuMonitorPanel.spec.ts
```

Expected:
- PASS
- 默认折叠、展开/收起、切换任务重置、标题高亮全部通过

- [ ] **Step 6: Commit**

```bash
git add web-vue/src/views/xianyu/components/XianyuMonitorPanel.vue web-vue/src/views/xianyu/components/XianyuMonitorPanel.spec.ts
git commit -m "feat: collapse xianyu monitor hit preview"
```

---

### Task 3: 做相关验证与真实页面检查

**Files:**
- Modify: `web-vue/src/views/xianyu/components/XianyuMonitorPanel.vue`（若需要细调）
- Modify: `web-vue/src/views/xianyu/components/XianyuMonitorPanel.spec.ts`（若需要细调）
- Test: `web-vue/src/views/xianyu/index.spec.ts`
- Test: `web-vue/src/views/xianyu/components/XianyuMonitorPanel.spec.ts`

- [ ] **Step 1: 跑监控相关测试**

Run:
```bash
cd web-vue
pnpm exec vitest run src/views/xianyu/index.spec.ts src/views/xianyu/components/XianyuMonitorPanel.spec.ts
```

Expected:
- PASS
- 监控页新交互不影响页签基础测试

- [ ] **Step 2: 跑前端构建**

Run:
```bash
cd web-vue
pnpm exec vite build
```

Expected:
- build success
- 无模板错误、无样式错误

- [ ] **Step 3: 真实页面验证交互**

打开 `http://localhost:3000/xianyu`，进入“监控”页，确认：

```text
- 进入任务详情时，“最近命中”默认只显示摘要头部
- 点击“展开预览”后才显示命中商品卡片
- 点击“收起预览”后列表隐藏
- 切换左侧任务后，命中预览恢复为折叠
- 左侧任务标题比关键词、时间、命中数更醒目
- 当前选中任务标题有额外高亮效果
```

- [ ] **Step 4: 如需细调，跑最小回归验证**

Run:
```bash
cd web-vue
pnpm exec vitest run src/views/xianyu/components/XianyuMonitorPanel.spec.ts
pnpm exec vite build
```

Expected:
- 两条命令都 PASS

- [ ] **Step 5: Commit**

```bash
git add web-vue/src/views/xianyu/components/XianyuMonitorPanel.vue web-vue/src/views/xianyu/components/XianyuMonitorPanel.spec.ts
git commit -m "test: verify xianyu monitor preview toggle"
```
