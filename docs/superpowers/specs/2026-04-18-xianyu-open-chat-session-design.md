# 闲鱼详情页项目内拉起聊天会话设计

## 目标
让闲鱼详情弹窗中的“联系卖家”按钮优先在项目内直接打开聊天会话，而不是跳转原站 IM 页面。

## 用户期望
- 点击“联系卖家”后，优先项目内打开聊天
- 成功时自动切到聊天 tab 并打开对应会话
- 失败时只提示失败，不跳原站、不自动发消息、不离开当前页面

## 当前现状
### 前端
- `web-vue/src/views/xianyu/index.vue` 中详情弹窗已具备 `item_id` 与 `seller_user_id`
- `web-vue/src/views/xianyu/components/XianyuChatPanel.vue` 当前只能加载已有会话列表，并基于 `cid` 选中已有会话
- 详情页与聊天面板之间还没有“外部指定打开会话”的联动通道

### 后端
- `backend/app/modules/xianyu/service.py` 已支持：
  - 获取聊天会话列表
  - 获取会话消息
  - 发消息 `send_chat_text`
- 发送消息链路内部已经具备 `createSingleChatCoversation / createSingleChatConversationOption / receiverScope` 等会话上下文结构，说明服务端已有部分单聊创建能力可复用
- 但当前没有“打开或创建会话”的独立接口

## 方案选择
采用“新增后端打开/创建会话接口 + 前端联动聊天面板”的方案。

不采用：
- 仅切聊天 tab + 查已有会话：无法满足“新建会话”目标
- 自动发送默认消息来带起会话：行为过重，且不符合“失败只提示、不自动发消息”的要求

## 后端设计
### 新接口
新增：
- `POST /api/v1/xianyu/chat/open-session`

请求体：
- `item_id: string`
- `peer_user_id: string`

响应体：
- `success: boolean`
- `message: string`
- `cid?: string`
- `session?: XianyuChatConversation`

### 服务逻辑
在 `XianyuService` 中新增 `open_chat_session(item_id, peer_user_id)`：

1. 校验参数不能为空
2. 先获取当前会话列表 `list_chat_conversations(offset=0, limit=40)`
3. 优先匹配：
   - `session.peer_user_id == peer_user_id`
   - 若 `item_id` 也一致则直接命中
   - 若没有 item 完全匹配，则退化为 peer 匹配的首个会话
4. 若命中已有会话：
   - 返回该 `cid` 和会话对象
5. 若未命中：
   - 使用现有 chat client 链路，构造“最小单聊创建请求”尝试向服务端打开/创建会话
   - 不发送业务文本消息
   - 若服务端成功返回会话信息，则转成 `XianyuChatConversation`
6. 若创建失败：
   - 返回明确错误消息
   - 前端只提示，不跳转

### 风险控制
- 不自动发消息
- 不修改现有发送消息逻辑
- 新能力只服务“从详情页进入聊天”场景
- 若远端只允许已有会话，不做激进兜底行为

## 前端设计
### 详情页
在 `web-vue/src/views/xianyu/index.vue`：
- 点击“联系卖家”时，调用 `/xianyu/chat/open-session`
- 成功时：
  - 关闭详情弹窗或保持弹窗关闭（实现时择一，默认关闭更自然）
  - 切换 `activeBottomTab = 'chat'`
  - 通过状态或 props 把目标 `cid` 传给聊天面板
- 失败时：
  - `ElMessage.error(message)`
  - 不跳原站，不切 tab，不打开新页面

### 聊天面板
在 `XianyuChatPanel.vue` 增加一个外部入口，例如：
- `preferredCid?: string`

行为：
- 当 `preferredCid` 变化时，若当前会话列表中存在该 `cid`，则自动选中并加载消息
- 若会话列表未加载到该 `cid`，则先刷新列表再尝试匹配

## UI 行为
- 成功进入聊天后，用户直接看到该卖家的会话
- 失败只弹错误提示
- 不做任何自动消息发送
- 保持现有主题风格，不额外引入新视觉系统

## 涉及文件
### 后端
- `backend/app/modules/xianyu/service.py`
- `backend/app/modules/xianyu/schemas.py`
- `backend/app/api/v1/xianyu.py`
- `backend/tests/test_xianyu_auth_api.py` 或新增 chat open session 专项测试

### 前端
- `web-vue/src/api/modules/xianyu.ts`
- `web-vue/src/views/xianyu/index.vue`
- `web-vue/src/views/xianyu/components/XianyuChatPanel.vue`

## 验收标准
1. 从详情页点击“联系卖家”时，能够在项目内直接切到聊天并打开对应会话
2. 若卖家已有历史会话，优先打开历史会话
3. 若服务端允许创建新会话，能够在不发送消息的情况下建立会话并打开
4. 若失败，只提示失败，不跳原站、不打开新页面、不自动发送消息
5. 不影响现有聊天列表、消息加载、发送消息功能
