#!/bin/bash

set -euo pipefail

# Qingcao_Tools - 一键启动脚本

echo "========================================"
echo "  Qingcao_Tools v1.0.0"
echo "========================================"

# 获取项目根目录
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"

# 停止已有服务
echo "停止已有服务..."
lsof -ti:3121 | xargs kill -9 2>/dev/null || true
lsof -ti:3120 | xargs kill -9 2>/dev/null || true
sleep 1

# 检查 YAML 配置文件
mkdir -p "$PROJECT_ROOT/backend/app/config"
if [ ! -f "$PROJECT_ROOT/backend/app/config/config.yaml" ]; then
    echo ""
    echo "⚠️  配置文件不存在，正在创建默认配置..."
    cat > "$PROJECT_ROOT/backend/app/config/config.yaml" << 'EOF'
# Qingcao_Tools 配置文件
app:
  name: "Qingcao_Tools API"
  version: "1.0.0"
  debug: false
  api_prefix: "/api/v1"

server:
  host: "0.0.0.0"
  port: 5000

database:
  url: "sqlite+aiosqlite:///./data.db"

redis:
  url: "redis://localhost:6379/0"
  enabled: false

cookies:
  douyin: ""
  douyin_live: ""
  quark: ""

download:
  path: "./datas/media"
  excel_path: "./datas/excel"

security:
  secret_key: "please-change-this-secret-key-in-production"
  access_token_expire_minutes: 1440

request:
  timeout: 30
  max_retries: 3
EOF
    echo "✅ 配置文件已创建: backend/app/config/config.yaml"
    echo "💡 请在设置页面配置 Cookie 后使用"
fi

# 启动后端
echo ""
echo "启动后端服务..."
cd "$PROJECT_ROOT/backend"

VENV_DIR=""
if [ -d ".venv" ]; then
    VENV_DIR=".venv"
elif [ -d "venv" ]; then
    VENV_DIR="venv"
else
    echo "创建虚拟环境..."
    python3 -m venv .venv
    VENV_DIR=".venv"
fi

PYTHON_BIN="$PROJECT_ROOT/backend/$VENV_DIR/bin/python"
echo "使用虚拟环境: backend/$VENV_DIR"
if ! "$PYTHON_BIN" -c "import uvicorn" >/dev/null 2>&1; then
    echo "检测到后端依赖未安装，正在补全..."
    if ! "$PYTHON_BIN" -m pip --version >/dev/null 2>&1; then
        "$PYTHON_BIN" -m ensurepip --upgrade >/dev/null 2>&1 || true
    fi
    "$PYTHON_BIN" -m pip install -r requirements.txt -q
fi

if ! "$PYTHON_BIN" -c "import uvicorn" >/dev/null 2>&1; then
    echo "❌ 后端依赖安装不完整：当前虚拟环境缺少 uvicorn"
    echo "💡 请执行: cd backend && $PYTHON_BIN -m pip install -r requirements.txt"
    exit 1
fi

# 后台启动后端
: > /tmp/qingcao-backend.log
nohup "$PYTHON_BIN" -m uvicorn app.main:app --host 0.0.0.0 --port 3121 > /tmp/qingcao-backend.log 2>&1 &
BACKEND_PID=$!

# 启动前端
echo "启动前端服务..."
cd "$PROJECT_ROOT/web-vue"

if command -v pnpm &> /dev/null; then
    if [ ! -d "node_modules" ]; then
        echo "安装前端依赖..."
        pnpm install
    fi
    : > /tmp/qingcao-frontend.log
    nohup pnpm run dev > /tmp/qingcao-frontend.log 2>&1 &
    FRONTEND_PID=$!
elif command -v npm &> /dev/null; then
    if [ ! -d "node_modules" ]; then
        echo "安装前端依赖..."
        npm install
    fi
    : > /tmp/qingcao-frontend.log
    nohup npm run dev > /tmp/qingcao-frontend.log 2>&1 &
    FRONTEND_PID=$!
else
    echo "⚠️  未找到 npm 或 pnpm，请手动安装前端依赖"
fi

# 等待后端服务启动
BACKEND_READY=0
for _ in $(seq 1 30); do
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
        break
    fi

    if grep -q "Uvicorn running on" /tmp/qingcao-backend.log 2>/dev/null; then
        BACKEND_READY=1
        break
    fi

    if "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
import sys
from urllib.request import urlopen

try:
    with urlopen("http://127.0.0.1:3121/health", timeout=1) as resp:
        sys.exit(0 if resp.status == 200 else 1)
except Exception:
    sys.exit(1)
PY
    then
        BACKEND_READY=1
        break
    fi

    sleep 1
done

if [ "$BACKEND_READY" -ne 1 ]; then
    echo ""
    echo "❌ 后端启动失败，日志如下:"
    tail -n 40 /tmp/qingcao-backend.log 2>/dev/null || true
    exit 1
fi

echo ""
echo "========================================"
echo "  ✅ 服务启动完成"
echo "========================================"
echo ""
echo "  🌐 前端地址: http://localhost:3120"
echo "  🔧 后端API:  http://localhost:3121"
echo "  📚 API文档:  http://localhost:3121/docs"
echo "  📖 ReDoc:    http://localhost:3121/redoc"
echo ""
echo "========================================"
echo "  📝 日志文件"
echo "========================================"
echo "  后端: /tmp/qingcao-backend.log"
echo "  前端: /tmp/qingcao-frontend.log"
echo "========================================"
echo ""
echo "💡 提示: 配置文件为 backend/app/config/config.yaml"
echo "💡 提示: 首次使用请在设置页面配置 Cookie"
echo ""
echo "按 Ctrl+C 停止所有服务"

# 等待
wait
