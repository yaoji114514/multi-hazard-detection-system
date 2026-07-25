@echo off
chcp 65001 >nul
echo [1/2] 正在下载 Python 3.11.9...
powershell -Command "$ProgressPreference = 'SilentlyContinue'; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile '%TEMP%\python-3.11.9-amd64.exe'"
if %errorlevel% neq 0 (
    echo 下载失败
    exit /b 1
)
echo 下载完成

echo [2/2] 正在静默安装 Python...
%TEMP%\python-3.11.9-amd64.exe /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
if %errorlevel% neq 0 (
    echo 安装失败
    exit /b 1
)
echo Python 安装完成
exit /b 0
