<div align="center">
  <img src="./web-vue/public/qingcao-logo.svg" width="96" alt="青草工具箱 Logo" />

  # 青草工具箱

  <p>一个基于 <strong>FastAPI + Vue 3 + TypeScript</strong> 的多功能工具箱，集成抖音解析、夸克网盘、视频号助手、闲鱼工具、消息推送与统一配置管理。</p>

  <p>
    <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white" alt="Python 3.10+" />
    <img src="https://img.shields.io/badge/Node.js-18%2B-339933?logo=node.js&logoColor=white" alt="Node.js 18+" />
    <img src="https://img.shields.io/badge/Vue-3.4%2B-4FC08D?logo=vue.js&logoColor=white" alt="Vue 3.4+" />
    <img src="https://img.shields.io/badge/FastAPI-0.110%2B-009688?logo=fastapi&logoColor=white" alt="FastAPI" />
    <img src="https://img.shields.io/badge/Element%20Plus-2.6%2B-409EFF" alt="Element Plus" />
  </p>
</div>

> ⚠️ 本项目仅供学习交流与个人工具化使用。请遵守相关平台服务条款与法律法规，不要用于非法用途或侵犯他人权益。

## 目录

- [功能概览](#功能概览)
- [技术栈](#技术栈)
- [项目结构](#项目结构)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [功能模块说明](#功能模块说明)
- [常用开发命令](#常用开发命令)
- [接口与访问地址](#接口与访问地址)
- [常见问题](#常见问题)
- [许可证](#许可证)

## 功能概览

| 模块 | 功能 |
| ---- | ---- |
| 抖音解析 | 作品解析、评论获取、无水印下载、用户主页、作品列表、综合/视频/用户/直播搜索、直播间信息与弹幕 WebSocket |
| 夸克工具 | 扫码/自动登录、网盘文件列表、上传下载、新建文件夹、重命名、移动、删除、分享管理、分享链接转存/下载 |
| 视频号助手 | 监听视频号资源、视频记录管理、下载任务、下载目录选择、预览与打开目录、监听端口配置、证书检测/安装 |
| 闲鱼工具 | 登录/扫码登录、商品搜索、详情查看、监控任务、命中商品、聊天会话、AI 自动回复、商品管理、自动发货、订单管理 |
| 消息推送 | 企业微信、钉钉、飞书 Webhook 配置与测试 |
| 系统设置 | Cookie 配置、运行状态、统计数据、统一运行态配置初始化与备份 |

## 技术栈

### 后端

- FastAPI / Uvicorn
- Pydantic v2
- SQLAlchemy Async + SQLite
- httpx / requests / websockets
- Playwright（闲鱼浏览器扫码登录等场景）
- mitmproxy、websocket-client、BeautifulSoup、lxml 等辅助依赖
- pytest / pytest-asyncio

### 前端

- Vue 3 + TypeScript
- Vite
- Element Plus
- Pinia + pinia-plugin-persistedstate
- Vue Router
- Tailwind CSS / Sass
- Vitest / Vue Test Utils

## 项目结构

```text
青草工具箱/
├── backend/                         # FastAPI 后端
│   ├── app/
│   │   ├── api/v1/                  # API 路由聚合
│   │   ├── core/                    # 配置、日志、中间件、异常处理
│   │   ├── db/                      # 数据库连接与仓储
│   │   ├── models/                  # 数据模型
│   │   ├── modules/                 # 业务模块
│   │   │   ├── douyin/              # 抖音解析/搜索/直播
│   │   │   ├── quark/               # 夸克网盘
│   │   │   ├── settings/            # 设置与 Cookie 存储
│   │   │   ├── wechat/              # 视频号助手
│   │   │   └── xianyu/              # 闲鱼工具、聊天、AI、监控、发货
│   │   └── utils/                   # 通用工具
│   ├── config.example/              # 可提交的安全配置模板
│   ├── config/                      # 本机运行态配置，已被 gitignore 忽略
│   ├── tests/                       # 后端测试
│   └── requirements.txt             # Python 依赖
├── web-vue/                         # Vue 前端
│   ├── public/                      # favicon / Logo 等静态资源
│   ├── src/
│   │   ├── api/                     # 前端 API 封装
│   │   ├── assets/                  # 样式与资源
│   │   ├── components/              # 公共/业务组件
│   │   ├── layouts/                 # 页面布局
│   │   ├── router/                  # 路由
│   │   ├── stores/                  # Pinia 状态
│   │   └── views/                   # 页面视图
│   ├── package.json
│   └── vite.config.ts
├── docs/                            # 设计/实现计划文档
├── start.sh                         # 一键启动脚本
└── README.md
```

## 快速开始

### 环境要求

- Python 3.10+（推荐 3.11）
- Node.js 18+
- pnpm（推荐）或 npm
- macOS / Linux / Windows WSL 均可运行；涉及浏览器自动化、目录打开等功能时，桌面环境体验更完整

### 方式一：一键启动（推荐）

```bash
chmod +x start.sh
./start.sh
```

`start.sh` 会自动完成：

1. 显示当前版本号；
2. 停止已有的 `3120` / `3121` 端口服务；
3. 初始化 `backend/config/` 运行态配置；
4. 兼容迁移旧目录 `backend/app/config/config.yaml`；
5. 从 `backend/config.example/` 补齐缺失的本地配置模板；
6. 自动设置 `QINGCAO_CONFIG_DIR`、`XIANYU_CONFIG_DIR`、`QUARK_CONFIG_DIR`；
7. 创建或复用后端虚拟环境 `.venv` / `venv`；
8. 检测并补全后端依赖；
9. 启动后端 `http://localhost:3121`，并通过日志/健康检查确认服务可用；
10. 使用 `pnpm` 或 `npm` 安装前端依赖并启动前端 `http://localhost:3120`；
11. 输出前端、后端、Swagger、ReDoc 地址以及日志文件路径。

启动日志默认写入：

```text
/tmp/qingcao-backend.log
/tmp/qingcao-frontend.log
```

如果后端启动失败，脚本会直接打印最近的后端日志，便于定位依赖、端口或配置问题。

### 方式二：手动启动

后端：

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 3121 --reload
```

前端：

```bash
cd web-vue
pnpm install
pnpm run dev
```

如果需要使用 Playwright 相关能力：

```bash
cd backend
.venv/bin/python -m playwright install chromium
```

## 配置说明

项目使用统一的本地运行态配置目录，方便 clone 后初始化，也避免真实 Cookie、API Key、设备指纹等敏感数据误提交。

| 路径 | 说明 |
| ---- | ---- |
| `backend/config.example/` | 可提交的安全模板，不包含真实账号信息 |
| `backend/config/` | 本机私有运行态配置，已被 `.gitignore` 忽略 |
| `backend/app/config/` | 旧版配置目录，仅用于迁移兼容 |

首次启动时会自动从 `backend/config.example/` 初始化缺失文件到 `backend/config/`。也可以手动复制：

```bash
cp -R backend/config.example backend/config
```

常用配置文件：

```text
backend/config/config.yaml                    # 全局 YAML 配置
backend/config/quark_cookies.json             # 夸克 Cookie
backend/config/xianyu_cookies.json            # 闲鱼 Cookie
backend/config/xianyu_fingerprint.json        # 闲鱼指纹信息
backend/config/xianyu_chat_devices.json       # 闲鱼聊天 deviceId 映射
backend/config/xianyu_ai_config.json          # 闲鱼 AI 供应商配置
backend/config/xianyu_ai_sessions.json        # 闲鱼会话 AI 开关状态
backend/config/xianyu_monitor_tasks.json      # 闲鱼监控任务
backend/config/xianyu_manage_items.json       # 闲鱼商品管理缓存
backend/config/xianyu_delivery_rules.json     # 闲鱼自动发货规则
backend/config/xianyu_delivery_runtime.json   # 闲鱼自动发货运行态
```

关键配置写入时会维护同名 `.bak`，例如：

```text
backend/config/xianyu_ai_config.json.bak
backend/config/xianyu_monitor_tasks.json.bak
```

如果配置意外丢失，可以优先检查同目录 `.bak` 文件。

### 环境变量

| 环境变量 | 说明 |
| -------- | ---- |
| `QINGCAO_CONFIG_DIR` | 覆盖统一运行态配置目录 |
| `QINGCAO_CONFIG_EXAMPLE_DIR` | 覆盖配置模板目录 |
| `XIANYU_CONFIG_DIR` | 覆盖闲鱼模块配置目录，默认跟随 `QINGCAO_CONFIG_DIR` |
| `QUARK_CONFIG_DIR` | 覆盖夸克模块配置目录，默认跟随 `QINGCAO_CONFIG_DIR` |

### Cookie 配置建议

推荐在前端“系统设置”或对应模块登录页配置 Cookie / 登录状态。手动获取 Cookie 的通用方式：

1. 浏览器打开对应平台并登录；
2. 按 `F12` 打开开发者工具；
3. 切换到 Network/网络面板并刷新页面；
4. 找到任意已登录请求，在 Request Headers 中复制完整 `Cookie`；
5. 粘贴到系统设置对应字段。

## 功能模块说明

### 抖音解析

前端路由：`/douyin`

后端接口前缀：`/api/v1/douyin`

主要能力：

- 视频作品解析与详情查询；
- 评论获取；
- 无水印视频/图集下载；
- 用户信息与作品列表；
- 综合搜索、视频搜索、用户搜索、直播搜索；
- 搜索分页、动态签名参数与风控提示兼容；
- 直播间信息解析、弹幕 WebSocket、直播缓存管理。

### 夸克工具

前端路由：`/quark`

后端接口前缀：`/api/v1/quark`

主要能力：

- 扫码登录、自动登录、登录状态检查、退出登录；
- 文件列表、目录树、存储空间信息；
- 新建文件夹、重命名、移动、删除；
- 文件上传、本地文件上传、原始上传；
- 文件/文件夹下载；
- 分享创建、分享列表、分享删除；
- 分享链接信息解析、转存、下载。

### 视频号助手

前端路由：`/wechat`

后端接口前缀：`/api/v1/wechat`

主要能力：

- 启动/停止/查看视频号监听状态；
- 捕获视频记录并维护列表；
- 下载目录选择；
- 创建、重试、取消、删除下载任务；
- 预览下载文件、打开下载目录。
- 配置 `local_server` 与 `mitm proxy` 端口；
- 检测并安装 mitm 证书，安装失败时提供手动安装指引；
- 默认端口：后端 API `3121`、mitm proxy `8090`、local_server `3122`。

### 闲鱼工具

前端路由：`/xianyu`

后端接口前缀：`/api/v1/xianyu`

主要能力：

- 登录状态管理、Cookie 登录、二维码登录、浏览器二维码登录；
- 商品搜索、商品详情、用户资料；
- 监控任务：关键词/价格/筛选条件、手动运行、启停、命中商品预览；
- 聊天会话：会话列表、消息列表、发送文本/图片、撤回、标记已读、清除红点、WebSocket 实时消息、共享连接保活；
- AI 助手：全局开关、会话级开关、供应商管理、模型选择、API Key 掩码读取、连通性测试、保活间隔、收到消息后标记已读再自动回复；
- 商品管理：同步在售商品、分页同步、全量同步、编辑商品、删除缓存、擦亮商品、多数量自动发货开关；
- 自动发货：规则管理、启停规则、运行状态、执行记录；
- 订单管理：订单筛选、订单搜索、虚拟商品免物流发货。

### 消息推送

前端路由：`/notify`

后端接口前缀：`/api/v1/notify`

支持：

- 企业微信 Webhook；
- 钉钉 Webhook；
- 飞书 Webhook；
- 配置读取、保存与测试发送。

### 系统设置

前端路由：`/settings`

后端接口前缀：`/api/v1/settings`

支持：

- 服务状态查看；
- 抖音/直播/夸克/闲鱼 Cookie 保存；
- 闲鱼完整 Cookie 读取；
- 统计数据读取。

## 常用开发命令

### 后端

```bash
cd backend

# 安装依赖
.venv/bin/python -m pip install -r requirements.txt

# 启动开发服务
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 3121 --reload

# 运行全部后端测试
.venv/bin/python -m pytest

# 运行指定测试
.venv/bin/python -m pytest tests/test_config_bootstrap.py -q

# Python 语法检查
.venv/bin/python -m py_compile app/main.py app/core/config.py app/core/config_bootstrap.py
```

### 前端

```bash
cd web-vue

# 安装依赖
pnpm install

# 启动开发服务
pnpm run dev

# TypeScript 类型检查 + Vite 生产构建
pnpm run build

# 仅验证生产产物生成
pnpm exec vite build

# 单元测试
pnpm run test

# ESLint 自动修复
pnpm run lint
```

> 说明：`package.json` 中的 `pnpm run build` 会先执行 `vue-tsc` 再执行 Vite 构建；如果只想快速验证产物生成，可使用 `pnpm exec vite build`。

## 接口与访问地址

| 服务 | 地址 |
| ---- | ---- |
| 前端开发服务 | <http://localhost:3120> |
| 后端服务 | <http://localhost:3121> |
| Swagger 文档 | <http://localhost:3121/docs> |
| ReDoc 文档 | <http://localhost:3121/redoc> |
| 健康检查 | <http://localhost:3121/health> |

默认 API 前缀：

```text
/api/v1
```

常见后端路由：

```text
/api/v1/douyin/work/*
/api/v1/douyin/user/*
/api/v1/douyin/search/*
/api/v1/douyin/live/*
/api/v1/quark/*
/api/v1/wechat/*
/api/v1/xianyu/*
/api/v1/notify/*
/api/v1/settings/*
```

## 常见问题

### 1. 后端启动失败，提示缺少依赖

```bash
cd backend
.venv/bin/python -m pip install -r requirements.txt
```

如果虚拟环境损坏，可以删除后重建：

```bash
rm -rf backend/.venv
./start.sh
```

### 2. 前端无法访问后端

确认后端运行在 `3121`，前端 Vite 代理会将 `/api` 转发到：

```text
http://localhost:3121
```

### 3. 配置或 AI 供应商“不见了”

优先检查：

```text
backend/config/xianyu_ai_config.json
backend/config/xianyu_ai_config.json.bak
backend/config/config.yaml
```

确认没有把 `QINGCAO_CONFIG_DIR` / `XIANYU_CONFIG_DIR` 指到其他目录。

### 4. Cookie 鉴权失败

- 重新登录平台后更新 Cookie；
- 闲鱼建议优先使用模块内登录/浏览器二维码登录能力；
- 避免频繁切换账号或短时间高频请求；
- 若提示风控或登录失效，等待一段时间后重新登录并更新配置；
- 闲鱼聊天链路命中风控后会暂停自动轮询/重复建连，避免持续触发 `login.token`。

### 5. Playwright 相关功能不可用

安装浏览器依赖：

```bash
cd backend
.venv/bin/python -m playwright install chromium
```

## 版本与变更

当前版本：`v2.0.0`

近期主要变更：

- 品牌升级为“青草工具箱”，新增青草主题 Logo 与页面标题；
- 新增统一运行态配置目录 `backend/config/` 与模板目录 `backend/config.example/`；
- 为关键本地配置加入 `.bak` 防丢失机制；
- 闲鱼工具接入聊天、AI 自动回复、监控任务、商品管理、自动发货与订单管理；
- 闲鱼聊天增加共享 WebSocket、保活、会话切换兼容与风控熔断；
- 视频号助手新增 `local_server` / mitm 端口配置、证书检测与安装指引；
- 抖音综合/视频/用户/直播搜索链路与分页兼容持续优化；
- 前端通过 `vue-tsc + vite build` 全量构建校验；
- 抖音首页/直播页与闲鱼监控/管理等页面持续优化 UI 展示。

## 许可证

本项目采用 GNU Affero General Public License v3.0（AGPL-3.0）许可证，详见 [`LICENSE`](./LICENSE)。

如果你修改本项目并通过网络向用户提供服务，需要按照 AGPL-3.0 的要求向这些用户提供对应源码。

## 说明

本项目仍在持续迭代中，部分平台接口、Cookie、风控策略可能随平台变化而失效。建议优先使用页面内提供的登录、设置和测试功能，并定期更新依赖与配置。

---

<div align="center">
  <sub>Built with ❤️ by H1d3rOne</sub>
</div>
