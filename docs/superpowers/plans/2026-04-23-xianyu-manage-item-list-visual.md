# Xianyu Manage Item List Visual Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让咸鱼管理页商品列表显示封面图，并以暖色价格胶囊强化价格信息，同时保持紧凑排版与现有交互不回归。

**Architecture:** 仅在 `XianyuManageItemsPanel.vue` 内重构列表项模板与样式，不改接口和数据结构；先用组件测试锁定“有图 / 无图 / 有价 / 无价”四类展示，再做最小模板与 CSS 改造；最后跑组件测试、构建和真实页面验证。

**Tech Stack:** Vue 3 `<script setup>`, Element Plus, Vitest, Vue Test Utils, Vite

---

## File Map

- Modify: `web-vue/src/views/xianyu/components/XianyuManageItemsPanel.vue`
  - 负责商品管理列表模板、图片空态、价格展示、响应式排版
- Modify: `web-vue/src/views/xianyu/components/XianyuManageItemsPanel.spec.ts`
  - 负责组件视觉分支与现有删除交互回归测试

---

### Task 1: 锁定视觉分支测试

**Files:**
- Modify: `web-vue/src/views/xianyu/components/XianyuManageItemsPanel.spec.ts`
- Test: `web-vue/src/views/xianyu/components/XianyuManageItemsPanel.spec.ts`

- [ ] **Step 1: 写失败测试，覆盖封面图 / 占位图 / 价格胶囊 / 空价格**

在 `web-vue/src/views/xianyu/components/XianyuManageItemsPanel.spec.ts` 中补充第 2 个用例，并让默认 mock 返回两条商品：一条有图有价，一条无图无价。

```ts
beforeEach(() => {
  vi.clearAllMocks()
  mocks.listXianyuManageItems.mockResolvedValue({
    data: {
      items: [
        {
          item_id: '1001',
          item_title: '商品1',
          item_price: '10',
          item_image: 'https://example.com/item-1.jpg',
          item_status: 'onsale',
          item_detail: '详情1',
          multi_quantity_delivery: false,
          synced_at: 1,
          updated_at: 1,
        },
        {
          item_id: '1002',
          item_title: '商品2',
          item_price: '',
          item_image: '',
          item_status: 'onsale',
          item_detail: '',
          multi_quantity_delivery: true,
          synced_at: 2,
          updated_at: 2,
        },
      ],
      total: 25,
      page: 1,
      page_size: 20,
      has_more: true,
    },
  })
})

it('renders cover, placeholder and price states', async () => {
  const wrapper = buildWrapper()
  await flushPromises()

  const images = wrapper.findAll('img.mg-item__cover-image')
  expect(images).toHaveLength(1)
  expect(images[0].attributes('src')).toBe('https://example.com/item-1.jpg')

  expect(wrapper.findAll('.mg-item__cover-placeholder')).toHaveLength(1)
  expect(wrapper.find('.mg-item__price-pill').text()).toContain('¥10')
  expect(wrapper.find('.mg-item__price-pill--muted').text()).toContain('未设置价格')
})
```

- [ ] **Step 2: 运行测试，确认它先失败**

Run:
```bash
cd web-vue
pnpm exec vitest run src/views/xianyu/components/XianyuManageItemsPanel.spec.ts
```

Expected:
- FAIL
- 报错应来自找不到 `.mg-item__cover-image` / `.mg-item__cover-placeholder` / `.mg-item__price-pill` 等新结构，而不是测试写错或 mount 失败

- [ ] **Step 3: 保持现有删除回归断言可用**

把原有删除测试从“只有一条商品”调整为“在多条商品中仍删除 `1001`”，避免因新增第二条商品让断言误删对象。

```ts
const deleteButton = wrapper.findAll('button').find((node) => {
  return node.text().includes('删除') && wrapper.text().includes('商品1')
})

await deleteButton!.trigger('click')
await flushPromises()

expect(mocks.deleteXianyuManageItem).toHaveBeenCalledWith('1001')
```

- [ ] **Step 4: 再跑一次单测，确认仍是红灯但失败点聚焦在 UI 未实现**

Run:
```bash
cd web-vue
pnpm exec vitest run src/views/xianyu/components/XianyuManageItemsPanel.spec.ts
```

Expected:
- FAIL
- 删除用例结构仍正常，新的视觉断言尚未满足

- [ ] **Step 5: Commit**

```bash
git add web-vue/src/views/xianyu/components/XianyuManageItemsPanel.spec.ts
git commit -m "test: cover xianyu manage item visual states"
```

---

### Task 2: 实现封面图与价格胶囊布局

**Files:**
- Modify: `web-vue/src/views/xianyu/components/XianyuManageItemsPanel.vue`
- Test: `web-vue/src/views/xianyu/components/XianyuManageItemsPanel.spec.ts`

- [ ] **Step 1: 在模板里加入媒体区、内容区、价格胶囊和图片空态**

把当前列表项模板替换为“三段式结构”：左侧封面、中间信息、右侧操作。核心模板应变成：

```vue
<article v-for="item in items" :key="item.item_id" class="mg-item">
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
      <span
        class="mg-item__price-pill"
        :class="{ 'mg-item__price-pill--muted': !item.item_price }"
      >
        {{ item.item_price ? `¥${item.item_price}` : '未设置价格' }}
      </span>
    </div>

    <p class="mg-item__detail">{{ item.item_detail || '暂无商品详情' }}</p>
  </div>

  <div class="mg-item__actions">
    <el-switch
      :model-value="item.multi_quantity_delivery"
      active-text="多数量发货"
      @change="toggleMultiQuantity(item, Boolean($event))"
    />
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
```

- [ ] **Step 2: 用最小 CSS 实现紧凑列表与暖色价格胶囊**

在同文件 `<style scoped>` 中新增并替换相关样式，至少包括下面这些类：

```css
.mg-item {
  display: grid;
  grid-template-columns: 88px minmax(0, 1fr) auto;
  gap: 14px;
  align-items: center;
  padding: 14px 16px;
  border-radius: 12px;
  border: 1px solid rgba(var(--app-border-rgb), 0.3);
  background: rgba(var(--app-surface-rgb), 0.6);
}

.mg-item__media {
  width: 88px;
  height: 88px;
  border-radius: 12px;
  overflow: hidden;
  background: rgba(var(--app-surface-alt-rgb), 0.8);
  border: 1px solid rgba(var(--app-border-rgb), 0.22);
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
  color: rgb(var(--app-text-subtle-rgb));
  background: linear-gradient(135deg, rgba(var(--app-surface-alt-rgb), 0.95), rgba(var(--app-border-rgb), 0.1));
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
  background: rgba(var(--app-surface-alt-rgb), 0.8);
  box-shadow: none;
  font-size: 12px;
  font-weight: 600;
}
```

- [ ] **Step 3: 调整详情和操作区排版，保持桌面端整齐、移动端不拥挤**

继续补齐剩余样式：

```css
.mg-item__body {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.mg-item__detail {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: rgb(var(--app-text-subtle-rgb));
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

@media (max-width: 768px) {
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

  .mg-item__price-pill {
    align-self: flex-start;
  }

  .mg-item__actions {
    grid-column: 1 / -1;
    justify-items: start;
    margin-top: 4px;
  }
}
```

- [ ] **Step 4: 运行单测，确认从红变绿**

Run:
```bash
cd web-vue
pnpm exec vitest run src/views/xianyu/components/XianyuManageItemsPanel.spec.ts
```

Expected:
- PASS
- 新增视觉用例通过
- 删除回归用例仍通过

- [ ] **Step 5: Commit**

```bash
git add web-vue/src/views/xianyu/components/XianyuManageItemsPanel.vue web-vue/src/views/xianyu/components/XianyuManageItemsPanel.spec.ts
git commit -m "feat: refresh xianyu manage item list visuals"
```

---

### Task 3: 做全量前端验证并人工确认真实页面

**Files:**
- Modify: `web-vue/src/views/xianyu/components/XianyuManageItemsPanel.vue`（若验证后需细调）
- Modify: `web-vue/src/views/xianyu/components/XianyuManageItemsPanel.spec.ts`（若验证后需细调）
- Test: `web-vue/src/views/xianyu/index.spec.ts`
- Test: `web-vue/src/views/xianyu/components/XianyuManagePanel.spec.ts`
- Test: `web-vue/src/views/xianyu/components/XianyuManageItemsPanel.spec.ts`
- Test: `web-vue/src/views/xianyu/components/XianyuManageDeliveryPanel.spec.ts`
- Test: `web-vue/src/views/xianyu/components/XianyuManageRuntimePanel.spec.ts`

- [ ] **Step 1: 跑管理页相关测试套件**

Run:
```bash
cd web-vue
pnpm exec vitest run \
  src/views/xianyu/index.spec.ts \
  src/views/xianyu/components/XianyuManagePanel.spec.ts \
  src/views/xianyu/components/XianyuManageItemsPanel.spec.ts \
  src/views/xianyu/components/XianyuManageDeliveryPanel.spec.ts \
  src/views/xianyu/components/XianyuManageRuntimePanel.spec.ts
```

Expected:
- PASS
- 商品管理改造不影响管理页其它面板测试

- [ ] **Step 2: 跑前端构建**

Run:
```bash
cd web-vue
pnpm exec vite build
```

Expected:
- build success
- 无模板编译错误、无样式语法错误

- [ ] **Step 3: 真实页面人工确认商品管理布局**

打开 `http://localhost:3000/xianyu`，进入“管理 > 商品管理”，确认：

```text
- 左侧显示封面图；无图时显示占位块
- 价格是暖色高亮胶囊
- 标题最多两行，不挤压操作按钮
- 商品 ID 仍可读
- 详情最多两行
- 编辑 / 删除 / 多数量发货仍可操作
```

如需最小微调，只允许修改 `XianyuManageItemsPanel.vue` 中的结构和样式，不改接口行为。

- [ ] **Step 4: 重新跑最小验证，确认微调后仍然通过**

Run:
```bash
cd web-vue
pnpm exec vitest run src/views/xianyu/components/XianyuManageItemsPanel.spec.ts
pnpm exec vite build
```

Expected:
- 两条命令都 PASS

- [ ] **Step 5: Commit**

```bash
git add web-vue/src/views/xianyu/components/XianyuManageItemsPanel.vue web-vue/src/views/xianyu/components/XianyuManageItemsPanel.spec.ts
git commit -m "test: verify xianyu manage item layout refresh"
```
