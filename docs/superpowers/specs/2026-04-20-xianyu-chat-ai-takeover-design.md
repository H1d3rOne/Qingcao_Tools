# 闲鱼聊天 AI 接管设计

## 目标

在本项目的闲鱼聊天模块中接入 AI 自动回复能力，参考 `/Users/Apple/Documents/Projects/Github/XianYuApis` 中 `handle_message -> your_ai_agent -> send_msg` 的思路，但保持本项目现有页面结构、闲鱼登录态、消息 token、WebSocket 推送和发送链路不变。

第一版目标是：

- 在 **聊天页在线时** 启用 AI 接管
- 支持 **全局总开关 + 会话级开关**
- 仅对 **对方发来的文本消息** 自动回复
- 使用 **OpenAI `chat/completions` 格式** 调用模型
- 增加可配置的模型参数与后端本地持久化
- 不影响现有人工聊天、商品上下文展示和会话列表体验

## 范围

### 本次纳入

- 后端新增 AI 配置持久化、会话级开关持久化、AI 自动回复编排
- 前端聊天页新增 AI 总开关、当前会话 AI 开关、AI 配置入口
- 前端会话列表增加轻量 AI 状态标记
- 后端在现有闲鱼聊天 WebSocket 代理链路中接入 AI 处理分支
- 使用 OpenAI `chat/completions` 兼容协议请求模型

### 本次不纳入

- 页面关闭后的后台常驻 AI 托管
- 图片、商品卡片、系统消息、撤回消息的 AI 自动处理
- 多闲鱼账号隔离的 AI 配置
- 复杂规则引擎（关键词、工作时间、延迟回复、黑白名单）
- 多模型路由、流式生成、函数调用

## 已确认需求

1. AI 控制方式：**全局总开关 + 会话级单独开关**
2. 生效范围：**仅页面在线时生效**
3. 触发条件：**仅对文本消息自动回复**
4. AI 配置项：
   - `base_url`
   - `api_key`
   - `model`
   - `system_prompt`
   - `temperature`
5. AI 配置保存方式：**整个闲鱼模块共用一套配置**
6. 前端布局：
   - 左侧顶部“账号头像 + 昵称”所在行，新增：
     - `AI 总开关`
     - `当前会话 AI 开关`
     - `AI 配置按钮`
   - 左侧会话列表保留轻量 `AI 开 / AI 关` 状态标记
   - 右侧聊天头部继续只展示商品图、商品标题、卖家信息等商品上下文

## 总体方案

采用 **后端接管 AI，绑定当前聊天页在线状态** 的方案。

### 方案说明

- 前端继续连接现有 `/api/v1/xianyu/chat/ws`
- 后端继续作为闲鱼 WebSocket 推送代理
- 后端收到推送后，先照常转发给前端
- 同时在后端判断该消息是否满足 AI 接管条件
- 若满足，则后端调用配置好的 OpenAI `chat/completions` 接口
- 拿到回复文本后，复用现有 `send_chat_text()` 发送到闲鱼会话

### 选择原因

- `api_key` 保留在后端，不暴露到前端
- 最大程度复用现有聊天收发链路
- 最贴合“页面在线时生效”的约束
- 后续若要扩展为后台常驻托管，可在此方案上继续演进

## 架构设计

### 一、后端结构

在 `backend/app/modules/xianyu/service.py` 周边增加三类能力：

1. **AI 配置管理**
2. **会话 AI 开关管理**
3. **消息去重 + 自动回复编排**

建议新增/扩展以下文件：

- `backend/app/modules/xianyu/service.py`
- `backend/app/modules/xianyu/schemas.py`
- `backend/app/api/v1/xianyu.py`
- `backend/config/xianyu_ai_config.json`
- `backend/config/xianyu_ai_sessions.json`
- `backend/tests/test_xianyu_chat_ai_config.py`
- `backend/tests/test_xianyu_chat_ai_trigger.py`
- `backend/tests/test_xianyu_chat_ai_api.py`

### 二、前端结构

建议新增/扩展以下位置：

- `web-vue/src/views/xianyu/components/XianyuChatPanel.vue`
- `web-vue/src/api/modules/xianyu.ts`

如状态较多，也可拆出小组件：

- `web-vue/src/views/xianyu/components/XianyuChatAiConfigDialog.vue`

## 数据持久化设计

### 1. AI 配置文件

路径：`backend/config/xianyu_ai_config.json`

建议结构：

```json
{
  "enabled": false,
  "base_url": "https://api.openai.com/v1",
  "api_key": "",
  "model": "gpt-4.1-mini",
  "system_prompt": "你是闲鱼客服助手，回复要简洁、礼貌、像真人卖家。",
  "temperature": 0.3
}
```

约束：

- `api_key` 只保存在后端
- 前端读取配置时返回脱敏值或额外字段标识“已配置”
- `temperature` 限定在合理范围（如 `0 ~ 2`）

### 2. 会话 AI 状态文件

路径：`backend/config/xianyu_ai_sessions.json`

建议结构：

```json
{
  "sessions": {
    "cid_xxx": true,
    "cid_yyy": false
  }
}
```

选择 `cid` 作为主键的原因：

- 与当前聊天系统天然一致
- 前端、消息列表、发送接口都直接使用 `cid`
- 不需要再额外组合 `peer_user_id + item_id`

## 后端接口设计

### 1. AI 配置接口

- `GET /api/v1/xianyu/chat/ai/config`
- `POST /api/v1/xianyu/chat/ai/config`

用途：

- 获取当前 AI 配置
- 更新当前 AI 配置

建议响应字段：

- `enabled`
- `base_url`
- `model`
- `system_prompt`
- `temperature`
- `api_key_configured`（布尔值）
- `api_key_masked`（可选，如 `sk-****abcd`）

说明：

- `POST` 时若前端未填写新 `api_key`，应保留旧值
- `GET` 不回传完整明文 `api_key`

### 2. 会话级开关接口

- `GET /api/v1/xianyu/chat/ai/sessions`
- `POST /api/v1/xianyu/chat/ai/sessions/{cid}`

用途：

- 批量拉取会话 AI 开关状态
- 修改单个会话的 AI 开关

建议 `POST` 请求体：

```json
{
  "enabled": true
}
```

### 3. 可选测试接口（建议纳入第一版）

- `POST /api/v1/xianyu/chat/ai/test`

用途：

- 用当前配置对一段文本做一次模型请求验证
- 用于 AI 配置弹窗中“测试连接 / 测试回复”

若实现成本偏高，可延后到第二版；但推荐第一版就加入，便于定位配置错误。

## Schema 设计

建议新增以下 Schema：

- `XianyuChatAiConfig`
- `XianyuChatAiConfigUpdateRequest`
- `XianyuChatAiSessionState`
- `XianyuChatAiSessionUpdateRequest`
- `XianyuChatAiTestRequest`
- `XianyuChatAiTestResponse`

关键字段建议：

### `XianyuChatAiConfig`

- `enabled: bool`
- `base_url: str`
- `model: str`
- `system_prompt: str`
- `temperature: float`
- `api_key_configured: bool`
- `api_key_masked: str`

### `XianyuChatAiConfigUpdateRequest`

- `enabled: bool`
- `base_url: str`
- `api_key: str | None`
- `model: str`
- `system_prompt: str`
- `temperature: float`

### `XianyuChatAiSessionState`

- `cid: str`
- `enabled: bool`

## 消息处理与触发规则

### 触发条件

只有在以下条件全部满足时，AI 才会自动回复：

1. 当前聊天页在线，且 `/api/v1/xianyu/chat/ws` 已建立连接
2. 全局 AI 总开关为开启
3. 当前会话 `cid` 的会话级 AI 开关为开启
4. 消息来自对方，而不是当前登录用户自己
5. 消息类型是文本消息
6. 该消息尚未被 AI 处理过
7. 当前会话允许发送（`can_send = true`）

### 非触发消息

以下消息直接忽略：

- 自己发出的消息
- 图片消息
- 商品卡片消息
- 系统消息 / 状态消息
- 无法提取文本正文的消息
- 已被 AI 处理过的重复推送

## AI 请求设计

使用 OpenAI `chat/completions` 格式。

### 请求 URL

`{base_url}/chat/completions`

### 请求头

```http
Authorization: Bearer <api_key>
Content-Type: application/json
```

### 请求体

```json
{
  "model": "gpt-4.1-mini",
  "temperature": 0.3,
  "messages": [
    {
      "role": "system",
      "content": "你是闲鱼客服助手，回复要简洁、礼貌、像真人卖家。"
    },
    {
      "role": "user",
      "content": "这个还在吗？"
    }
  ]
}
```

### 第一版上下文策略

第一版只传最小上下文，避免复杂度过高：

- `system_prompt`
- 当前这条用户文本
- 可选补充一条商品标题上下文（若提取方便）

推荐格式：

- system：系统提示词
- user：`商品标题：xxx
买家消息：xxx`

这样能提升回复贴合度，但不需要一次性带入整段历史消息。

## 防重与防自激设计

必须避免 AI 自己把自己触发起来。

### 需要的保护机制

1. **消息 ID 去重**
   - 后端维护一个最近处理消息 ID 的内存缓存
   - 同一条消息只处理一次
   - 建议保留最近 500~1000 条

2. **只处理入站消息**
   - `direction == 'in'`

3. **过滤自己发送的消息**
   - `sender_uid != current_user_id`

4. **AI 发出的消息不再回流触发**
   - 因为发送出去的消息本身属于出站消息，应自然被过滤

5. **失败不死循环重试**
   - AI 接口失败、本次发送失败时记录日志并放弃，不做无限自动重试

## 错误处理

AI 失败不能拖垮聊天主流程。

### 错误场景

- AI 配置缺失
- `api_key` 无效
- 模型接口超时
- 返回格式不符合预期
- 闲鱼消息发送失败
- 会话在此时已经不可发送

### 处理策略

- 记录后端日志
- 本次消息跳过 AI 回复
- WebSocket 代理照常工作，不中断前端聊天页
- 前端配置保存接口应明确返回错误信息，便于用户修正配置

## 前端交互设计

### 1. 左侧顶部信息区

在当前登录账号头像、昵称所在行，增加三个控件：

- `AI 总开关`
- `当前会话 AI 开关`
- `AI 配置按钮`

布局要求：

- 与账号头像、昵称处于同一行
- 位于左侧会话列表上方
- 右侧商品头部不放 AI 控件

### 2. 左侧会话列表

每个会话项保留当前头像、昵称、摘要结构，并增加轻量状态标记：

- `AI 开`
- `AI 关`

状态标记只做展示，不在列表项里放复杂按钮，避免布局拥挤。

### 3. AI 配置弹窗

弹窗字段：

- `base_url`
- `api_key`
- `model`
- `system_prompt`
- `temperature`
- `enabled`（也可直接通过总开关控制）

弹窗行为：

- 保存配置
- 关闭弹窗
- 可选加入“测试连接 / 测试回复”按钮

### 4. 当前会话 AI 开关

行为建议：

- 无选中会话时禁用
- 切换时立即调用后端接口持久化
- 变更成功后同步更新左侧对应会话的 AI 状态标记

### 5. 人工发送兼容

即使当前会话开启 AI：

- 仍允许用户在输入框中手动输入和发送
- 不锁死人工接管
- 第一版不做“AI 工作中”输入禁用

## 数据流

### 页面初始化

1. 加载聊天资料
2. 加载会话列表
3. 加载 AI 全局配置
4. 加载会话级 AI 状态
5. 建立 `/api/v1/xianyu/chat/ws` 连接

### 收到新消息

1. 后端收到闲鱼推送
2. 后端照常透传给前端
3. 后端解析消息
4. 判断是否满足 AI 触发条件
5. 调用 `chat/completions`
6. 生成回复文本
7. 调用现有发送消息方法回发
8. 前端通过现有刷新/推送看到新消息

### 用户改配置

1. 打开 AI 配置弹窗
2. 修改配置并保存
3. 后端写入 `xianyu_ai_config.json`
4. 前端局部刷新配置状态

### 用户切换会话级开关

1. 选中会话
2. 切换“当前会话 AI”
3. 后端写入 `xianyu_ai_sessions.json`
4. 左侧会话状态标记同步更新

## 测试策略

### 后端测试

1. **配置读写测试**
   - 配置文件不存在时返回默认值
   - 保存后再次读取一致
   - `api_key` 更新与保留逻辑正确

2. **会话状态测试**
   - `cid` 开关写入、读取正确
   - 不同会话互不影响

3. **触发规则测试**
   - 自己发出的消息不触发
   - 图片消息不触发
   - 全局关闭不触发
   - 会话关闭不触发
   - 文本入站消息触发

4. **AI API 调用测试**
   - 正确发出 `chat/completions` 请求
   - 正确解析 `choices[0].message.content`
   - 异常响应能被优雅处理

5. **去重测试**
   - 同一消息多次推送只回复一次

### 前端测试

1. AI 配置弹窗展示与保存
2. 左侧顶部开关与当前会话联动
3. 左侧会话列表状态标记渲染
4. 切换会话时“当前会话 AI”正确反映该 `cid` 状态
5. 无会话选中时当前会话开关禁用

## 实施边界与后续演进

### 第一版边界

- 仅页面在线时生效
- 仅文本消息自动回复
- 仅一套全局 AI 配置
- 仅最小消息上下文

### 后续可扩展项

- 后台常驻托管
- 基于历史消息的多轮上下文
- 工作时间/关键词/优先级规则
- 每个会话独立 prompt
- 多账号隔离配置
- 模型连通性测试与速率限制

## 结论

第一版采用“**后端 AI 接管 + 页面在线生效 + 全局配置 + 会话级开关 + 文本消息触发**”的实现方式，能够在最小改动现有聊天结构的前提下，把 AI 自动回复稳定接入本项目闲鱼聊天模块。

该设计保持了以下关键约束：

- 复用现有闲鱼真实聊天链路
- 不暴露模型密钥到前端
- 不破坏现有商品上下文展示
- 将 AI 控制集中在左侧顶部账号信息行
- 左侧会话列表仅保留轻量状态展示
