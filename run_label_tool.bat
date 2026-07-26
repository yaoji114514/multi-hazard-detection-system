@echo off
chcp 65001 >nul
cd /d "%~dp0.."
echo 启动PPE图片标注工具...
start "" http://localhost:8502
python -m streamlit run tools\label_tool.py --server.port 8502
pause
