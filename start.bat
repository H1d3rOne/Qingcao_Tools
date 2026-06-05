@echo off
setlocal EnableExtensions EnableDelayedExpansion

echo ========================================
echo   Qingcao Toolbox v2.0.0
echo ========================================

set "PROJECT_ROOT=%~dp0"
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"

call :resolve_python

set "VENV_DIR="
if exist "%PROJECT_ROOT%\backend\.venv\Scripts\python.exe" set "VENV_DIR=.venv"
if not defined VENV_DIR if exist "%PROJECT_ROOT%\backend\venv\Scripts\python.exe" set "VENV_DIR=venv"

if not defined VENV_DIR (
  echo.
  echo Backend environment is not ready.
  echo Run these commands first:
  echo.
  if defined PYTHON_CMD (
    echo   cd "%PROJECT_ROOT%\backend"
    echo   !PYTHON_CMD! -m venv .venv
    echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
  ) else (
    echo   Install Python 3.10+ first:
    echo   https://www.python.org/downloads/
    echo.
    echo   Or run:
    echo   winget install Python.Python.3.11
  )
  echo.
  echo Then run start.bat again.
  exit /b 1
)

where node >nul 2>nul
if errorlevel 1 (
  echo.
  echo Node.js 18+ is required.
  echo Install Node.js first:
  echo   https://nodejs.org/
  echo.
  echo Or run:
  echo   winget install OpenJS.NodeJS.LTS
  echo.
  echo Then run start.bat again.
  exit /b 1
)

where pnpm >nul 2>nul
if errorlevel 1 (
  where npm >nul 2>nul
  if errorlevel 1 (
    echo.
    echo pnpm or npm is required.
    echo Install Node.js/npm first, or run:
    echo   npm install -g pnpm
    echo.
    echo Then run start.bat again.
    exit /b 1
  )
)

echo Stopping existing services...
call :kill_port 3121
call :kill_port 3120
timeout /t 1 /nobreak >nul

set "CONFIG_DIR=%PROJECT_ROOT%\backend\config"
set "CONFIG_EXAMPLE_DIR=%PROJECT_ROOT%\backend\config.example"
set "LEGACY_CONFIG_DIR=%PROJECT_ROOT%\backend\app\config"

if not exist "%CONFIG_DIR%" mkdir "%CONFIG_DIR%"

if not exist "%CONFIG_DIR%\config.yaml" if exist "%LEGACY_CONFIG_DIR%\config.yaml" (
  copy /Y "%LEGACY_CONFIG_DIR%\config.yaml" "%CONFIG_DIR%\config.yaml" >nul
  echo Migrated legacy config: backend\app\config\config.yaml -^> backend\config\config.yaml
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
    echo Initialized local config dir: backend\config\
    echo Real Cookie/API Key files are stored in backend\config\ and ignored by Git.
  )
)

if not defined QINGCAO_CONFIG_DIR set "QINGCAO_CONFIG_DIR=%CONFIG_DIR%"
if not defined XIANYU_CONFIG_DIR set "XIANYU_CONFIG_DIR=%QINGCAO_CONFIG_DIR%"
if not defined QUARK_CONFIG_DIR set "QUARK_CONFIG_DIR=%QINGCAO_CONFIG_DIR%"

echo.
echo Starting backend service...
cd /d "%PROJECT_ROOT%\backend"

set "PYTHON_BIN=%PROJECT_ROOT%\backend\%VENV_DIR%\Scripts\python.exe"
echo Using virtual environment: backend\%VENV_DIR%

if not exist "%PYTHON_BIN%" (
  echo.
  echo Backend virtual environment is incomplete.
  echo Recreate it with:
  echo.
  echo   cd "%PROJECT_ROOT%\backend"
  if defined PYTHON_CMD (
    echo   !PYTHON_CMD! -m venv .venv
  ) else (
    echo   py -3 -m venv .venv
  )
  echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
  echo.
  echo Then run start.bat again.
  exit /b 1
)

"%PYTHON_BIN%" -m pip --version >nul 2>nul
if errorlevel 1 (
  echo.
  echo pip is missing in the backend virtual environment.
  echo Run these commands:
  echo.
  echo   cd "%PROJECT_ROOT%\backend"
  echo   "%PYTHON_BIN%" -m ensurepip --upgrade
  echo   "%PYTHON_BIN%" -m pip install -r requirements.txt
  echo.
  echo Then run start.bat again.
  exit /b 1
)

set "BACKEND_CHECK_RESULT="
for /f "usebackq delims=" %%M in (`"%PYTHON_BIN%" -c "import importlib.util; modules='fastapi starlette uvicorn pydantic pydantic_settings multipart sqlalchemy aiosqlite requests urllib3 httpx httpcore h11 certifi websockets websocket aiofiles yaml openpyxl bs4 lxml google.protobuf execjs qrcode retry tenacity playwright mitmproxy cryptography loguru rich typer tqdm pytest pytest_asyncio'.split(); missing=[m for m in modules if importlib.util.find_spec(m) is None]; print('OK' if not missing else ', '.join(missing))"`) do set "BACKEND_CHECK_RESULT=%%M"
if /I not "!BACKEND_CHECK_RESULT!"=="OK" (
  echo.
  echo Backend dependencies are not ready.
  if not "!BACKEND_CHECK_RESULT!"=="" (
    echo Missing modules: !BACKEND_CHECK_RESULT!
  )
  echo.
  echo Run this command:
  echo.
  echo   cd "%PROJECT_ROOT%\backend"
  echo   "%PYTHON_BIN%" -m pip install -r requirements.txt
  echo.
  echo Then run start.bat again.
  exit /b 1
)

set "FRONTEND_PM="
where pnpm >nul 2>nul
if not errorlevel 1 (
  set "FRONTEND_PM=pnpm"
) else (
  where npm >nul 2>nul
  if not errorlevel 1 (
    set "FRONTEND_PM=npm"
  )
)

if not defined FRONTEND_PM (
  echo.
  echo pnpm or npm is required.
  echo Install Node.js/npm first, or run:
  echo   npm install -g pnpm
  echo.
  echo Then run start.bat again.
  exit /b 1
)

if not exist "%PROJECT_ROOT%\web-vue\node_modules\.bin\vite.cmd" if not exist "%PROJECT_ROOT%\web-vue\node_modules\.bin\vite" (
  echo.
  echo Frontend dependencies are not ready.
  echo Run these commands:
  echo.
  echo   cd "%PROJECT_ROOT%\web-vue"
  echo   !FRONTEND_PM! install
  echo.
  echo Then run start.bat again.
  exit /b 1
)

set "BACKEND_LOG=%TEMP%\qingcao-backend.log"
break > "%BACKEND_LOG%"
start "Qingcao Backend" /B cmd /c ""%PYTHON_BIN%" -m uvicorn app.main:app --host 0.0.0.0 --port 3121 ^> "%BACKEND_LOG%" 2^>^&1"

echo Starting frontend service...
cd /d "%PROJECT_ROOT%\web-vue"

set "FRONTEND_LOG=%TEMP%\qingcao-frontend.log"
break > "%FRONTEND_LOG%"
if "%FRONTEND_PM%"=="pnpm" (
  start "Qingcao Frontend" /B cmd /c "pnpm run dev -- --host 0.0.0.0 --port 3120 ^> "%FRONTEND_LOG%" 2^>^&1"
) else (
  start "Qingcao Frontend" /B cmd /c "npm run dev -- --host 0.0.0.0 --port 3120 ^> "%FRONTEND_LOG%" 2^>^&1"
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
  echo Backend failed to start. Recent backend log:
  powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Test-Path '%BACKEND_LOG%') { Get-Content -Path '%BACKEND_LOG%' -Tail 40 }"
  exit /b 1
)

echo.
echo ========================================
echo   Services started
echo ========================================
echo.
echo   Frontend: http://localhost:3120
echo   Backend:  http://localhost:3121
echo   API docs: http://localhost:3121/docs
echo   ReDoc:    http://localhost:3121/redoc
echo.
echo ========================================
echo   Log files
echo ========================================
echo   Backend:  %BACKEND_LOG%
echo   Frontend: %FRONTEND_LOG%
echo ========================================
echo.
echo Runtime config dir: backend\config\
echo Template config dir: backend\config.example\
echo Configure Cookie/API Key in the Settings page before first use.
echo.
echo Press Ctrl+C or close this window to stop the script. Re-run this script to clean ports if needed.
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
