@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
set PYTHONUTF8=1

title 多类隐患检测系统 - 环境安装

echo ============================================
echo   多类隐患智能检测与预警系统
echo   一键环境安装程序
echo ============================================
echo.

REM 切换到脚本所在目录(保证可移植)
cd /d "%~dp0"

REM setup.bat 仅适用于 Windows；macOS 请使用 python3 setup.py（自动识别系统）。
if /i not "%OS%"=="Windows_NT" (
    echo [错误] 此脚本仅支持 Windows。macOS 请运行: python3 setup.py
    pause
    exit /b 1
)

REM ===== 第1步: 检测 Python =====
echo [1/6] 正在检测 Python 环境...
set "PY_CMD="

python --version >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=python"
    goto :found_python
)

py -3 --version >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=py -3"
    goto :found_python
)

echo.
echo [错误] 未检测到 Python!
echo.
echo 请先安装 Python 3.9 及以上版本:
echo   1. 访问 https://www.python.org/downloads/ 下载
echo   2. 安装时务必勾选 "Add Python to PATH"
echo   3. 安装完成后重新运行本脚本
echo.
pause
exit /b 1

:found_python
for /f "tokens=2" %%v in ('!PY_CMD! --version 2^>^&1') do set "PY_VER=%%v"
echo       已找到 Python: !PY_VER!
echo.

REM ===== 第2步: 创建虚拟环境 =====
echo [2/6] 正在创建独立虚拟环境(.venv)...
if exist ".venv" (
    echo       虚拟环境已存在,跳过创建
) else (
    REM 不继承系统 site-packages，避免全局 OpenCV/PyTorch 等依赖影响项目环境
    !PY_CMD! -m venv .venv
    if !errorlevel! neq 0 (
        echo [错误] 虚拟环境创建失败
        pause
        exit /b 1
    )
    echo       虚拟环境创建成功
)
echo.

REM ===== 第3步: 配置 pip 国内源 =====
echo [3/6] 正在配置 pip 国内镜像源(南京大学源)...
set "PIP_CMD=.venv\Scripts\pip.exe"
set "PIP_INDEX=-i https://mirrors.nju.edu.cn/pypi/web/simple"

!PIP_CMD! install --upgrade pip %PIP_INDEX% >nul 2>&1
echo       pip 已就绪
echo.

REM ===== 第4步: 检测 GPU =====
echo [4/6] 正在检测 NVIDIA GPU...
set "HAS_NVIDIA=0"
nvidia-smi >nul 2>&1
if !errorlevel! equ 0 (
    set "HAS_NVIDIA=1"
    for /f "tokens=*" %%i in ('nvidia-smi --query-gpu^=name^,driver_version^,memory.total --format^=csv^,noheader 2^>nul') do set "GPU_INFO=%%i"
    echo       检测到 NVIDIA GPU: !GPU_INFO!
    echo       将优先安装 CUDA 12.8 版 PyTorch(GPU 加速)
) else (
    echo       未检测到 NVIDIA GPU,将安装 CPU 版 PyTorch
)
echo.

REM ===== 第5步: 安装 PyTorch (根据 GPU 选版本) =====
echo [5/6] 正在安装 PyTorch(首次约需 5-20 分钟,取决于网速)...
echo       请耐心等待,不要关闭窗口...
echo.

set "TORCH_READY=0"
if !HAS_NVIDIA! equ 1 (
    ".venv\Scripts\python.exe" -c "import torch, torchvision; raise SystemExit(0 if torch.cuda.is_available() else 1)" >nul 2>&1
) else (
    ".venv\Scripts\python.exe" -c "import torch, torchvision" >nul 2>&1
)
if !errorlevel! equ 0 (
    set "TORCH_READY=1"
    echo       检测到已有可用 PyTorch,跳过重复下载
    ".venv\Scripts\python.exe" -c "import torch; print('      PyTorch:', torch.__version__, '| CUDA:', torch.version.cuda, '| GPU:', torch.cuda.is_available())"
)

if !TORCH_READY! equ 0 (
    if !HAS_NVIDIA! equ 1 (
        REM GPU 版: 新显卡（如 RTX 50 系列）需要 CUDA 12.8 构建。
        echo       正在下载 CUDA 12.8 版 torch + torchvision...
        !PIP_CMD! install torch torchvision --index-url https://download.pytorch.org/whl/cu128
        if !errorlevel! neq 0 (
            echo.
            echo [警告] CUDA 12.8 版下载失败,尝试 CUDA 12.4 版...
            !PIP_CMD! install torch torchvision --index-url https://download.pytorch.org/whl/cu124
            if !errorlevel! neq 0 (
                echo [警告] CUDA 版安装失败,回退到 CPU 版
                !PIP_CMD! install torch torchvision %PIP_INDEX%
                if !errorlevel! equ 0 (
                    set HAS_NVIDIA=0
                    echo       已回退到 CPU 版,后续按 CPU 模式提示
                )
            )
        )
    ) else (
        REM CPU 版: 从南京大学源安装
        echo       正在下载 CPU 版 torch + torchvision...
        !PIP_CMD! install torch torchvision %PIP_INDEX%
    )
)
if !errorlevel! neq 0 (
    echo [错误] PyTorch 安装失败,请检查网络连接
    pause
    exit /b 1
)
echo       PyTorch 安装完成!
echo.

REM ===== 第5.5步: 安装其他依赖 =====
echo       正在安装其他依赖(ultralytics, FastAPI, OpenCV 等)...
!PIP_CMD! install -r requirements.txt %PIP_INDEX%
if !errorlevel! neq 0 (
    echo.
    echo [警告] 部分依赖安装失败,尝试使用默认源重试...
    !PIP_CMD! install -r requirements.txt
    if !errorlevel! neq 0 (
        echo [错误] 依赖安装失败,请检查网络连接
        echo.
        echo 可尝试手动安装:
        echo   1. 进入本目录
        echo   2. 运行: .venv\Scripts\pip install -r requirements.txt
        pause
        exit /b 1
    )
)

echo.
echo       依赖安装完成!
echo.

REM ===== 第6步: 初始化目录 =====
echo [6/6] 正在初始化数据目录...
if not exist "data\uploads" mkdir "data\uploads"
if not exist "data\db" mkdir "data\db"
echo       目录初始化完成
echo.

REM ===== 完成 =====
echo ============================================
echo   安装完成!
echo ============================================
echo.
if !HAS_NVIDIA! equ 1 (
    echo   运行模式: GPU 加速(NVIDIA CUDA)
    echo   检测速度: 单张图片约 0.1-0.5 秒,实时约 25-60 帧/秒
) else (
    echo   运行模式: CPU 推理
    echo   检测速度: 单张图片约 2-5 秒,实时约 5-15 帧/秒
)
echo.
echo   现在可以双击 run.bat 启动系统
echo   或直接关闭本窗口
echo.
pause
