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
src/                   检测、预警、数据库模块
models/best.pt         PPE 检测模型
data/sample_images/    示例图片
data/sample_videos/    示例视频
data/alert.wav         告警音频
setup.bat              环境安装
run.bat                应用启动
verify_install.py      安装与模型验证
PROJECT_LOG.md         跨对话共享工作日志
```

`data/db/`、`data/uploads/`、`.venv/` 和缓存目录均为本地生成内容，不纳入版本控制。

## 验证

```powershell
.\.venv\Scripts\python.exe verify_install.py
```

## 协作

所有参与项目的对话在开始工作前读取 `AGENTS.md` 和 `PROJECT_LOG.md`，完成工作后更新共享日志。
