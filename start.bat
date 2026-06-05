@echo off
setlocal EnableExtensions EnableDelayedExpansion

chcp 65001 >nul

echo ========================================
echo   青草工具箱 v2.0.0
echo ========================================

set "PROJECT_ROOT=%~dp0"
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"

rem 基础运行环境检查：缺少必要运行时先提示，不先杀掉已有服务。
set "HAS_BACKEND_VENV=0"
if exist "%PROJECT_ROOT%\backend\.venv\Scripts\python.exe" set "HAS_BACKEND_VENV=1"
if exist "%PROJECT_ROOT%\backend\venv\Scripts\python.exe" set "HAS_BACKEND_VENV=1"
if not "%HAS_BACKEND_VENV%"=="1" (
  call :resolve_python
  if not defined PYTHON_CMD (
    echo ❌ 未找到 Python，请先安装 Python 3.10+ 并加入 PATH
    echo 💡 Windows 可从 https://www.python.org/downloads/ 安装，或使用 winget install Python.Python.3.11
    exit /b 1
  )
)

where node >nul 2>nul
if errorlevel 1 (
  echo ❌ 未找到 Node.js，请先安装 Node.js 18+ 并加入 PATH
  echo 💡 Windows 可从 https://nodejs.org/ 安装，或使用 winget install OpenJS.NodeJS.LTS
  exit /b 1
)

where pnpm >nul 2>nul
if errorlevel 1 (
  where npm >nul 2>nul
  if errorlevel 1 (
    echo ❌ 未找到 pnpm 或 npm，请先安装 Node.js/npm，或执行: npm install -g pnpm
    exit /b 1
  )
)

echo 停止已有服务...
call :kill_port 3121
call :kill_port 3120
timeout /t 1 /nobreak >nul

set "CONFIG_DIR=%PROJECT_ROOT%\backend\config"
set "CONFIG_EXAMPLE_DIR=%PROJECT_ROOT%\backend\config.example"
set "LEGACY_CONFIG_DIR=%PROJECT_ROOT%\backend\app\config"

if not exist "%CONFIG_DIR%" mkdir "%CONFIG_DIR%"

if not exist "%CONFIG_DIR%\config.yaml" if exist "%LEGACY_CONFIG_DIR%\config.yaml" (
  copy /Y "%LEGACY_CONFIG_DIR%\config.yaml" "%CONFIG_DIR%\config.yaml" >nul
  echo ✅ 已迁移旧配置: backend\app\config\config.yaml -^> backend\config\config.yaml
)

if exist "%CONFIG_EXAMPLE_DIR%" (
  set "CREATED_CONFIG=0"
  for %%F in (
    config.yaml
    quark_cookies.json
    xianyu_ai_config.json
    xianyu_ai_sessions.json
    xianyu_chat_devices.json
    xianyu_cookies.json
    xianyu_delivery_rules.json
    xianyu_delivery_runtime.json
    xianyu_fingerprint.json
    xianyu_manage_items.json
    xianyu_monitor_tasks.json
  ) do (
    if not exist "%CONFIG_DIR%\%%F" if exist "%CONFIG_EXAMPLE_DIR%\%%F" (
      copy /Y "%CONFIG_EXAMPLE_DIR%\%%F" "%CONFIG_DIR%\%%F" >nul
      set "CREATED_CONFIG=1"
    )
  )
  if "!CREATED_CONFIG!"=="1" (
    echo ✅ 已初始化本地配置目录: backend\config\
    echo 💡 真实 Cookie/API Key 只会保存在 backend\config\，不会提交到 Git
  )
)

if not defined QINGCAO_CONFIG_DIR set "QINGCAO_CONFIG_DIR=%CONFIG_DIR%"
if not defined XIANYU_CONFIG_DIR set "XIANYU_CONFIG_DIR=%QINGCAO_CONFIG_DIR%"
if not defined QUARK_CONFIG_DIR set "QUARK_CONFIG_DIR=%QINGCAO_CONFIG_DIR%"

echo.
echo 启动后端服务...
cd /d "%PROJECT_ROOT%\backend"

set "VENV_DIR="
if exist ".venv\Scripts\python.exe" (
  set "VENV_DIR=.venv"
) else if exist "venv\Scripts\python.exe" (
  set "VENV_DIR=venv"
) else (
  call :resolve_python
  if not defined PYTHON_CMD (
    echo ❌ 未找到 Python，请先安装 Python 3.10+ 并加入 PATH
    exit /b 1
  )
  echo 创建虚拟环境...
  %PYTHON_CMD% -m venv .venv
  if errorlevel 1 (
    echo ❌ 创建虚拟环境失败
    exit /b 1
  )
  set "VENV_DIR=.venv"
)

set "PYTHON_BIN=%PROJECT_ROOT%\backend\%VENV_DIR%\Scripts\python.exe"
echo 使用虚拟环境: backend\%VENV_DIR%

"%PYTHON_BIN%" -c "import uvicorn" >nul 2>nul
if errorlevel 1 (
  echo 检测到后端依赖未安装，正在补全...
  "%PYTHON_BIN%" -m pip --version >nul 2>nul
  if errorlevel 1 (
    "%PYTHON_BIN%" -m ensurepip --upgrade >nul 2>nul
  )
  "%PYTHON_BIN%" -m pip install -r requirements.txt -q
)

"%PYTHON_BIN%" -c "import uvicorn" >nul 2>nul
if errorlevel 1 (
  echo ❌ 后端依赖安装不完整：当前虚拟环境缺少 uvicorn
  echo 💡 请执行: cd backend ^&^& "%PYTHON_BIN%" -m pip install -r requirements.txt
  exit /b 1
)

set "BACKEND_LOG=%TEMP%\qingcao-backend.log"
break > "%BACKEND_LOG%"
start "Qingcao Backend" /B cmd /c ""%PYTHON_BIN%" -m uvicorn app.main:app --host 0.0.0.0 --port 3121 ^> "%BACKEND_LOG%" 2^>^&1"

echo 启动前端服务...
cd /d "%PROJECT_ROOT%\web-vue"

set "FRONTEND_LOG=%TEMP%\qingcao-frontend.log"
break > "%FRONTEND_LOG%"

where pnpm >nul 2>nul
if not errorlevel 1 (
  echo 安装/同步前端依赖...
  pnpm install
  if errorlevel 1 (
    echo ❌ 前端依赖安装失败，请检查 pnpm 输出后重试
    exit /b 1
  )
  start "Qingcao Frontend" /B cmd /c "pnpm run dev -- --host 0.0.0.0 --port 3120 ^> "%FRONTEND_LOG%" 2^>^&1"
) else (
  where npm >nul 2>nul
  if not errorlevel 1 (
    echo 安装/同步前端依赖...
    npm install
    if errorlevel 1 (
      echo ❌ 前端依赖安装失败，请检查 npm 输出后重试
      exit /b 1
    )
    start "Qingcao Frontend" /B cmd /c "npm run dev -- --host 0.0.0.0 --port 3120 ^> "%FRONTEND_LOG%" 2^>^&1"
  ) else (
    echo ❌ 未找到 npm 或 pnpm，请先安装 Node.js/npm，或执行: npm install -g pnpm
    exit /b 1
  )
)

set "BACKEND_READY=0"
for /L %%I in (1,1,30) do (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:3121/health' -TimeoutSec 1; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>nul
  if !errorlevel! EQU 0 (
    set "BACKEND_READY=1"
    goto backend_ready
  )
  timeout /t 1 /nobreak >nul
)

:backend_ready
if not "%BACKEND_READY%"=="1" (
  echo.
  echo ❌ 后端启动失败，日志如下:
  powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Test-Path '%BACKEND_LOG%') { Get-Content -Path '%BACKEND_LOG%' -Tail 40 }"
  exit /b 1
)

echo.
echo ========================================
echo   ✅ 服务启动完成
echo ========================================
echo.
echo   🌐 前端地址: http://localhost:3120
echo   🔧 后端API:  http://localhost:3121
echo   📚 API文档:  http://localhost:3121/docs
echo   📖 ReDoc:    http://localhost:3121/redoc
echo.
echo ========================================
echo   📝 日志文件
echo ========================================
echo   后端: %BACKEND_LOG%
echo   前端: %FRONTEND_LOG%
echo ========================================
echo.
echo 💡 提示: 本地配置目录为 backend\config\
echo 💡 提示: 可提交模板目录为 backend\config.example\
echo 💡 提示: 首次使用请在设置页面配置 Cookie
echo.
echo 按 Ctrl+C 或关闭窗口停止脚本；如需清理端口，可重新运行本脚本。
pause >nul
exit /b 0

:kill_port
set "TARGET_PORT=%~1"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-NetTCPConnection -LocalPort %TARGET_PORT% -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }" >nul 2>nul
exit /b 0

:resolve_python
set "PYTHON_CMD="
where py >nul 2>nul
if not errorlevel 1 (
  set "PYTHON_CMD=py -3"
  exit /b 0
)
where python >nul 2>nul
if not errorlevel 1 (
  set "PYTHON_CMD=python"
)
exit /b 0
