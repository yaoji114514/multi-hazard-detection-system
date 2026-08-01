@echo off
chcp 65001 >nul
setlocal
title 多类隐患检测系统 - 运行中

echo ============================================
echo   多类隐患智能检测与预警系统
echo   正在启动，请稍候...
echo ============================================
echo.

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" goto system_python

".venv\Scripts\python.exe" -c "import streamlit, torch, ultralytics" >nul 2>&1
if errorlevel 1 goto venv_error

if /i "%~1"=="--check" (
    ".venv\Scripts\python.exe" -c "import streamlit, torch, ultralytics; print('[OK] Python environment is ready')"
    exit /b 0
)

powershell.exe -NoProfile -Command "try { $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 'http://localhost:8501/_stcore/health'; if ($r.StatusCode -eq 200) { exit 0 } } catch {}; exit 1" >nul 2>&1
if not errorlevel 1 goto already_running

".venv\Scripts\python.exe" src\configure_streamlit.py
if errorlevel 1 goto config_error


call :open_browser
".venv\Scripts\python.exe" -m streamlit run app.py --server.headless true
goto stopped

:system_python
python --version >nul 2>&1
if errorlevel 1 goto python_error

python -c "import streamlit, torch, ultralytics" >nul 2>&1
if errorlevel 1 goto environment_error

if /i "%~1"=="--check" (
    python -c "import streamlit, torch, ultralytics; print('[OK] Python environment is ready')"
    exit /b 0
)

powershell.exe -NoProfile -Command "try { $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 'http://localhost:8501/_stcore/health'; if ($r.StatusCode -eq 200) { exit 0 } } catch {}; exit 1" >nul 2>&1
if not errorlevel 1 goto already_running

python src\configure_streamlit.py
if errorlevel 1 goto config_error


call :open_browser
python -m streamlit run app.py --server.headless true
goto stopped

:venv_error
echo [错误] 虚拟环境不完整，请先双击 setup.bat 完成依赖安装。
goto failed

:python_error
echo [错误] 未检测到 Python。
goto failed

:environment_error
echo [错误] 未找到完整运行环境，请先双击 setup.bat。
goto failed

:config_error
echo [错误] Streamlit 配置失败。
goto failed

:already_running
echo [信息] 系统已经在运行，正在打开页面...
call :open_browser
exit /b 0

:failed
echo.
pause
exit /b 1

:stopped
echo.
echo 服务已停止
pause

:open_browser
if exist "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" (
    start "" "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --app=http://localhost:8501
    goto :eof
)
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --app=http://localhost:8501
    goto :eof
)
start "" http://localhost:8501
goto :eof
