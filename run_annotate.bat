@echo off
chcp 65001 >nul
cd /d "%~dp0"

if "%~1"=="" (
    set IMGDIR=evaluation\datasets\ppe\images\val
) else (
    set IMGDIR=%1
)

echo === YOLO Annotation Tool ===
echo Images: %IMGDIR%
echo Open: http://localhost:8504
echo ====================================
echo.

.venv\Scripts\python.exe tools\annotate_server.py %IMGDIR% --port 8504

echo.
echo === Stopped at %date% %time% ===
pause
