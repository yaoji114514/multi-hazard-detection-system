@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

title Hazard Detection - Debug

echo ============================================
echo   Debug Start - diagnose run.bat crash
echo ============================================
echo.

cd /d "%~dp0"

echo [1] Working dir: %CD%
echo.

echo [2] Python:
".venv\Scripts\python.exe" --version 2>&1
if !errorlevel! neq 0 echo     python call FAILED
echo.

echo [3] streamlit.exe:
if exist ".venv\Scripts\streamlit.exe" (echo FOUND) else (echo NOT FOUND - run setup.bat first)
echo.

echo [4] Port 8501:
netstat -ano | findstr ":8501" | findstr "LISTENING" || echo FREE
echo.

echo [5] Python syntax check:
".venv\Scripts\python.exe" -m py_compile app.py src\detector.py src\database.py src\alert.py
if !errorlevel! equ 0 (echo Python syntax OK) else (echo Python syntax ERROR)
echo.

echo [6] Core dependencies:
".venv\Scripts\python.exe" -c "import streamlit, torch, ultralytics; print('OK')"
if !errorlevel! neq 0 echo     dependencies missing - run setup.bat first
echo.

echo ============================================
echo   Starting streamlit...
echo   If it fails, error will show below.
echo ============================================
echo.

".venv\Scripts\python.exe" -m streamlit run app.py
set EC=!errorlevel!

echo.
echo ============================================
echo   streamlit exited, exit code: !EC!
echo   (0 = normal, non-zero = startup failed)
echo ============================================
echo.
pause
