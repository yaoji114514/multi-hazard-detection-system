# 多类隐患智能检测与预警系统

基于 YOLOv8、React、FastAPI 和 SQLite 的本地 PPE 隐患检测应用，支持图片、摄像头、视频文件检测与隐患闭环处置。前端构建产物随项目分发，目标电脑运行时不需要 Node.js。

## 快速开始

### Windows

1. 双击 `setup.bat` 安装依赖。
2. 双击 `run.bat` 启动系统。
3. 浏览器访问 <http://localhost:8501>。

### macOS

1. 安装 Python 3.9 或更高版本（Apple Silicon 建议使用原生 arm64 Python 3.11/3.12）。
2. 在终端进入项目目录后运行 `python3 setup.py`；安装入口会自动识别 macOS 并创建 `.venv`、安装依赖。
3. 运行 `bash run_macos.sh`，再访问 <http://localhost:8501>。

Apple Silicon 会自动优先使用 MPS；不支持 MPS 的 Mac 会回退到 CPU。

完整安装和使用方法见 [使用说明.md](使用说明.md)。

## 目录

```text
frontend/              V3 React 前端源码与预构建 dist
src/web_api.py         V3 本地 FastAPI 入口
app.py                 经典 Streamlit 回滚界面
src/                   检测、预警、数据库、钉钉与本地 API 模块
models/                AI 模型权重 + active_model.txt（当前启用模型）
config/                配置（钉钉示例；本地密钥配置不入库）
tools/                 开发工具（标注/评估/训练数据/钉钉测试），legacy/ 为已弃用工具
tests/                 离线自动化回归测试（标准库 unittest）
data/                  数据目录（db、uploads、训练集、素材库等，本地不入库）
setup.bat              环境安装（自动检测 GPU，装 CUDA/CPU 版 PyTorch）
run.bat                V3 默认启动
run_v3.bat             V3 Windows 启动与环境检查
run_legacy.bat         经典 Streamlit 回滚入口
run_annotate.bat       标注工具启动
setup.py               跨平台安装入口（自动识别 Windows/macOS）
setup_macos.sh         macOS 环境安装
run_macos.sh           V3 macOS 应用启动
run_legacy_macos.sh    经典 Streamlit macOS 回滚入口
run_annotate_macos.sh  macOS 标注工具启动
使用说明.md             完整安装、使用与钉钉配置说明
迁移说明.md             跨电脑迁移说明
AGENTS.md              多对话协作规则
PROJECT_LOG.md         跨对话共享工作日志
```

`data/db/`、`data/uploads/`、`data/training_dataset/`、`data/training_v4clean/`、`data/partner_field_test/`、`runs/`、`archive/`、`.venv/` 和缓存目录均为本地内容，不纳入版本控制。

## 验证

```powershell
.\.venv\Scripts\python.exe verify_install.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

macOS：

```bash
.venv/bin/python verify_install.py
.venv/bin/python -m unittest discover -s tests -v
```

测量全工作区 Python 代码的分支覆盖率：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m coverage run -m unittest discover -s tests
.\.venv\Scripts\python.exe -m coverage report
```

## 协作

所有参与项目的对话在开始工作前读取 `AGENTS.md` 和 `PROJECT_LOG.md`，完成工作后更新共享日志。
