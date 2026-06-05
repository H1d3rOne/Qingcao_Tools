#!/bin/bash

set -euo pipefail

# 青草工具箱 - 一键启动脚本

echo "========================================"
echo "  青草工具箱 v2.0.0"
echo "========================================"

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"

BACKEND_VENV_DIR=""
if [ -x "$PROJECT_ROOT/backend/.venv/bin/python" ]; then
    BACKEND_VENV_DIR=".venv"
elif [ -x "$PROJECT_ROOT/backend/venv/bin/python" ]; then
    BACKEND_VENV_DIR="venv"
fi

if [ -n "$BACKEND_VENV_DIR" ]; then
    PYTHON_BIN="$PROJECT_ROOT/backend/$BACKEND_VENV_DIR/bin/python"
    echo "使用虚拟环境: backend/$BACKEND_VENV_DIR"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
else
    echo "❌ 后端启动失败：未找到可用 Python"
    exit 1
fi

FRONTEND_PM=""
if command -v pnpm >/dev/null 2>&1; then
    FRONTEND_PM="pnpm"
elif command -v npm >/dev/null 2>&1; then
    FRONTEND_PM="npm"
else
    echo "❌ 前端启动失败：未找到 pnpm 或 npm"
    exit 1
fi

# 停止已有服务
echo "停止已有服务..."
lsof -ti:3121 | xargs kill -9 2>/dev/null || true
lsof -ti:3120 | xargs kill -9 2>/dev/null || true
sleep 1

CONFIG_DIR="$PROJECT_ROOT/backend/config"
CONFIG_EXAMPLE_DIR="$PROJECT_ROOT/backend/config.example"
LEGACY_CONFIG_DIR="$PROJECT_ROOT/backend/app/config"
mkdir -p "$CONFIG_DIR"

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
export PYTHONUTF8="${PYTHONUTF8:-1}"
export PYTHONIOENCODING="${PYTHONIOENCODING:-utf-8}"

echo ""
echo "启动后端服务..."
cd "$PROJECT_ROOT/backend"

: > /tmp/qingcao-backend.log
nohup "$PYTHON_BIN" -m uvicorn app.main:app --host 0.0.0.0 --port 3121 > /tmp/qingcao-backend.log 2>&1 &
BACKEND_PID=$!

echo "启动前端服务..."
cd "$PROJECT_ROOT/web-vue"

: > /tmp/qingcao-frontend.log
if [ "$FRONTEND_PM" = "pnpm" ]; then
    nohup pnpm run dev -- --host 0.0.0.0 --port 3120 > /tmp/qingcao-frontend.log 2>&1 &
    FRONTEND_PID=$!
else
    nohup npm run dev -- --host 0.0.0.0 --port 3120 > /tmp/qingcao-frontend.log 2>&1 &
    FRONTEND_PID=$!
fi

BACKEND_READY=0
for _ in $(seq 1 30); do
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
        break
    fi

    if grep -q "Uvicorn running on" /tmp/qingcao-backend.log 2>/dev/null; then
        BACKEND_READY=1
        break
    fi

    if "$PYTHON_BIN" - <<'INNER_PY' >/dev/null 2>&1
import sys
from urllib.request import urlopen

try:
    with urlopen("http://127.0.0.1:3121/health", timeout=1) as resp:
        sys.exit(0 if resp.status == 200 else 1)
except Exception:
    sys.exit(1)
INNER_PY
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

FRONTEND_READY=0
for _ in $(seq 1 30); do
    if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
        break
    fi

    if "$PYTHON_BIN" - <<'INNER_PY' >/dev/null 2>&1
import sys
from urllib.request import urlopen

try:
    with urlopen("http://127.0.0.1:3120/", timeout=1) as resp:
        sys.exit(0 if 200 <= resp.status < 500 else 1)
except Exception:
    sys.exit(1)
INNER_PY
    then
        FRONTEND_READY=1
        break
    fi

    sleep 1
done

if [ "$FRONTEND_READY" -ne 1 ]; then
    echo ""
    echo "❌ 前端启动失败，日志如下:"
    tail -n 40 /tmp/qingcao-frontend.log 2>/dev/null || true
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
