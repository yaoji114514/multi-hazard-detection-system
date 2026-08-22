@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0"
call "%~dp0run_v3.bat" %*
exit /b %errorlevel%
