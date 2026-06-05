#!/bin/bash

set -euo pipefail

# 青草工具箱 - 一键启动脚本

echo "========================================"
echo "  青草工具箱 v2.0.0"
echo "========================================"

# 获取项目根目录
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"

# 基础运行环境检查：缺少必要运行时先提示，不先杀掉已有服务。
HAS_BACKEND_VENV=0
if [ -x "$PROJECT_ROOT/backend/.venv/bin/python" ] || [ -x "$PROJECT_ROOT/backend/venv/bin/python" ]; then
    HAS_BACKEND_VENV=1
fi

if [ "$HAS_BACKEND_VENV" -ne 1 ] && ! command -v python3 >/dev/null 2>&1; then
    echo "❌ 未找到 Python 3，请先安装 Python 3.10+ 并加入 PATH"
    echo "💡 macOS 可执行: brew install python"
    exit 1
fi

if ! command -v node >/dev/null 2>&1; then
    echo "❌ 未找到 Node.js，请先安装 Node.js 18+ 并加入 PATH"
    echo "💡 macOS 可执行: brew install node"
    exit 1
fi

if ! command -v pnpm >/dev/null 2>&1 && ! command -v npm >/dev/null 2>&1; then
    echo "❌ 未找到 pnpm 或 npm，请先安装 Node.js/npm，或执行: npm install -g pnpm"
    exit 1
fi

# 停止已有服务
echo "停止已有服务..."
lsof -ti:3121 | xargs kill -9 2>/dev/null || true
lsof -ti:3120 | xargs kill -9 2>/dev/null || true
sleep 1

# 检查统一运行态配置目录
CONFIG_DIR="$PROJECT_ROOT/backend/config"
CONFIG_EXAMPLE_DIR="$PROJECT_ROOT/backend/config.example"
LEGACY_CONFIG_DIR="$PROJECT_ROOT/backend/app/config"
mkdir -p "$CONFIG_DIR"

# 兼容旧版本：如果 backend/app/config/config.yaml 已存在，优先复制到新的统一目录。
if [ ! -f "$CONFIG_DIR/config.yaml" ] && [ -f "$LEGACY_CONFIG_DIR/config.yaml" ]; then
    cp "$LEGACY_CONFIG_DIR/config.yaml" "$CONFIG_DIR/config.yaml"
    echo "✅ 已迁移旧配置: backend/app/config/config.yaml -> backend/config/config.yaml"
fi

if [ -d "$CONFIG_EXAMPLE_DIR" ]; then
    CREATED_CONFIG=0
    for file in \
        config.yaml \
        quark_cookies.json \
        xianyu_ai_config.json \
        xianyu_ai_sessions.json \
        xianyu_chat_devices.json \
        xianyu_cookies.json \
        xianyu_delivery_rules.json \
        xianyu_delivery_runtime.json \
        xianyu_fingerprint.json \
        xianyu_manage_items.json \
        xianyu_monitor_tasks.json
    do
        if [ ! -f "$CONFIG_DIR/$file" ] && [ -f "$CONFIG_EXAMPLE_DIR/$file" ]; then
            cp "$CONFIG_EXAMPLE_DIR/$file" "$CONFIG_DIR/$file"
            CREATED_CONFIG=1
        fi
    done
    if [ "$CREATED_CONFIG" -eq 1 ]; then
        echo "✅ 已初始化本地配置目录: backend/config/"
        echo "💡 真实 Cookie/API Key 只会保存在 backend/config/，不会提交到 Git"
    fi
fi

export QINGCAO_CONFIG_DIR="${QINGCAO_CONFIG_DIR:-$CONFIG_DIR}"
export XIANYU_CONFIG_DIR="${XIANYU_CONFIG_DIR:-$QINGCAO_CONFIG_DIR}"
export QUARK_CONFIG_DIR="${QUARK_CONFIG_DIR:-$QINGCAO_CONFIG_DIR}"

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
    echo "安装/同步前端依赖..."
    pnpm install
    : > /tmp/qingcao-frontend.log
    nohup pnpm run dev > /tmp/qingcao-frontend.log 2>&1 &
    FRONTEND_PID=$!
elif command -v npm &> /dev/null; then
    echo "安装/同步前端依赖..."
    npm install
    : > /tmp/qingcao-frontend.log
    nohup npm run dev > /tmp/qingcao-frontend.log 2>&1 &
    FRONTEND_PID=$!
else
    echo "❌ 未找到 npm 或 pnpm，请先安装 Node.js/npm，或执行: npm install -g pnpm"
    exit 1
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
echo "💡 提示: 本地配置目录为 backend/config/"
echo "💡 提示: 可提交模板目录为 backend/config.example/"
echo "💡 提示: 首次使用请在设置页面配置 Cookie"
echo ""
echo "按 Ctrl+C 停止所有服务"

# 等待
wait
