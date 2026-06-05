@echo off
setlocal EnableExtensions EnableDelayedExpansion

echo ========================================
call :say 6Z2S6I2J5bel5YW3566xIHYyLjAuMA==
echo ========================================

set "PROJECT_ROOT=%~dp0"
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"

call :resolve_python

set "VENV_DIR="
if exist "%PROJECT_ROOT%\backend\.venv\Scripts\python.exe" set "VENV_DIR=.venv"
if not defined VENV_DIR if exist "%PROJECT_ROOT%\backend\venv\Scripts\python.exe" set "VENV_DIR=venv"

if not defined VENV_DIR (
  echo.
  call :say 5ZCO56uv5L6d6LWW5rKh5pyJ5a6J6KOF77yM6K+35L2/55SoIHBpcCBpbnN0YWxsIC1yIHJlcXVpcmVtZW50cy50eHQg5a6J6KOF5L6d6LWW44CC
  echo.
  if defined PYTHON_CMD (
    echo   cd "%PROJECT_ROOT%\backend"
    echo   !PYTHON_CMD! -m venv .venv
    echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
  ) else (
    call :say 6K+35YWI5a6J6KOFIFB5dGhvbiAzLjEwK++8mg==
    echo   https://www.python.org/downloads/
    echo.
    call :say 5Lmf5Y+v5Lul5omn6KGM77ya
    echo   winget install Python.Python.3.11
  )
  echo.
  call :say 5a6J6KOF5a6M5oiQ5ZCO6YeN5paw6L+Q6KGMIHN0YXJ0LmJhdOOAgg==
  exit /b 1
)

where node >nul 2>nul
if errorlevel 1 (
  echo.
  call :say 5pyq5qOA5rWL5YiwIE5vZGUuanMgMTgr77yM6K+35YWI5a6J6KOFIE5vZGUuanPjgII=
  call :say Tm9kZS5qcyDlronoo4XlnLDlnYDvvJo=
  echo   https://nodejs.org/
  echo.
  call :say 5Lmf5Y+v5Lul5omn6KGM77ya
  echo   winget install OpenJS.NodeJS.LTS
  echo.
  call :say 5a6J6KOF5a6M5oiQ5ZCO6YeN5paw6L+Q6KGMIHN0YXJ0LmJhdOOAgg==
  exit /b 1
)

where pnpm >nul 2>nul
if errorlevel 1 (
  where npm >nul 2>nul
  if errorlevel 1 (
    echo.
    call :say 5pyq5qOA5rWL5YiwIHBucG0g5oiWIG5wbeOAgg==
    call :say 6K+35YWI5a6J6KOFIE5vZGUuanMvbnBt77yM5oiW5omn6KGM77ya
    echo   npm install -g pnpm
    echo.
    call :say 5a6J6KOF5a6M5oiQ5ZCO6YeN5paw6L+Q6KGMIHN0YXJ0LmJhdOOAgg==
    exit /b 1
  )
)

call :say 5YGc5q2i5bey5pyJ5pyN5YqhLi4u
call :kill_port 3121
call :kill_port 3120
timeout /t 1 /nobreak >nul

set "CONFIG_DIR=%PROJECT_ROOT%\backend\config"
set "CONFIG_EXAMPLE_DIR=%PROJECT_ROOT%\backend\config.example"
set "LEGACY_CONFIG_DIR=%PROJECT_ROOT%\backend\app\config"

if not exist "%CONFIG_DIR%" mkdir "%CONFIG_DIR%"

if not exist "%CONFIG_DIR%\config.yaml" if exist "%LEGACY_CONFIG_DIR%\config.yaml" (
  copy /Y "%LEGACY_CONFIG_DIR%\config.yaml" "%CONFIG_DIR%\config.yaml" >nul
  call :say 5bey6L+B56e75pen6YWN572u77yaYmFja2VuZFxhcHBcY29uZmlnXGNvbmZpZy55YW1sIC0+IGJhY2tlbmRcY29uZmlnXGNvbmZpZy55YW1s
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
    call :say 5bey5Yid5aeL5YyW5pys5Zyw6YWN572u55uu5b2V77yaYmFja2VuZFxjb25maWdc
    call :say 55yf5a6eIENvb2tpZS9BUEkgS2V5IOWPquS8muS/neWtmOWcqCBiYWNrZW5kXGNvbmZpZ1zvvIzkuI3kvJrmj5DkuqTliLAgR2l044CC
  )
)

if not defined QINGCAO_CONFIG_DIR set "QINGCAO_CONFIG_DIR=%CONFIG_DIR%"
if not defined XIANYU_CONFIG_DIR set "XIANYU_CONFIG_DIR=%QINGCAO_CONFIG_DIR%"
if not defined QUARK_CONFIG_DIR set "QUARK_CONFIG_DIR=%QINGCAO_CONFIG_DIR%"

echo.
call :say 5ZCv5Yqo5ZCO56uv5pyN5YqhLi4u
cd /d "%PROJECT_ROOT%\backend"

set "PYTHON_BIN=%PROJECT_ROOT%\backend\%VENV_DIR%\Scripts\python.exe"
echo Using virtual environment: backend\%VENV_DIR%

if not exist "%PYTHON_BIN%" (
  echo.
  call :say 5ZCO56uv5L6d6LWW5rKh5pyJ5a6J6KOF77yM6K+35L2/55SoIHBpcCBpbnN0YWxsIC1yIHJlcXVpcmVtZW50cy50eHQg5a6J6KOF5L6d6LWW44CC
  echo.
  echo   cd "%PROJECT_ROOT%\backend"
  if defined PYTHON_CMD (
    echo   !PYTHON_CMD! -m venv .venv
  ) else (
    echo   py -3 -m venv .venv
  )
  echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
  echo.
  call :say 5a6J6KOF5a6M5oiQ5ZCO6YeN5paw6L+Q6KGMIHN0YXJ0LmJhdOOAgg==
  exit /b 1
)

"%PYTHON_BIN%" -m pip --version >nul 2>nul
if errorlevel 1 (
  echo.
  call :say 5ZCO56uv5L6d6LWW5rKh5pyJ5a6J6KOF77yM6K+35L2/55SoIHBpcCBpbnN0YWxsIC1yIHJlcXVpcmVtZW50cy50eHQg5a6J6KOF5L6d6LWW44CC
  echo.
  echo   cd "%PROJECT_ROOT%\backend"
  echo   "%PYTHON_BIN%" -m ensurepip --upgrade
  echo   "%PYTHON_BIN%" -m pip install -r requirements.txt
  echo.
  call :say 5a6J6KOF5a6M5oiQ5ZCO6YeN5paw6L+Q6KGMIHN0YXJ0LmJhdOOAgg==
  exit /b 1
)

set "BACKEND_CHECK_RESULT="
for /f "usebackq delims=" %%M in (`"%PYTHON_BIN%" -c "import importlib.util; modules='fastapi starlette uvicorn pydantic pydantic_settings multipart sqlalchemy aiosqlite requests urllib3 httpx httpcore h11 certifi websockets websocket aiofiles yaml openpyxl bs4 lxml google.protobuf execjs qrcode retry tenacity playwright mitmproxy cryptography loguru rich typer tqdm pytest pytest_asyncio'.split(); missing=[m for m in modules if importlib.util.find_spec(m) is None]; print('OK' if not missing else ', '.join(missing))"`) do set "BACKEND_CHECK_RESULT=%%M"
if /I not "!BACKEND_CHECK_RESULT!"=="OK" (
  echo.
  call :say 5ZCO56uv5L6d6LWW5rKh5pyJ5a6J6KOF77yM6K+35L2/55SoIHBpcCBpbnN0YWxsIC1yIHJlcXVpcmVtZW50cy50eHQg5a6J6KOF5L6d6LWW44CC
  if not "!BACKEND_CHECK_RESULT!"=="" (
    call :say 57y65bCR5qih5Z2X77ya & echo !BACKEND_CHECK_RESULT!
  )
  echo.
  echo   cd "%PROJECT_ROOT%\backend"
  echo   "%PYTHON_BIN%" -m pip install -r requirements.txt
  echo.
  call :say 5a6J6KOF5a6M5oiQ5ZCO6YeN5paw6L+Q6KGMIHN0YXJ0LmJhdOOAgg==
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
  call :say 5pyq5qOA5rWL5YiwIHBucG0g5oiWIG5wbeOAgg==
  call :say 6K+35YWI5a6J6KOFIE5vZGUuanMvbnBt77yM5oiW5omn6KGM77ya
  echo   npm install -g pnpm
  echo.
  call :say 5a6J6KOF5a6M5oiQ5ZCO6YeN5paw6L+Q6KGMIHN0YXJ0LmJhdOOAgg==
  exit /b 1
)

if not exist "%PROJECT_ROOT%\web-vue\node_modules\.bin\vite.cmd" if not exist "%PROJECT_ROOT%\web-vue\node_modules\.bin\vite" (
  echo.
  call :say 5YmN56uv5L6d6LWW5rKh5pyJ5a6J6KOF77yM6K+35YWI5a6J6KOF5YmN56uv5L6d6LWW44CC
  call :say 6K+35omn6KGM5LiL6Z2i5ZG95Luk77ya
  echo.
  echo   cd "%PROJECT_ROOT%\web-vue"
  echo   !FRONTEND_PM! install
  echo.
  call :say 5a6J6KOF5a6M5oiQ5ZCO6YeN5paw6L+Q6KGMIHN0YXJ0LmJhdOOAgg==
  exit /b 1
)

set "BACKEND_LOG=%TEMP%\qingcao-backend.log"
break > "%BACKEND_LOG%"
start "Qingcao Backend" /B cmd /c ""%PYTHON_BIN%" -m uvicorn app.main:app --host 0.0.0.0 --port 3121 ^> "%BACKEND_LOG%" 2^>^&1"

call :say 5ZCv5Yqo5YmN56uv5pyN5YqhLi4u
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
  call :say 5ZCO56uv5ZCv5Yqo5aSx6LSl77yM5pyA6L+R5pel5b+X5aaC5LiL77ya
  powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Test-Path '%BACKEND_LOG%') { Get-Content -Path '%BACKEND_LOG%' -Tail 40 }"
  exit /b 1
)

echo.
echo ========================================
call :say 5pyN5Yqh5ZCv5Yqo5a6M5oiQ
echo ========================================
echo.
echo   Frontend: http://localhost:3120
echo   Backend:  http://localhost:3121
echo   API docs: http://localhost:3121/docs
echo   ReDoc:    http://localhost:3121/redoc
echo.
echo ========================================
call :say 5pel5b+X5paH5Lu2
echo ========================================
echo   Backend:  %BACKEND_LOG%
echo   Frontend: %FRONTEND_LOG%
echo ========================================
echo.
call :say 5pys5Zyw6YWN572u55uu5b2V77yaYmFja2VuZFxjb25maWdc
call :say 6YWN572u5qih5p2/55uu5b2V77yaYmFja2VuZFxjb25maWcuZXhhbXBsZVw=
call :say 6aaW5qyh5L2/55So6K+35Zyo6K6+572u6aG16Z2i6YWN572uIENvb2tpZS9BUEkgS2V544CC
echo.
call :say 5oyJIEN0cmwrQyDmiJblhbPpl63nqpflj6PlgZzmraLohJrmnKzvvJvlpoLpnIDmuIXnkIbnq6/lj6PvvIzlj6/ph43mlrDov5DooYwgc3RhcnQuYmF044CC
pause >nul
exit /b 0


:say
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Console]::OutputEncoding=[Text.Encoding]::UTF8; Write-Host ([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('%~1')))"
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
