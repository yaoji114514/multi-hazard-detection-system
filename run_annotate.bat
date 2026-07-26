@echo off
chcp 65001 >nul
cd /d "%~dp0"

set STREAMLIT_LOG_LEVEL=debug

echo === PPE Annotation Tool ===
echo Starting at %date% %time%
echo Log: tools\annotate.log
echo ============================
echo.

.venv\Scripts\python.exe -m streamlit run tools\annotate.py --server.port 8504 --server.headless true --logger.level debug 2>&1

echo.
echo === Stopped at %date% %time% ===
pause
