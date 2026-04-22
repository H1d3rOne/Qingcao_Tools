# Xianyu Monitor Visual Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 精修监控任务卡片视觉层级，为“展开/收起预览”加入箭头图标，并在验证通过后仅做本地 git commit。

**Architecture:** 在现有 `XianyuMonitorPanel.vue` 基础上做轻量视觉迭代，不改变接口、状态流和折叠逻辑；先用测试锁定按钮箭头结构与现有折叠行为不回归，再最小实现样式与图标；最后运行目标测试、构建并本地提交。

**Tech Stack:** Vue 3 `<script setup>`, Element Plus icons, Vitest, Vue Test Utils, Vite, Git

---

## File Map

- Modify: `web-vue/src/views/xianyu/components/XianyuMonitorPanel.vue`
  - 负责任务卡片视觉精修与预览按钮箭头图标
- Modify: `web-vue/src/views/xianyu/components/XianyuMonitorPanel.spec.ts`
  - 负责按钮结构与既有折叠逻辑回归测试

---

### Task 1: 先补失败测试，锁定箭头按钮结构与回归边界

**Files:**
- Modify: `web-vue/src/views/xianyu/components/XianyuMonitorPanel.spec.ts`
- Test: `web-vue/src/views/xianyu/components/XianyuMonitorPanel.spec.ts`

- [ ] **Step 1: 在现有测试中增加对预览按钮图标结构的断言**

在 `web-vue/src/views/xianyu/components/XianyuMonitorPanel.spec.ts` 的第一个测试里，加上对箭头容器类的断言，要求默认折叠状态和展开状态都存在图标容器。

```ts
it('collapses hit preview by default and toggles preview list', async () => {
  const wrapper = buildWrapper()
  await flushPromises()

  expect(wrapper.text()).toContain('最近命中')
  expect(wrapper.text()).toContain('展开预览')
  expect(wrapper.find('.mp-hit-grid').exists()).toBe(false)
  expect(wrapper.get('.mp-hits__toggle-icon').exists()).toBe(true)

  const toggleButton = wrapper.get('.mp-hits__toggle')
  await toggleButton.trigger('click')
  await flushPromises()

  expect(wrapper.text()).toContain('收起预览')
  expect(wrapper.get('.mp-hits__toggle-icon').exists()).toBe(true)
  expect(wrapper.find('.mp-hit-grid').exists()).toBe(true)
})
```

- [ ] **Step 2: 运行目标测试，确认先失败**

Run:
```bash
cd web-vue
pnpm exec vitest run src/views/xianyu/components/XianyuMonitorPanel.spec.ts
```

Expected:
- FAIL
- 失败点应来自缺少 `.mp-hits__toggle-icon` 结构，而不是折叠逻辑或 mount 错误

- [ ] **Step 3: 如果测试因图标 stub 问题报错，补最小 `el-icon` 兼容断言方式**

如果断言直接查 `el-icon` 不稳定，坚持只查你将在模板里新增的稳定类名，例如：

```ts
expect(wrapper.get('.mp-hits__toggle-icon').exists()).toBe(true)
```

不要依赖运行时真实图标组件名称。

- [ ] **Step 4: 再跑一次测试，确认红灯落点正确**

Run:
```bash
cd web-vue
pnpm exec vitest run src/views/xianyu/components/XianyuMonitorPanel.spec.ts
```

Expected:
- FAIL
- 报错聚焦在按钮缺少新图标结构

- [ ] **Step 5: Commit**

```bash
git add web-vue/src/views/xianyu/components/XianyuMonitorPanel.spec.ts
git commit -m "test: cover xianyu monitor preview toggle icon"
```

---

### Task 2: 实现箭头图标与任务卡片精修

**Files:**
- Modify: `web-vue/src/views/xianyu/components/XianyuMonitorPanel.vue`
- Test: `web-vue/src/views/xianyu/components/XianyuMonitorPanel.spec.ts`

- [ ] **Step 1: 在预览按钮里加入箭头图标结构**

在 `web-vue/src/views/xianyu/components/XianyuMonitorPanel.vue` 的 `<script setup>` import 里补一个轻量箭头图标，例如：

```ts
import { ArrowDown, Bell, Delete, EditPen, Plus, RefreshRight, SwitchButton, VideoPlay } from '@element-plus/icons-vue'
```

然后把当前按钮：

```vue
<button
  type="button"
  class="mp-hits__toggle"
  @click="toggleHitsPreview"
>
  {{ hitsExpanded ? '收起预览' : '展开预览' }}
</button>
```

改成：

```vue
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
```

说明：
- 图标只保留一个，通过旋转区分展开/收起
- 不要改动 `toggleHitsPreview` 的逻辑

- [ ] **Step 2: 精修任务卡片视觉层级**

在同文件样式中，围绕下列类做轻量优化：

```css
.mp-task {
  gap: 8px;
  padding: 13px 14px;
  border-radius: 12px;
}

.mp-task__name {
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.01em;
}

.mp-task__keyword {
  font-size: 13px;
  font-weight: 500;
  opacity: 0.82;
}

.mp-task__footer {
  margin-top: 4px;
  font-size: 11px;
}

.mp-task__status {
  align-self: flex-start;
}
```

目的：
- 标题更稳
- 关键词更清楚但仍弱于标题
- 底部信息继续弱化
- 整体更好扫读，但不改变布局结构

- [ ] **Step 3: 为箭头按钮增加轻量排版与旋转过渡**

在样式中新增：

```css
.mp-hits__toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
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
```

要求：
- 只做轻微旋转，不加复杂动画
- 保持按钮轻量、清晰、不抢“刷新”按钮层级

- [ ] **Step 4: 跑目标测试，确认从红变绿**

Run:
```bash
cd web-vue
pnpm exec vitest run src/views/xianyu/components/XianyuMonitorPanel.spec.ts
```

Expected:
- PASS
- 既有折叠/切换逻辑仍通过
- 新增图标结构断言通过

- [ ] **Step 5: Commit**

```bash
git add web-vue/src/views/xianyu/components/XianyuMonitorPanel.vue web-vue/src/views/xianyu/components/XianyuMonitorPanel.spec.ts
git commit -m "feat: polish xianyu monitor task cards"
```

---

### Task 3: 验证真实效果并完成本地提交

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
- 页签测试与监控面板测试都通过

- [ ] **Step 2: 跑前端构建**

Run:
```bash
cd web-vue
pnpm exec vite build
```

Expected:
- build success
- 无模板错误、无样式错误

- [ ] **Step 3: 真实页面验证**

打开 `http://localhost:3000/xianyu` 的“监控”页，确认：

```text
- 左侧任务卡片层级更稳：标题 > 关键词 > 底部信息
- active 任务更容易识别，但不过分刺眼
- 展开预览按钮带小箭头
- 点击后箭头方向变化
- 折叠/展开逻辑不回归
```

- [ ] **Step 4: 如有细调，回跑最小验证**

Run:
```bash
cd web-vue
pnpm exec vitest run src/views/xianyu/components/XianyuMonitorPanel.spec.ts
pnpm exec vite build
```

Expected:
- 两条命令都 PASS

- [ ] **Step 5: 做本地 git commit**

如果这轮还有未提交改动，执行：

```bash
git add web-vue/src/views/xianyu/components/XianyuMonitorPanel.vue web-vue/src/views/xianyu/components/XianyuMonitorPanel.spec.ts
git commit -m "test: verify xianyu monitor visual polish"
```

说明：
- 只做本地 commit
- 不执行 `git push`
