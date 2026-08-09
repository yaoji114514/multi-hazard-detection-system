# 多类隐患智能检测与预警系统

基于 YOLOv8、Streamlit 和 SQLite 的本地 PPE 隐患检测应用，支持图片、摄像头和视频文件检测。

## 快速开始

Windows 首次运行：

1. 双击 `setup.bat` 安装依赖。
2. 双击 `run.bat` 启动系统。
3. 浏览器访问 <http://localhost:8501>。

完整安装和使用方法见 [使用说明.md](使用说明.md)。

## 目录

```text
app.py                 Streamlit 应用入口
src/                   检测、预警、数据库、钉钉模块
models/                AI 模型权重 + active_model.txt（当前启用模型）
config/                配置（钉钉示例；本地密钥配置不入库）
tools/                 开发工具（标注/评估/训练数据/钉钉测试），legacy/ 为已弃用工具
tests/                 离线自动化回归测试（标准库 unittest）
data/                  数据目录（db、uploads、训练集、素材库等，本地不入库）
setup.bat              环境安装（自动检测 GPU，装 CUDA/CPU 版 PyTorch）
run.bat                应用启动
run_annotate.bat       标注工具启动
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

测量全工作区 Python 代码的分支覆盖率：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m coverage run -m unittest discover -s tests
.\.venv\Scripts\python.exe -m coverage report
```

## 协作

所有参与项目的对话在开始工作前读取 `AGENTS.md` 和 `PROJECT_LOG.md`，完成工作后更新共享日志。
