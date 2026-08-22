@echo off
chcp 65001 >nul
setlocal
title 现场安全签派台 - V3

cd /d "%~dp0"

set "PYTHON_CMD="
if exist ".venv\Scripts\python.exe" set "PYTHON_CMD=.venv\Scripts\python.exe"
if not defined PYTHON_CMD (
    python --version >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD goto python_error

%PYTHON_CMD% -c "import fastapi, uvicorn, torch, ultralytics" >nul 2>&1
if errorlevel 1 goto environment_error

if not exist "frontend\dist\index.html" goto frontend_error

if /i "%~1"=="--check" (
    %PYTHON_CMD% -c "import fastapi, uvicorn, torch, ultralytics; print('[OK] V3 local API environment is ready')"
    exit /b 0
)

powershell.exe -NoProfile -Command "try { $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 'http://127.0.0.1:8501/api/health'; if ($r.StatusCode -eq 200) { exit 0 } } catch {}; exit 1" >nul 2>&1
if not errorlevel 1 goto already_running

call :open_browser
%PYTHON_CMD% -m uvicorn src.web_api:app --host 127.0.0.1 --port 8501
goto stopped

:python_error
echo [错误] 未检测到 Python，请先运行 setup.bat。
goto failed

:environment_error
echo [错误] V3 运行环境不完整，请重新运行 setup.bat 安装依赖。
goto failed

:frontend_error
echo [错误] 未找到 frontend\dist\index.html。
echo 请在开发电脑运行 npm --prefix frontend run build，或使用包含前端构建产物的正式包。
goto failed

:already_running
echo [信息] V3 已经在运行，正在打开页面...
call :open_browser
exit /b 0

:failed
echo.
pause
exit /b 1

:stopped
echo.
echo V3 服务已停止
pause
exit /b 0

:open_browser
if exist "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" (
    start "" "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --app=http://127.0.0.1:8501
    goto :eof
)
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --app=http://127.0.0.1:8501
    goto :eof
)
start "" http://127.0.0.1:8501
goto :eof
