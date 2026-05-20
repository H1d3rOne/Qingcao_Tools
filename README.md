<div align="center">
    <a href="https://www.python.org/">
        <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+">
    </a>
    <a href="https://nodejs.org/zh-cn/">
        <img src="https://img.shields.io/badge/nodejs-18%2B-blue" alt="NodeJS 18+">
    </a>
    <a href="https://vuejs.org/">
        <img src="https://img.shields.io/badge/vue-3.4%2B-brightgreen" alt="Vue 3.4+">
    </a>
</div>

# Qingcao_Tools

**✨ 一款集成多种实用工具的工具箱应用，目前支持抖音解析、夸克网盘等功能**

**⚠️ 本项目仅供学习交流使用，请勿用于非法用途，如有违反，后果自负**

## 📁 项目结构

```
Qingcao_Tools/
├── backend/                 # 后端服务 (FastAPI)
│   ├── app/
│   │   ├── api/            # API 路由
│   │   ├── services/       # 业务逻辑
│   │   ├── schemas/        # 数据模型
│   │   ├── spiders/        # 爬虫模块
│   │   └── config.py       # 配置管理
│   ├── datas/              # 数据存储
│   ├── requirements.txt    # Python 依赖
│   └── .env                # 环境配置
├── web-vue/                # 前端项目 (Vue 3)
│   ├── src/
│   │   ├── views/          # 页面视图
│   │   │   ├── douyin/     # 抖音解析模块
│   │   │   ├── quark/      # 夸克工具模块
│   │   │   └── settings/   # 系统设置
│   │   ├── api/            # API 接口
│   │   └── stores/         # 状态管理
│   └── package.json        # 前端依赖
├── start.sh                # 一键启动脚本
└── README.md
```

## 🌟 功能特性

### 📱 抖音解析模块
- ✅ **作品查询** - 解析视频详情，获取评论，无水印下载
- ✅ **用户查询** - 查看用户信息和作品列表
- ✅ **内容搜索** - 搜索抖音视频、用户等热门内容
- ✅ **直播间** - 获取直播间信息和实时弹幕

### ☁️ 夸克工具模块
- ✅ **网盘转存** - 快速转存分享链接到网盘
- ✅ **分享管理** - 管理分享链接，设置有效期和密码
- 🚧 **离线下载** - 支持磁力链接等多种格式（开发中）

### 🎨 系统特性
- 🚀 **现代化架构** - FastAPI + Vue 3 + TypeScript
- 🌙 **优雅深色主题** - 护眼舒适的 UI 设计
- 🔒 **安全稳定** - Cookie 本地存储，数据安全可控
- 📦 **模块化设计** - 易于扩展新功能模块

## 🛠️ 快速开始

### ⛳ 运行环境
- Python 3.10+
- Node.js 18+
- pnpm（推荐）或 npm

### 🎯 安装依赖

```bash
# 后端依赖
cd backend
pip install -r requirements.txt

# 前端依赖
cd ../web-vue
pnpm install
```

### 🎨 配置文件

项目现在使用统一的本地运行态配置目录：

- `backend/config.example/`：可提交的安全模板，方便别人 clone 后初始化；
- `backend/config/`：本机私有配置与运行态数据，已被 `.gitignore` 忽略，不会提交 Cookie/API Key/设备指纹；
- `backend/app/config/`：旧版配置目录，仅作为启动时迁移兼容。

一键启动时会自动从 `backend/config.example/` 初始化缺失文件到 `backend/config/`，也可以手动执行：

```bash
cp -R backend/config.example backend/config
```

常用配置文件：

```text
backend/config/config.yaml                    # 全局 YAML 配置
backend/config/quark_cookies.json             # 夸克 Cookie
backend/config/xianyu_cookies.json            # 闲鱼 Cookie
backend/config/xianyu_ai_config.json          # 闲鱼 AI 供应商配置
backend/config/xianyu_monitor_tasks.json      # 闲鱼监控任务
backend/config/xianyu_manage_items.json       # 闲鱼商品管理缓存
backend/config/xianyu_delivery_rules.json     # 闲鱼自动发货规则
backend/config/xianyu_chat_devices.json       # 闲鱼聊天 deviceId 映射
```

> 💡 推荐启动后在设置页面配置 Cookie 和 AI 供应商。关键本地配置写入时会自动生成同名 `.bak`，例如 `xianyu_ai_config.json.bak`，防止误删或被空配置覆盖。

**Cookie 获取方式：**
1. 在浏览器中打开对应网站并登录
2. 按 F12 打开开发者工具
3. 点击网络标签，刷新页面
4. 找到任意请求，在请求头中找到 Cookie，复制完整内容

### 🚀 运行项目

**方式一：一键启动（推荐）**
```bash
chmod +x start.sh
./start.sh
```

**方式二：分别启动**
```bash
# 启动后端（终端1）
cd backend
python -m app.main

# 启动前端（终端2）
cd web-vue
pnpm run dev
```

### 🌐 访问地址
- 前端界面: http://localhost:3120
- 后端 API 文档: http://localhost:3121/docs

## 📸 效果预览

### 首页
![首页](https://via.placeholder.com/800x450?text=Qingcao_Tools%E9%A6%96%E9%A1%B5)

### 抖音解析
![抖音解析](https://via.placeholder.com/800x450?text=抖音解析模块)

### 夸克工具
![夸克工具](https://via.placeholder.com/800x450?text=夸克工具模块)

## 🍥 更新日志

| 日期 | 说明 |
| ---- | ---- |
| 25/03/12 | 重构为 Qingcao_Tools，新增夸克工具模块，优化 UI 设计 |
| 25/03/12 | 重构项目结构，新增 Vue3 前端界面，支持 Web 配置 Cookie |
| 25/06/07 | 开放所有之前闭源的代码，包括数据爬取和直播间监听 |
| 23/12/22 | 修复了直播间监控 |
| 23/11/11 | 修复了很多很多大家的 bug |

## 🧸 额外说明

1. 感谢 star⭐ 和 follow📰！不时更新
2. 有问题可以提交 Issue 或 PR
3. 如果此项目对您有帮助，欢迎支持开发者

## 📄 开源协议

本项目仅供学习交流使用，请勿用于非法用途。

---

<div align="center">
  <sub>Built with ❤️ by 青草团队</sub>
</div>
