# 闲鱼浏览器辅助扫码登录设计

## 目标
把闲鱼工具的扫码登录从“纯 API + 指纹模拟”改成“真实浏览器会话辅助登录”，解决当前二维码生成后首次轮询即返回 `EXPIRED`、用户刚扫码就失效的问题。

## 用户期望
- 点击“二维码登录”后能稳定拿到可扫码、可确认的二维码
- 扫码成功后自动保存闲鱼 Cookie 到本地统一文件
- 登录成功后自动跳转到闲鱼工具页
- 项目里其他闲鱼模块继续从本地 Cookie 文件读取，不要求它们感知扫码实现细节
- 旧的手动 Cookie 登录继续可用

## 当前现状与根因
### 当前链路
- 前端 `web-vue/src/views/xianyu/login/index.vue` 调用：
  - `GET /api/v1/xianyu/auth/qrcode`
  - `POST /api/v1/xianyu/auth/check-login`
- 后端 `backend/app/modules/xianyu/service.py` 通过 `XianyuAPILogin`：
  - 初始化登录页
  - 本地拼装二维码 URL
  - 轮询 `/newlogin/qrcode/query.do`
  - 登录成功后导出 Cookie 并写入本地

### 已验证根因
本地复现实验已经证明：
- 二维码生成成功，但首次轮询 `qrCodeStatus` 就是 `EXPIRED`
- 该现象在“空指纹”“当前文件指纹”“最小化指纹”下都成立
- 说明问题不只是某几个静态字段过期，而是当前纯 `requests` 链路缺少真实浏览器上下文（页面运行态、挑战参数、浏览器环境、Cookie/Storage/JS 执行结果等）

结论：继续补静态指纹只能提升短期可用性，不能从根上解决扫码不稳定问题。

## 方案选择
采用“后端 Playwright 持久化浏览器上下文 + 真实页面登录态检测 + 成功后导出 Cookie”的方案。

### 不采用的方案
#### 1. 继续维护 `xianyu_fingerprint.json`
- 优点：改动小
- 缺点：已被当前问题证明不稳定，仍可能出现生成即过期、偶发风控、状态漂移

#### 2. 前端直接嵌入真实闲鱼登录页
- 优点：视觉上简单
- 缺点：跨域限制强、Cookie 难以安全回收、页面控制权弱，不适合作为本项目稳定能力

## 总体设计
在后端新增一个“浏览器辅助扫码登录管理器”，由它负责：
1. 启动并复用 Playwright 浏览器
2. 打开真实闲鱼登录页
3. 从真实页面获取二维码图片或二维码内容
4. 轮询真实页面登录状态
5. 登录成功后导出浏览器 Cookie
6. 按现有统一方式保存到 `backend/config/xianyu_cookies.json`

前端登录页默认改为调用新接口；旧 API 登录链路保留，但不再作为默认扫码路径。

## 后端设计
### 新增组件
建议新增文件：
- `backend/app/modules/xianyu/browser_login.py`

建议新增核心类：
- `XianyuBrowserLoginManager`
- `XianyuBrowserLoginSession`

### 会话职责
每个扫码会话负责：
- 唯一 `session_id`
- 浏览器上下文 `browser_context`
- 页面对象 `page`
- 创建时间/过期时间
- 当前状态：
  - `waiting`
  - `scanned`
  - `confirmed`
  - `success`
  - `expired`
  - `failed`
  - `cancelled`
- 最近错误信息
- 已提取二维码图片或二维码链接
- 登录成功后的 cookie 字符串（仅短暂保存在内存，用于返回与保存）

### 浏览器策略
采用 **持久化上下文**：
- 优先使用 Playwright Chromium
- 使用项目内专用目录保存浏览器用户数据，例如：
  - `backend/config/xianyu_browser_profile/`

原因：
- 能最大化保留真实页面登录态和风控相关上下文
- 比无状态上下文更接近真实用户行为
- 后续若用户再次登录，稳定性更高

### 页面流转
后端创建扫码会话时：
1. 启动浏览器上下文
2. 打开闲鱼真实登录页（使用当前站点真实入口）
3. 等待二维码区域渲染
4. 优先从页面 DOM 获取二维码 `img/src` 或 canvas 数据
5. 若 DOM 无法直接取到，则退化为对二维码区域截图，转成 base64 data URL 返回给前端
6. 后台轮询页面状态：
   - 是否出现“已扫码待确认”提示
   - 是否出现登录成功后的用户态特征
   - 是否跳转到已登录页面
   - 是否二维码失效

### Cookie 导出与保存
登录成功后：
1. 从 Playwright context 读取 cookies
2. 过滤 `goofish.com` 相关 Cookie
3. 转成现有闲鱼模块使用的 cookie string
4. 调用现有持久化函数：
   - `save_xianyu_cookie_string(..., source="browser_qrcode")`
5. 同步写入运行时：
   - `app_settings.cookies.xianyu = cookie_string`
6. 清理共享聊天 WS：
   - `self._shared_chat_client = None`

### 新增接口
#### 1. 启动扫码会话
`POST /api/v1/xianyu/auth/browser-qrcode/start`

响应：
- `success: bool`
- `message: str`
- `session_id: str`
- `qrcode_image?: str`
- `expires_in?: int`

说明：
- 默认有效期 5 分钟
- 若浏览器未安装或启动失败，返回明确错误

#### 2. 查询扫码状态
`GET /api/v1/xianyu/auth/browser-qrcode/status?session_id=...`

响应：
- `success: bool`
- `message: str`
- `status: waiting | scanned | confirmed | success | expired | failed | cancelled`
- `is_logged_in: bool`
- `login_token?: str`

说明：
- `success=true` 表示接口调用成功，不代表已登录
- 只有 `status=success` 时 `is_logged_in=true`

#### 3. 取消扫码会话
`POST /api/v1/xianyu/auth/browser-qrcode/cancel`

请求：
- `session_id: str`

响应：
- `success: bool`
- `message: str`

说明：
- 主动关闭浏览器页和上下文
- 前端切换页面、刷新二维码、离开登录页时调用

### 与旧接口关系
旧接口保留：
- `GET /auth/qrcode`
- `POST /auth/check-login`

但默认前端不再调用旧扫码链路。

保留原因：
- 避免影响已有代码或调试脚本
- 后续若要保留纯 API 实验路径仍有入口

## 前端设计
### 登录页默认改造
文件：
- `web-vue/src/views/xianyu/login/index.vue`
- `web-vue/src/api/modules/xianyu.ts`

行为改为：
1. 页面进入二维码 tab 时调用 `browser-qrcode/start`
2. 获取二维码图后展示
3. 每 2 秒轮询 `browser-qrcode/status`
4. 根据状态更新文案：
   - `waiting` => 等待扫码
   - `scanned` => 已扫码，请在手机确认
   - `confirmed` => 已确认，正在同步登录态
   - `success` => 登录成功并跳转
   - `expired/failed` => 展示错误并允许刷新
5. 页面卸载或重新获取二维码时调用 `cancel`

### UI 规则
- 沿用现有登录页布局，不新增复杂视觉结构
- 保留“刷新二维码”按钮
- 保留“Cookie 登录”tab 作为兜底
- 错误文案明确区分：
  - 浏览器依赖不可用
  - 二维码已失效
  - 登录成功但 Cookie 导出失败
  - 状态检查失败

## Cookie 读取兼容
项目内所有闲鱼能力继续从当前统一存储读取：
- `backend/config/xianyu_cookies.json`

这意味着：
- 搜索
- 商品详情
- 聊天
- AI 自动回复
- 其他闲鱼模块

都不需要知道登录来源是“手动 Cookie”还是“浏览器扫码”。

## 错误处理设计
### 可恢复错误
- 二维码失效
- 页面二维码元素未及时渲染
- 单次轮询失败
- 用户主动取消

处理：
- 返回明确状态/消息
- 保持前端可刷新重试

### 不可恢复错误
- Playwright 不可用
- 浏览器启动失败
- 页面结构长期变化导致二维码无法识别
- 登录成功但无法导出任何闲鱼 Cookie

处理：
- 明确提示具体原因
- 不伪装成“二维码过期”
- 建议用户暂时使用 Cookie 登录

## 安全与资源控制
- 浏览器 profile 仅用于闲鱼登录相关上下文
- 一个用户界面同时仅保留一个活跃扫码会话；新会话创建时关闭旧会话
- 已完成/失败/过期会话在短时间内自动清理
- 不在日志中打印完整 Cookie，仅记录脱敏摘要

## 涉及文件
### 后端
- `backend/app/modules/xianyu/browser_login.py`（新增）
- `backend/app/modules/xianyu/service.py`
- `backend/app/modules/xianyu/schemas.py`
- `backend/app/modules/xianyu/__init__.py`
- `backend/app/api/v1/xianyu.py`
- `backend/requirements.txt`（新增 Playwright 依赖）

### 前端
- `web-vue/src/api/modules/xianyu.ts`
- `web-vue/src/views/xianyu/login/index.vue`

### 测试
- `backend/tests/test_xianyu_browser_login_api.py`（新增）
- `backend/tests/test_xianyu_browser_login_manager.py`（新增）
- 视情况补充前端交互测试或最小 API/状态映射测试

## 测试策略
### 后端单元测试
覆盖：
- 启动扫码会话成功
- 同时只保留一个活跃会话
- 状态从 `waiting` 到 `success` 的映射
- 登录成功后 cookie 持久化
- 取消会话和过期清理
- 浏览器不可用时报错映射

### API 测试
覆盖：
- `start/status/cancel` 三个接口的响应结构
- `status=success` 时返回 `is_logged_in=true`
- 非法 `session_id` 返回明确错误

### 手工验证
验证路径：
1. 打开闲鱼登录页
2. 生成二维码
3. 手机扫码
4. 手机确认登录
5. 页面跳转到闲鱼工具
6. 检查 `backend/config/xianyu_cookies.json` 已写入
7. 验证闲鱼搜索/聊天接口能读到本地 cookie

## 验收标准
1. 二维码登录不再出现“生成后首次轮询即 EXPIRED”这一核心问题
2. 用户扫码后，状态能稳定经历“等待扫码 → 已扫码/已确认 → 登录成功”
3. 登录成功后，Cookie 能稳定保存到统一闲鱼 Cookie 文件
4. 项目内其他闲鱼模块无需改登录来源判断，也能继续使用本地 Cookie
5. 手动 Cookie 登录能力不受影响
6. 浏览器依赖不可用时，前端能看到清晰错误，而不是笼统显示二维码过期
