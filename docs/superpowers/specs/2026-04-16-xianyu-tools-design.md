# 闲鱼工具模块补全设计

## 目标

基于参考项目 `/Users/Apple/Documents/Projects/Other/js_reverse` 中已验证的闲鱼 API 调用方式，补全本项目闲鱼工具页中尚未落地的两个模块：

- 关键词监控
- 完整发布

同时保持现有的搜索、详情、聊天能力继续可用，并尽量沿用当前项目已有的接口风格、Schema 组织和页面结构。

## 范围

### 本次纳入

- `monitor` tab：实现关键词监控任务管理、轮询执行、命中结果展示
- `publish` tab：实现完整商品发布表单、图片上传、发布提交
- 后端新增对应 API、Schema、持久化和服务逻辑
- 前端新增监控和发布面板，并与现有搜索/详情联动

### 本次不纳入

- 卖家监控
- 指定商品监控
- 批量发布
- 自动上下架、自动改价
- 已发布商品编辑
- 多账号支持
- 复杂任务调度系统（Redis/Celery/消息队列）

## 设计原则

1. **优先复用当前项目的闲鱼模块**
   - 以 `backend/app/modules/xianyu/service.py` 为核心继续扩展
   - 不将参考项目整仓复制进当前项目

2. **参考项目只作为协议与参数来源**
   - 复用其 API 名称、参数结构、签名方式、响应解析经验
   - 在当前项目内重新组织成符合现有风格的服务方法

3. **先做能稳定使用的闭环**
   - 监控先做关键词监控
   - 发布先做单商品完整发布

4. **保持前后端协议统一**
   - 新接口继续使用当前项目 `ApiResponse[T]`
   - 前端沿用现有 `web-vue/src/api/modules/xianyu.ts` 风格

## 现状评估

### 已完成能力

当前项目的闲鱼模块已经具备：

- 搜索
- 商品详情
- 用户信息
- 聊天资料
- 会话列表
- 消息列表
- 发送消息
- 红点清理
- WebSocket 聊天推送

### 当前缺口

前端 `web-vue/src/views/xianyu/index.vue` 中：

- `search` 已完成
- `chat` 已完成
- `monitor` 仍为占位
- `publish` 仍为占位

### 参考项目能力

参考项目 `js_reverse` 中已具备统一门面与底层接口经验：

- 用户/首页接口
- 搜索/筛选/建议词/详情
- IM/聊天
- cookies 登录
- 统一门面 `UnifiedGoofishAPI`

本次优先吸收其：

- 搜索接口参数组织方式
- 闲鱼商品发布所需的元数据/提交调用方式
- 图片上传调用方式
- IM/会话数据结构映射经验

## 总体架构

本次改动分为四层：

1. **参考接口适配层**
   - 在当前项目闲鱼 service 内新增若干私有方法
   - 按参考项目协议组织参数、签名、调用与解析

2. **闲鱼领域服务层**
   - `XianyuService` 中新增监控和发布能力
   - 对上提供稳定、面向业务的返回结构

3. **API 层**
   - 在 `backend/app/api/v1/xianyu.py` 中新增监控和发布接口
   - 输入输出都使用清晰的 Pydantic Schema

4. **前端页面层**
   - `xianyu/index.vue` 的 `monitor` 和 `publish` tab 替换为真实功能
   - 与搜索、详情、聊天形成同页工具闭环

## 后端设计

### 一、监控模块

#### 能力定义

监控模块第一阶段只支持“关键词监控任务”。

每个任务包含：

- `id`
- `name`
- `keyword`
- `page`
- `page_size`
- `sort_field`
- `sort_value`
- `prop_values`
- `min_price`
- `max_price`
- `interval_seconds`
- `enabled`
- `created_at`
- `updated_at`
- `last_run_at`
- `last_status`
- `last_error`
- `seen_item_ids`
- `latest_hits`

#### 执行模型

- 服务启动后初始化监控管理器
- 从本地 JSON 文件加载任务与状态
- 启动轻量轮询协程
- 按任务时间间隔执行真实闲鱼搜索
- 用 `item_id` 去重识别新商品
- 更新任务状态并写回本地

#### 持久化

新增一个闲鱼监控状态文件，放在后端可写目录中，例如：

- `backend/config/xianyu_monitor_tasks.json`

内容包含：

- 任务定义
- 每个任务的已见商品集合
- 最近命中结果
- 最近执行状态

#### API 设计

新增接口：

- `GET /api/v1/xianyu/monitor/tasks`
- `POST /api/v1/xianyu/monitor/tasks`
- `PUT /api/v1/xianyu/monitor/tasks/{task_id}`
- `DELETE /api/v1/xianyu/monitor/tasks/{task_id}`
- `POST /api/v1/xianyu/monitor/tasks/{task_id}/toggle`
- `POST /api/v1/xianyu/monitor/tasks/{task_id}/run`
- `GET /api/v1/xianyu/monitor/tasks/{task_id}/hits`

#### 结果展示策略

每次任务执行只保留有限窗口的最近命中结果，避免文件无限增长。

建议：

- 每个任务保留最近 50 条命中
- `seen_item_ids` 只保留最近窗口相关去重信息

### 二、发布模块

#### 能力定义

发布模块第一阶段支持单商品完整发布，覆盖：

- 标题
- 描述
- 售价
- 原价
- 分类
- 成色
- 发货地
- 运费方式
- 是否包邮
- 属性项
- 标签/补充项
- 图片上传

#### 发布流程

发布拆成三步：

1. 获取发布所需元数据
   - 分类
   - 成色
   - 区域
   - 属性项
   - 运费相关配置

2. 上传图片
   - 接收前端上传文件
   - 调用闲鱼图片上传接口
   - 返回图片标识/URL/顺序信息

3. 提交发布
   - 按闲鱼要求组装 payload
   - 调用正式发布接口
   - 返回发布结果、商品 ID、原站链接或错误信息

#### 草稿策略

为降低表单丢失风险：

- 前端本地保存草稿
- 后端本次不强制做数据库草稿
- 后端接口只负责发布元数据、图片上传、正式提交

#### API 设计

新增接口：

- `GET /api/v1/xianyu/publish/meta`
- `POST /api/v1/xianyu/publish/upload-image`
- `POST /api/v1/xianyu/publish/submit`

如参考项目协议要求拆分更多元数据接口，再在实现阶段补充细化，但对前端维持统一入口优先。

### 三、参考项目接入方式

不直接依赖参考项目运行时模块导入，而是：

- 阅读并提取其协议调用规则
- 在当前项目中补充对应请求方法
- 复用已有 `httpx`/cookie/sign 逻辑风格

如某些协议特别复杂，允许在当前项目里加入小型适配辅助文件，但必须：

- 职责单一
- 只为闲鱼服务
- 不引入参考项目中与本项目无关的 CLI 或 facade 结构

## 前端设计

### 一、监控 tab

`monitor` 区分成三块：

1. **任务表单**
   - 新建监控任务
   - 字段包括关键词、分页、排序、筛选、价格区间、轮询间隔
   - 支持从当前搜索条件一键生成

2. **任务列表**
   - 展示任务启用状态、下次执行、上次执行结果、命中新品数量
   - 支持启停、立即执行、删除、编辑

3. **命中结果**
   - 展示最近新命中的商品卡片
   - 支持跳详情、带回搜索页、查看命中来源任务

### 二、发布 tab

发布区分成四块：

1. **基础信息**
   - 标题
   - 描述
   - 价格
   - 原价

2. **商品配置**
   - 分类
   - 成色
   - 地区
   - 运费
   - 其他属性

3. **图片上传**
   - 多图上传
   - 排序
   - 删除
   - 上传状态反馈

4. **提交区**
   - 草稿保存/恢复（前端本地）
   - 发布按钮
   - 发布结果提示

### 三、与现有搜索页联动

监控与搜索之间联动：

- 在搜索结果区可一键“加入监控”
- 直接带入关键词、筛选、排序、价格区间

发布与搜索页联动保持弱耦合：

- 发布成功后展示商品 ID/链接
- 不强制跳回搜索

## 数据与错误处理

### 监控

- 单任务失败不影响其他任务
- 失败信息写入任务状态
- 前端展示最近错误，但不打断整个页面

### 发布

- 图片上传失败时单张报错，允许用户重试
- 表单校验失败在前端先拦截
- 闲鱼接口返回业务错误时原样转成用户可读消息

### Cookie

- 继续复用系统设置中已配置的闲鱼 cookie
- 若 cookie 缺失或失效：
  - 后端统一抛出明确错误
  - 前端提示去设置页更新

## 测试设计

### 后端测试

优先补这些测试：

1. 监控任务 CRUD
2. 监控任务执行与新商品识别
3. 监控任务状态持久化
4. 发布表单 payload 组装
5. 图片上传响应解析
6. 发布结果解析

### 前端验证

前端至少验证：

1. `monitor` tab 不再占位
2. 可创建/启停/删除任务
3. 可查看命中结果
4. `publish` tab 不再占位
5. 可上传图片并提交发布

## 文件影响范围

### 后端

- 修改：`backend/app/modules/xianyu/service.py`
- 修改：`backend/app/modules/xianyu/schemas.py`
- 修改：`backend/app/api/v1/xianyu.py`
- 可能新增：`backend/app/modules/xianyu/monitor_store.py`
- 可能新增：`backend/app/modules/xianyu/publish_helpers.py`

### 前端

- 修改：`web-vue/src/api/modules/xianyu.ts`
- 修改：`web-vue/src/views/xianyu/index.vue`
- 可能新增：`web-vue/src/views/xianyu/components/XianyuMonitorPanel.vue`
- 可能新增：`web-vue/src/views/xianyu/components/XianyuPublishPanel.vue`

### 文档

- 本设计文档
- 后续 implementation plan

## 成功标准

完成后应满足：

- 闲鱼页四个 tab 都是可用功能，不再有监控/发布占位
- 搜索能力继续可用
- 聊天能力继续可用
- 监控可真实运行关键词轮询并识别新品
- 发布可完成完整单商品发布闭环
- 新能力遵循当前项目的接口、Schema、页面风格

## 自检

### 占位检查

- 无 `TODO`
- 无 `TBD`
- 无未定义“后续再说”的关键依赖

### 一致性检查

- 范围与用户确认一致：监控=关键词监控，发布=完整发布
- 架构与当前项目结构一致：扩展现有 xianyu 模块，而非整仓迁移参考项目

### 范围检查

- 方案聚焦于一个实现周期内可落地的监控与发布
- 未混入卖家监控、批量发布等额外子项目

### 歧义检查

- “各个模块”已明确限定为当前闲鱼页中的 `monitor + publish`
- 搜索/详情/聊天仅做必要联动，不作为本轮重构目标
