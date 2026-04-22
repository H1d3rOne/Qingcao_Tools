# 闲鱼管理 Tab 与自动发货接入设计

## 目标

在当前项目既有的闲鱼工具页中，将底部 `发布` Tab 替换为 `管理` Tab，并按本项目现有分层结构接入参考项目中的以下能力：

1. 商品管理
2. 自动发货规则管理
3. 自动发货后台运行链路
4. 运行状态与执行记录展示

本次目标是先形成**最小可用闭环**：

- 能真实同步商品
- 能管理自动发货规则
- 能从现有聊天/订单链路中识别一次待发货场景并触发自动发货
- 能记录成功/失败结果并在 UI 中可见
- 能保留人工补发路径

不要求第一版完全迁移参考项目全部复杂匹配与风控恢复细节。

---

## 已确认的产品决策

### 1. 底部导航调整

当前闲鱼工具底部导航：

- 搜索
- 监控
- 发布
- 聊天

调整为：

- 搜索
- 监控
- 管理
- 聊天

即：**现有 `publish` 入口直接替换为 `manage` 入口**，本次不新增第五个底部 Tab。

### 2. 管理 Tab 内部结构

管理 Tab 下拆分为三个子面板：

1. **商品管理**
2. **自动发货**
3. **运行状态**

### 3. 技术策略

采用“**按本项目分层重构接入**”方案，而不是整体搬运参考项目原始目录结构。

核心原则：

- 复用当前项目已有 `XianyuService`、路由层、API 模块、订单面板能力
- 新增独立 store/runtime 模块承接自动发货本地状态与后台执行逻辑
- 避免把参考项目的数据库结构、全局对象和超大文件原样挪入当前项目

---

## 整体架构

### 前端

入口仍为：`web-vue/src/views/xianyu/index.vue`

但其职责调整为：

- 维护底部主 Tab：`search / monitor / manage / chat`
- 将原 `publish` 占位替换为 `manage`
- 将管理功能下沉到独立总面板组件 `XianyuManagePanel.vue`

管理总面板内部分为三个子组件：

- `XianyuManageItemsPanel.vue`
- `XianyuManageDeliveryPanel.vue`
- `XianyuManageRuntimePanel.vue`

### 后端

沿用当前项目的层次：

- API：`backend/app/api/v1/xianyu.py`
- Schema：`backend/app/modules/xianyu/schemas.py`
- Service：`backend/app/modules/xianyu/service.py`

在此基础上新增模块：

- `backend/app/modules/xianyu/item_store.py`
- `backend/app/modules/xianyu/delivery_store.py`
- `backend/app/modules/xianyu/delivery_runtime.py`

职责划分：

#### `service.py`
负责真实闲鱼接口调用与基础业务动作：

- 商品列表同步
- 商品详情更新
- 订单列表与订单发货
- 自动发货执行所需的基础 API（聊天发消息、虚拟发货接口等）

#### `item_store.py`
负责商品本地持久化状态与商品级配置：

- 商品缓存列表
- 商品详情文本
- 商品配置开关（例如多数量发货）
- 同步时间、更新时间等本地元信息

#### `delivery_store.py`
负责自动发货本地配置与运行记录：

- 自动发货规则 CRUD
- 规则启停状态
- 规则匹配范围
- 最近执行记录
- 运行时总状态快照

#### `delivery_runtime.py`
负责后台自动发货运行时：

- 监听现有聊天/订单相关事件
- 解析订单/商品线索
- 执行规则匹配
- 调用 `service.py` 完成聊天发货与虚拟发货
- 将结果写入 `delivery_store.py`

---

## 前端设计

### 1. `index.vue` 调整

#### 当前问题
`index.vue` 已经承载搜索、详情、监控跳转、聊天跳转等较多逻辑，如果继续把管理逻辑直接堆入，会进一步变成超大文件。

#### 调整方式
仅保留：

- 底部导航定义
- 当前账号态与公共上下文
- 各主面板切换

新增：

- `bottomTabs` 中将 `publish` 改为 `manage`
- `activeBottomTab === 'manage'` 时渲染 `XianyuManagePanel`

### 2. `XianyuManagePanel.vue`

作为管理 Tab 的总容器，负责：

- 顶部二级导航切换（商品管理 / 自动发货 / 运行状态）
- 共享刷新动作
- 共享当前登录用户信息
- 在必要时协调子面板数据刷新

建议 props：

- `currentUser?: XianyuUserProfile | null`

内部状态：

- `activeManageTab: 'items' | 'delivery' | 'runtime'`

### 3. `XianyuManageItemsPanel.vue`

负责商品管理相关能力：

- 查看商品列表
- 按条件筛选商品
- 单页同步商品
- 全量同步商品
- 查看/编辑商品详情
- 删除本地商品缓存
- 开关“多数量发货”

V1 必须能力：

- 商品列表
- 单页同步 / 全量同步
- 编辑商品详情
- 多数量发货开关

V1 可先不做：

- 非关键字段的复杂批量编辑
- 参考项目中所有本地管理字段的完全复刻

### 4. `XianyuManageDeliveryPanel.vue`

负责自动发货规则管理：

- 规则列表
- 新增规则
- 编辑规则
- 删除规则
- 启用/停用规则
- 基础匹配条件配置
- 发货内容配置

V1 规则配置范围：

- 关联商品 ID（可选）
- 关键词/规则名称
- 是否启用
- 发货文本内容
- 是否允许调用虚拟发货接口
- 是否开启图片/富内容（可先预留字段）

V1 可先不做：

- 复杂多规格精确匹配
- 多层兜底匹配优先级编辑器
- 参考项目全部高级策略项

### 5. `XianyuManageRuntimePanel.vue`

负责运行状态可视化：

- 自动发货运行总状态
- 最近执行记录列表
- 最近失败原因
- 最近成功记录
- 待处理/待人工补发提示
- 必要时可跳转到订单面板或复用订单能力

V1 必须保证：

- 用户能看到自动发货是否在运行
- 用户能看到最近一次/多次执行结果
- 用户能定位失败原因
- 用户能通过已有订单能力人工补发

---

## API 设计

统一放在：`backend/app/api/v1/xianyu.py`

### 路由分组

#### 商品管理
- `GET /xianyu/manage/items`
- `POST /xianyu/manage/items/sync-page`
- `POST /xianyu/manage/items/sync-all`
- `GET /xianyu/manage/items/{item_id}`
- `PUT /xianyu/manage/items/{item_id}`
- `DELETE /xianyu/manage/items/{item_id}`
- `PUT /xianyu/manage/items/{item_id}/multi-quantity-delivery`

#### 自动发货规则
- `GET /xianyu/manage/delivery-rules`
- `POST /xianyu/manage/delivery-rules`
- `PUT /xianyu/manage/delivery-rules/{rule_id}`
- `DELETE /xianyu/manage/delivery-rules/{rule_id}`
- `POST /xianyu/manage/delivery-rules/{rule_id}/toggle`
- `POST /xianyu/manage/delivery-rules/test-match`（可选，若 V1 负担过重可后移）

#### 运行状态
- `GET /xianyu/manage/runtime/status`
- `GET /xianyu/manage/runtime/executions`
- `POST /xianyu/manage/runtime/start`
- `POST /xianyu/manage/runtime/stop`
- `POST /xianyu/manage/runtime/replay/{execution_id}`（可后移）

#### 既有订单接口
保留现有：
- `GET /xianyu/orders`
- `POST /xianyu/orders/ship`

原因：

- 这些接口已经存在并可复用
- 运行状态面板不需要重造订单域能力
- 管理域和订单域可逻辑关联，但不强行混成同一路由前缀

---

## Schema 设计

统一补充到：`backend/app/modules/xianyu/schemas.py`

### 商品管理模型

#### `XianyuManageItem`
建议字段：

- `item_id: str`
- `item_title: str`
- `item_price: str`
- `item_image: str`
- `item_status: str`
- `item_detail: str`
- `multi_quantity_delivery: bool`
- `updated_at: int | str`
- `synced_at: int | str`

#### `XianyuManageItemPage`
- `items: list[XianyuManageItem]`
- `total: int`
- `page: int`
- `page_size: int`
- `has_more: bool`

#### `XianyuManageItemSyncPageRequest`
- `page: int`
- `page_size: int`

#### `XianyuManageItemUpdateRequest`
- `item_detail: str`

#### `XianyuManageItemMultiQuantityUpdateRequest`
- `enabled: bool`

### 自动发货规则模型

#### `XianyuDeliveryRule`
建议字段：

- `id: str`
- `name: str`
- `enabled: bool`
- `item_id: str`
- `keyword: str`
- `match_mode: str`（V1 可只支持 `item_id` / `keyword` 两类）
- `delivery_text: str`
- `send_chat_text: bool`
- `send_dummy_ship: bool`
- `created_at: int`
- `updated_at: int`

#### `XianyuDeliveryRuleCreateRequest`
- `name: str`
- `enabled: bool = True`
- `item_id: str = ''`
- `keyword: str = ''`
- `match_mode: str`
- `delivery_text: str`
- `send_chat_text: bool = True`
- `send_dummy_ship: bool = True`

#### `XianyuDeliveryRuleUpdateRequest`
全部字段允许可选更新。

### 运行状态模型

#### `XianyuDeliveryExecutionRecord`
建议字段：

- `id: str`
- `rule_id: str`
- `rule_name: str`
- `order_id: str`
- `item_id: str`
- `buyer_id: str`
- `status: str`（`success` / `failed` / `skipped`）
- `message: str`
- `created_at: int`

#### `XianyuDeliveryRuntimeStatus`
建议字段：

- `running: bool`
- `last_event_at: int`
- `last_success_at: int`
- `last_failure_at: int`
- `last_error: str`
- `enabled_rule_count: int`
- `recent_success_count: int`
- `recent_failure_count: int`

---

## 自动发货最小闭环设计

### V1 目标

形成从事件到执行的完整闭环：

1. 接收现有聊天/订单链路中的事件
2. 提取订单 ID、商品 ID、买家标识和文本线索
3. 读取商品配置与自动发货规则
4. 命中规则后执行自动发货动作
5. 写入执行记录
6. 在运行状态面板中展示结果

### V1 事件流

```text
聊天推送 / 订单相关事件
  -> 提取 order_id / item_id / buyer_id / message text
  -> 商品归属校验
  -> 自动发货规则匹配
  -> 执行聊天发货文本 / 虚拟发货接口
  -> 记录 success / failed / skipped
  -> 更新运行状态视图
```

### V1 支持的执行动作

#### 1. 聊天消息发货
复用当前项目已有聊天能力：

- 通过会话能力发送文本消息
- 发货文本来自规则配置 `delivery_text`

#### 2. 虚拟商品确认发货
复用当前项目已有接口：

- `ship_merchant_order()`
- 使用 `mtop.taobao.idle.logistic.consign.dummy`

### V1 必须具备的保障

- 同一事件不要无限重复发货
- 执行异常必须被记录
- 规则停用后立即不参与匹配
- 找不到规则时要有 `skipped` 记录或可观测日志
- 自动发货失败后，用户仍可通过订单面板人工发货

---

## 与现有代码的衔接方式

### 复用点

#### 1. 订单能力
已存在：

- `XianyuOrderPanel.vue`
- `listXianyuOrders()`
- `shipXianyuOrder()`
- `XianyuService.list_merchant_orders()`
- `XianyuService.ship_merchant_order()`

这些继续保留，不重复实现。

#### 2. 聊天能力
已存在：

- `XianyuChatPanel.vue`
- 聊天 profile / 会话 / 消息 / 发消息能力
- 后台聊天 listener 雏形

自动发货运行时优先复用现有聊天链路，而不是另起一套 websocket 体系。

#### 3. 数据持久化模式
当前监控/AI 配置已经有本地 store 思路，自动发货与商品管理优先沿用这一思路，而不是引入参考项目那种整套数据库结构与跨模块全局管理方式。

---

## 错误处理设计

### 后端

#### 商品同步错误
- 返回明确错误信息
- 不覆盖已有本地可用缓存
- 记录同步失败时间与原因

#### 自动发货执行错误
- 必须写入 execution record
- 标记为 `failed`
- `message` 中写入可读失败原因
- 更新 runtime status 的 `last_error` 与 `last_failure_at`

#### 规则匹配失败
- 不视为系统异常
- 记录为 `skipped` 或在日志中可见

### 前端

#### 商品管理面板
- 同步失败时提示“同步失败，但保留本地列表”
- 编辑失败时不关闭弹窗

#### 自动发货规则面板
- 保存失败时保留表单输入
- 启停失败时回滚 UI 状态

#### 运行状态面板
- 加载失败时显示错误卡片
- 不隐藏已有最近记录

---

## 测试策略

### 后端测试

新增或补充以下测试方向：

1. 商品管理 API
   - 列表返回
   - 单页同步请求
   - 全量同步请求
   - 更新详情
   - 多数量发货开关更新

2. 自动发货规则 API
   - 规则 CRUD
   - 启停切换
   - 空规则/非法参数校验

3. 自动发货运行时
   - 事件输入后能命中规则
   - 命中后调用聊天发送或虚拟发货执行器
   - 成功时写入 success record
   - 异常时写入 failed record
   - 未命中时写入 skipped 或保留可观测行为

### 前端测试

优先补组件级与 API 交互级测试：

1. `index.vue`
   - `publish` -> `manage` tab 替换

2. `XianyuManagePanel.vue`
   - 子 tab 切换

3. `XianyuManageItemsPanel.vue`
   - 列表加载
   - 同步动作触发
   - 编辑详情提交

4. `XianyuManageDeliveryPanel.vue`
   - 规则列表
   - 新建/编辑/删除/启停

5. `XianyuManageRuntimePanel.vue`
   - 运行状态展示
   - 最近执行记录展示

---

## 分阶段范围

### V1 本次实现

必须完成：

- 底部 `publish` -> `manage`
- 管理总面板与三个子面板骨架
- 商品同步与商品管理基本操作
- 自动发货规则 CRUD + 启停
- 自动发货运行时最小闭环
- 执行记录与运行状态可视化
- 复用现有订单人工补发

### V2 后续补强

后移内容：

- 复杂多规格精确匹配
- 多层兜底规则优先级策略
- 参考项目中更完整的风控恢复逻辑
- 更复杂的通知渠道联动
- 完整历史迁移与高级运营能力

---

## 文件边界总结

### 前端
- 修改：`web-vue/src/views/xianyu/index.vue`
- 新增：`web-vue/src/views/xianyu/components/XianyuManagePanel.vue`
- 新增：`web-vue/src/views/xianyu/components/XianyuManageItemsPanel.vue`
- 新增：`web-vue/src/views/xianyu/components/XianyuManageDeliveryPanel.vue`
- 新增：`web-vue/src/views/xianyu/components/XianyuManageRuntimePanel.vue`
- 修改：`web-vue/src/api/modules/xianyu.ts`

### 后端
- 修改：`backend/app/api/v1/xianyu.py`
- 修改：`backend/app/modules/xianyu/schemas.py`
- 修改：`backend/app/modules/xianyu/service.py`
- 修改：`backend/app/modules/xianyu/__init__.py`
- 新增：`backend/app/modules/xianyu/item_store.py`
- 新增：`backend/app/modules/xianyu/delivery_store.py`
- 新增：`backend/app/modules/xianyu/delivery_runtime.py`

### 测试
- 新增/修改：`backend/tests/*xianyu*`
- 新增/修改：`web-vue` 对应组件/API 测试文件

---

## 最终建议

本次实现严格遵守以下顺序：

1. 先完成导航替换与管理面板骨架
2. 再接商品管理 API 与 UI
3. 再接自动发货规则 CRUD
4. 最后接入运行时最小闭环
5. 用执行记录与运行状态面板收口，保证可观测与可人工补救

这样可以在不破坏当前项目结构的前提下，把参考项目最有价值的“商品管理 + 自动发货”能力稳定迁入本项目。
