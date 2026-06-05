@echo off
setlocal EnableExtensions EnableDelayedExpansion

echo ========================================
echo   Qingcao Toolbox v2.0.0
echo ========================================

set "PROJECT_ROOT=%~dp0"
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"

set "PYTHON_CMD="
set "PYTHON_BIN="
set "VENV_DIR="
if exist "%PROJECT_ROOT%\backend\.venv\Scripts\python.exe" (
  set "VENV_DIR=.venv"
  set "PYTHON_BIN=%PROJECT_ROOT%\backend\.venv\Scripts\python.exe"
)
if not defined PYTHON_BIN if exist "%PROJECT_ROOT%\backend\venv\Scripts\python.exe" (
  set "VENV_DIR=venv"
  set "PYTHON_BIN=%PROJECT_ROOT%\backend\venv\Scripts\python.exe"
)
if not defined PYTHON_BIN if not defined PYTHON_CMD (
  where py >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=py -3"
)
if not defined PYTHON_BIN if not defined PYTHON_CMD (
  where python >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=python"
)
if not defined PYTHON_BIN if not defined PYTHON_CMD (
  echo Backend failed to start: Python not found.
  exit /b 1
)

set "FRONTEND_PM="
where pnpm >nul 2>nul
if not errorlevel 1 (
  set "FRONTEND_PM=pnpm"
) else (
  where npm >nul 2>nul
  if not errorlevel 1 set "FRONTEND_PM=npm"
)
if not defined FRONTEND_PM (
  echo Frontend failed to start: pnpm or npm not found.
  exit /b 1
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
  echo [OK] Migrated legacy config: backend\app\config\config.yaml -^> backend\config\config.yaml
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
    echo [OK] Initialized local config dir: backend\config\
    echo [TIP] Real Cookie/API Key files are stored in backend\config\ and ignored by Git.
  )
)

if not defined QINGCAO_CONFIG_DIR set "QINGCAO_CONFIG_DIR=%CONFIG_DIR%"
if not defined XIANYU_CONFIG_DIR set "XIANYU_CONFIG_DIR=%QINGCAO_CONFIG_DIR%"
if not defined QUARK_CONFIG_DIR set "QUARK_CONFIG_DIR=%QINGCAO_CONFIG_DIR%"
if not defined PYTHONUTF8 set "PYTHONUTF8=1"
if not defined PYTHONIOENCODING set "PYTHONIOENCODING=utf-8"

echo.
echo Starting backend service...
cd /d "%PROJECT_ROOT%\backend"
if defined VENV_DIR echo Using virtual environment: backend\%VENV_DIR%

set "BACKEND_LOG=%TEMP%\qingcao-backend.log"
break > "%BACKEND_LOG%"
if defined PYTHON_BIN (
  start "Qingcao Backend" /B cmd /c call "%PYTHON_BIN%" -m uvicorn app.main:app --host 0.0.0.0 --port 3121 ^> "%BACKEND_LOG%" 2^>^&1
) else (
  start "Qingcao Backend" /B cmd /c %PYTHON_CMD% -m uvicorn app.main:app --host 0.0.0.0 --port 3121 ^> "%BACKEND_LOG%" 2^>^&1
)

echo Starting frontend service...
cd /d "%PROJECT_ROOT%\web-vue"

set "FRONTEND_LOG=%TEMP%\qingcao-frontend.log"
break > "%FRONTEND_LOG%"
if "%FRONTEND_PM%"=="pnpm" (
  start "Qingcao Frontend" /B cmd /c pnpm run dev -- --host 0.0.0.0 --port 3120 ^> "%FRONTEND_LOG%" 2^>^&1
) else (
  start "Qingcao Frontend" /B cmd /c npm run dev -- --host 0.0.0.0 --port 3120 ^> "%FRONTEND_LOG%" 2^>^&1
)

call :wait_url "http://127.0.0.1:3121/health"
if errorlevel 1 (
  echo.
  echo Backend failed to start. Recent backend log:
  powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Test-Path '%BACKEND_LOG%') { Get-Content -Encoding UTF8 -Path '%BACKEND_LOG%' -Tail 40 }"
  exit /b 1
)

call :wait_url "http://127.0.0.1:3120/"
if errorlevel 1 (
  echo.
  echo Frontend failed to start. Recent frontend log:
  powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Test-Path '%FRONTEND_LOG%') { Get-Content -Encoding UTF8 -Path '%FRONTEND_LOG%' -Tail 40 }"
  exit /b 1
)

echo.
echo ========================================
echo Services started
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
echo ========================================
echo   Backend:  %BACKEND_LOG%
echo   Frontend: %FRONTEND_LOG%
echo ========================================
echo.
echo Runtime config dir: backend\config\
echo Template config dir: backend\config.example\
echo Configure Cookie/API Key in the Settings page before first use.
echo.
echo Press Ctrl+C or close this window to stop the script.
pause >nul
exit /b 0

:wait_url
set "TARGET_URL=%~1"
for /L %%I in (1,1,30) do (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-WebRequest -UseBasicParsing -Uri '%TARGET_URL%' -TimeoutSec 1; if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>nul
  if !errorlevel! EQU 0 exit /b 0
  timeout /t 1 /nobreak >nul
)
exit /b 1

:kill_port
set "TARGET_PORT=%~1"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-NetTCPConnection -LocalPort %TARGET_PORT% -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }" >nul 2>nul
exit /b 0
