@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo === Partner Site Image Review ===
echo Dataset: data\material_library\partner_review
echo Open: http://localhost:8504
echo =================================
echo.

call run_annotate.bat data\material_library\partner_review\images
