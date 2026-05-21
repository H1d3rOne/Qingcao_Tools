# 青草工具箱 - 前端项目

基于 Vue 3 + TypeScript + Element Plus 的现代化前端应用。

## 技术栈

- **框架**: Vue 3.4 + TypeScript 5
- **构建工具**: Vite 5
- **UI 组件库**: Element Plus 2.6
- **状态管理**: Pinia 2
- **路由**: Vue Router 4
- **样式**: Tailwind CSS 3
- **HTTP**: Axios

## 快速开始

### 1. 安装依赖

```bash
cd web-vue
npm install
```

### 2. 启动开发服务器

```bash
npm run dev
```

访问 http://localhost:3120

### 3. 构建生产版本

```bash
npm run build
```

## 项目结构

```
web-vue/
├── src/
│   ├── api/          # API 接口
│   ├── assets/       # 静态资源
│   ├── components/   # 组件
│   │   ├── common/   # 公共组件
│   │   └── business/ # 业务组件
│   ├── composables/  # 组合式函数
│   ├── layouts/      # 布局组件
│   ├── router/       # 路由配置
│   ├── stores/       # 状态管理
│   ├── types/        # 类型定义
│   ├── utils/        # 工具函数
│   └── views/        # 页面视图
├── public/           # 公共资源
└── index.html        # 入口 HTML
```

## 功能模块

| 模块 | 路由 | 说明 |
|------|------|------|
| 首页 | `/` | 推荐视频展示 |
| 作品 | `/video` | 作品查询和详情 |
| 用户 | `/user` | 用户查询和主页 |
| 搜索 | `/search` | 视频/用户搜索 |
| 直播 | `/live` | 直播间查询 |

## 开发命令

```bash
# 开发
npm run dev

# 构建
npm run build

# 预览构建结果
npm run preview

# 代码检查
npm run lint

# 代码格式化
npm run format
```

## 环境变量

| 变量 | 说明 |
|------|------|
| `VITE_API_BASE_URL` | API 基础路径 |
| `VITE_APP_TITLE` | 应用标题 |

## 后端服务

前端需要配合后端 API 服务使用：

```bash
# 在项目根目录运行
python3 web_server.py
```

后端服务默认运行在 http://localhost:3121
