# 闲鱼详情弹窗主题一致性设计

## 目标
让 `web-vue/src/views/xianyu/index.vue` 中的闲鱼商品详情弹窗在所有现有主题下与页面其他区域保持同一色系语言，并保证正文、标签、统计、卖家信息在浅色/深色主题下都清晰可见。

## 现状
当前详情弹窗已经部分使用全局主题变量，但仍混用了较强的局部渐变、高光、偏固定的亮色边框与阴影表现，导致：

- 详情弹窗视觉权重高于同页其他卡片，显得像另一套皮肤
- 浅色主题下局部对比度不稳定
- 深色主题下卖家卡、统计卡、标签芯片的层级与其他页面不一致

## 设计原则
1. 详情弹窗不是独立视觉系统，而是搜索页主题卡片体系的延展。
2. 颜色只来源于现有主题 token，不新增独立 detail 主题变量。
3. 主色仅用于价格、激活态、轻量强调，不用于大面积底色。
4. 内容可读性优先于“高级感”装饰。

## 方案
采用“收敛到现有主题 token”的方案：

- 详情弹窗容器、卖家卡、描述卡、属性卡、统计卡全部统一依赖：
  - `--app-surface-rgb`
  - `--app-surface-alt-rgb`
  - `--app-border-rgb`
  - `--app-text-strong-rgb`
  - `--app-text-rgb`
  - `--app-text-muted-rgb`
  - `--app-text-subtle-rgb`
- 弱化详情区当前大面积渐变、高光和偏白描边
- 将标签、属性项、统计块收敛到和搜索卡片一致的层级与边框语言
- 保留价格的主色强调，以及缩略图当前选中态的主色描边

## 作用范围
只调整闲鱼详情弹窗相关样式，不改全局主题 token，不影响搜索页其他模块。

涉及区域：
- `:deep(.xianyu-detail-dialog .el-dialog)`
- `.detail-dialog__header`
- `.detail-overview`
- `.detail-meta-list span`
- `.detail-tags span`
- `.detail-desc-block`
- `.detail-attr`
- `.detail-stat`
- `.detail-seller`
- `.detail-seller__chips span`
- `.detail-seller__avatar`
- `.detail-gallery__thumb`

## 具体调整
### 1. 弹窗容器
- 保持当前圆角与布局
- 背景改为标准 surface，减少额外透明和漂浮感
- header/body 使用与页面卡片一致的文字层级

### 2. 商品概览卡
- 保留价格高亮
- 减弱背景中的 radial gradient 和顶部高光
- title、meta、tag 的文字对比度统一用 app text token
- meta/tag 芯片统一改为低饱和 surface-alt 背景 + 标准边框

### 3. 卖家卡
- 去掉偏白头像描边，改为主题边框色
- 卖家 badge 保留主色，但缩小其对整体色彩的影响
- 卖家状态 chips 改为与标签一致的轻量主题样式
- stats 卡片改为和页面其他信息卡相同的层级

### 4. 描述 / 属性 / 统计
- 描述正文使用 `app-text-rgb`，不是过亮白字
- 属性项 label/value 保持稳定对比
- 统计卡背景和搜索页卡片风格统一，不额外制造高光

### 5. 缩略图和空态
- 缩略图未选中状态使用标准边框与 soft surface
- 选中态保留主色描边
- 空态文案颜色使用 `app-text-subtle-rgb`

## 验收标准
1. 在 `graphite / ivory / ocean / forest / amethyst` 下，详情弹窗整体色系与当前主题一致。
2. 标题、正文、属性值、统计数字、卖家信息均可直接辨识，无“发灰看不清”或“过亮刺眼”。
3. 弹窗视觉上与同页搜索卡片、用户卡、导航保持同一设计语言。
4. 不引入新的全局主题 token。

## 风险控制
- 只改详情弹窗相关 CSS，避免影响其他区域
- 尽量复用现有 token 和现有 `theme-surface-*` 设计语言
- 如需微调，仅做局部透明度/阴影收敛，不大改结构
