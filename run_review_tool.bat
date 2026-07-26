@echo off
chcp 65001 >nul
cd /d "%~dp0.."
echo PPE标注复核工具 - 口罩专项
echo 显示自动标注结果，只需点击确认口罩状态
echo.
start "" http://localhost:8503
python -m streamlit run tools\review_tool.py --server.port 8503
pause
