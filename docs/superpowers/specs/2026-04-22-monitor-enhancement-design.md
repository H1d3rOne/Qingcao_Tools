# 闲鱼监控功能增强设计

## 概述

在现有闲鱼监控模块基础上，增加搜索页"添加监控"快捷入口、监控任务条件筛选（发布时间、命中数限制）、命中触发 Webhook 通知，以及通知配置持久化。

## 需求

1. 搜索页添加"添加监控"按钮，点击后自动跳转监控 Tab 并创建暂停状态的任务（携带当前搜索条件）
2. 监控任务新增筛选条件：商品发布时间范围、满足条件的最大命中数
3. 命中时触发 Webhook 通知（复用现有企业微信/钉钉/飞书通知模块）
4. 通知配置持久化到 JSON 文件（替代现有内存存储）

## 设计

### 1. 搜索页"添加监控"按钮

**前端改动**：`web-vue/src/views/xianyu/index.vue`

- 搜索结果区域顶部（搜索栏旁边或结果计数旁）添加"添加监控"按钮
- 点击逻辑：
  1. 调用 `createXianyuMonitorTask()` 创建任务，参数从当前搜索条件映射：
     - `keyword` ← 搜索关键词
     - `sort_field` / `sort_value` ← 当前排序
     - `prop_values` ← 当前属性筛选
     - `min_price` / `max_price` ← 当前价格区间
     - `enabled` = false（默认暂停）
     - `name` = `监控: {keyword}`
  2. 切换到监控 Tab
  3. 监控面板自动选中新创建的任务进入编辑状态

**按钮样式**：与现有 UI 风格一致，使用主题色按钮，图标用 `Monitor` 或 `Bell`。

### 2. 监控任务新增字段

**后端 Schema 改动**：`backend/app/modules/xianyu/schemas.py`

`XianyuMonitorTask` 新增：
- `max_hits: int = 0` — 满足过滤条件的最大命中数，0 表示不限。达到后自动暂停任务。
- `published_within_hours: int = 0` — 只监控发布时间在 N 小时内的商品，0 表示不限。

`XianyuMonitorTaskCreate` / `XianyuMonitorTaskUpdate` 同步新增这两个可选字段。

**后端执行逻辑改动**：`backend/app/modules/xianyu/service.py` 的 `run_monitor_task()`

在现有价格过滤之后，增加：
1. 发布时间过滤：如果 `published_within_hours > 0`，检查商品的发布时间字段，超过 N 小时的跳过
2. 命中数检查：如果 `max_hits > 0` 且当前任务累计命中数 >= `max_hits`，自动暂停任务

**商品发布时间字段**：闲鱼搜索结果 `XianyuSearchItem` 需要确认是否包含发布时间。如果不包含，需要在 `_map_result()` 中从接口返回数据中提取。如果接口不返回发布时间，则使用 `published_within_hours` 过滤时通过商品详情接口获取（会增加 API 调用），或者暂时不支持此字段并在 UI 上标注。

### 3. Webhook 通知集成

**后端改动**：`backend/app/modules/xianyu/service.py` 的 `run_monitor_task()`

当有新命中时，调用通知模块发送 Webhook。通知内容格式：

```
【闲鱼监控命中】
任务：{task.name}
关键词：{task.keyword}
命中商品：{hit.title}
价格：¥{hit.price}
链接：{hit.detail_url}
发现时间：{hit.discovered_at}
```

**通知模块改动**：`backend/app/api/v1/notify.py`

- 将 `NotifyConfig` 持久化到 `config/notify_config.json`
- 提供一个 `send_monitor_notification(message: str)` 函数供监控模块调用
- 该函数检查所有已启用的 Webhook 配置，向每个启用的渠道发送通知

### 4. 通知配置持久化

**存储**：`config/notify_config.json`

```json
{
  "wecom": { "enabled": false, "webhook_url": "" },
  "dingtalk": { "enabled": false, "webhook_url": "" },
  "feishu": { "enabled": false, "webhook_url": "" }
}
```

**改动**：`backend/app/api/v1/notify.py`

- 新增 `_load_config()` / `_save_config()` 方法，读写 JSON 文件
- 所有配置读写操作改为通过文件持久化
- 启动时从文件加载，更新时同步写入文件

### 5. 前端监控面板增强

**改动**：`web-vue/src/views/xianyu/components/XianyuMonitorPanel.vue`

- 任务编辑表单新增：
  - "发布时间范围"输入框（N 小时内，0=不限）
  - "最大命中数"输入框（0=不限）
- 命中列表增加通知状态标识
- 接收从搜索页创建任务后自动进入编辑模式的逻辑

### 6. 监控启动自动化

**改动**：`backend/app/main.py`

在 `lifespan` 启动时调用 `get_xianyu_service().ensure_monitor_runner()`，确保监控循环随应用自动启动。

## 数据流

```
搜索页点击"添加监控"
  → createXianyuMonitorTask({keyword, sort, filters, price, enabled:false})
  → 切换到监控 Tab
  → 监控面板加载新任务，自动进入编辑模式
  → 用户编辑条件（发布时间、最大命中数、间隔等）
  → 用户手动启用任务
  → 后台监控循环按间隔执行
  → 搜索 → 过滤（价格+发布时间+去重）→ 记录命中
  → 命中时发送 Webhook 通知
  → 命中数达到 max_hits 时自动暂停
```

## 文件改动清单

| 文件 | 改动 |
|------|------|
| `backend/app/modules/xianyu/schemas.py` | 新增 `max_hits`、`published_within_hours` 字段 |
| `backend/app/modules/xianyu/monitor_store.py` | 无需改动（JSON 存储自动兼容新字段） |
| `backend/app/modules/xianyu/service.py` | `run_monitor_task()` 增加过滤逻辑和通知调用 |
| `backend/app/api/v1/notify.py` | 配置持久化 + 提供 `send_monitor_notification()` |
| `backend/app/api/v1/xianyu.py` | 无需改动（已有完整监控 API） |
| `backend/app/main.py` | 启动时调用 `ensure_monitor_runner()` |
| `web-vue/src/views/xianyu/index.vue` | 添加"添加监控"按钮和跳转逻辑 |
| `web-vue/src/views/xianyu/components/XianyuMonitorPanel.vue` | 编辑表单新增字段、自动编辑模式 |
| `web-vue/src/api/modules/xianyu.ts` | 接口类型新增字段 |
