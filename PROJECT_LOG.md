# 项目共享日志

本文件是所有项目对话共用的工作记录。开始任务前先阅读，完成改动后按 `AGENTS.md` 的格式在顶部追加记录。

## 2026-07-26 21:00 - 修正 _send_realtime_violations 调用缩进

- 任务：另一个对话在"修复通知调用位置"时将调用补回,但缩进仍在 `if to_record:` 块外(12 dots,与 if 同级),同样会触发 UnboundLocalError。
- 改动：将 `_send_realtime_violations(rt_stats, proj, insp)` 从 12 dots 改为 16 dots,使其正确位于 `if to_record:` 块内,与 `proj`/`insp` 赋值同级。同时清理日志中空标题行和重复孤儿条目。
- 验证：Python 编译通过；缩进已确认在 16 dots；`proj`/`insp` 引用在作用域内。
- 遗留：需重启服务后用摄像头实测验证钉钉通知链路；`_send_realtime_violations` 函数定义在第 196 行可后续清理。
## 2026-07-26 20:29 - 补记图片检测钉钉通知接入

- 任务：上传图片检测发现红色/黄色预警后，自动向钉钉发送汇总通知。
- 改动：app.py 新增 dingtalk 导入兜底；新增 _send_image_alert()；在 db.save_record() 成功后调用，通过 st.session_state 防重复。
- 验证：Python 编译通过；通知失败不阻断检测；配置缺失不中断启动。
- 遗留：后续可增加 Markdown 格式和图片发送。

## 2026-07-26 20:29 - 修复实时检测通知调用位置

- 任务：另一对话修复 proj UnboundLocalError 后 _send_realtime_violations 调用点丢失。
- 改动：将调用从 if to_record: 块外移入块内。
- 验证：编译通过；proj/insp 在作用域内。
- 遗留：需重启服务后用摄像头实测。


## 2026-07-26 20:14 - 接入实时摄像头检测钉钉通知

- 任务：让实时摄像头检测在发现违规后，以 60 秒节流向钉钉发送汇总预警。
- 改动：新增 DINGTALK_REALTIME_COOLDOWN 常量；新增 _send_realtime_violations() 通知函数；在 rt_stats 新增通知状态字段并接入重置链路；在 video_frame_callback 违规去重后累加并在入库后调用通知。
- 验证：Python 编译通过；通知函数与图片检测共用 dingtalk 模块和密钥配置；仅当 _HAS_DINGTALK 为 True 且累积有违规时才发送；60 秒节流避免手机轰炸。
- 遗留：需启动实时摄像头检测功能验证手机端实际收信效果；后续可增加预留通知间隙配置和钉钉 Markdown 消息格式。


## 2026-07-26 15:30 - 完成自动标注 + 复核工具替代纯手动标注

- 任务：避免手动从零画框，改用模型自动打标 + 快速复核的工作流。
- 改动：
  - 新建 tools/auto_label.py — 用现有 models/best.pt 对 51 张新图自动打标（YOLO 格式）
  - 新建 tools/review_tool.py — Streamlit 复核工具，只需点选"有口罩/无口罩"，无需画框
  - 新建 run_review_tool.bat — 一键启动复核工具（端口 8503）
- 验证：
  - 自动标注完成 51 张图，产生 282 个目标标注（Hardhat 49、Safety Vest 31、Person 112、machinery 34 等）
  - Mask 类检测为 0（模型未学过口罩），因此需通过复核工具人工标注口罩
  - 复核工具逻辑：复核时点选"有口罩"自动添加 Mask(class 1)标注；点选"无口罩"自动添加 NO-Mask(class 3)标注
- 遗留：
  - 运行 run_review_tool.bat 逐张复核口罩状态（51 张图，每张点一下即可）
  - 复核全部完成后，可运行 tools/evaluate_model.py 验证精度提升
  - 若仍嫌复核麻烦，可用 Ultralytics Hub 寻找专用口罩检测模型直接替换自动标注结果

## 2026-07-26 15:00 - 完成工地工人PPE素材收集与标注入口搭建

- 任务：搜索并下载 50 张工地工人同时佩戴安全帽+反光衣+口罩的图片，以提高模型对口罩检测的精度；建立人工标注流程。
- 改动：
  - 新建 data/material_library/new_candidates/raw/ 存放 51 张下载图片（42 张高清）
  - 新建 data/material_library/new_candidates/annotated/ 标注目录（含 data.yaml 匹配模型 10 类）
  - 新建 data/material_library/new_candidates/inventory.json 素材清单
  - 新建 tools/label_tool.py 基于 Streamlit 的 YOLO 格式标注工具
  - 新建 run_label_tool.bat 一键启动标注工具（端口 8502）
- 验证：
  - Roboflow 已有 1,613 张带标注图片，但 mask 类仅 1 张（train 集 1 实例）→ 确认必须补充口罩图片
  - bing-image-downloader 成功从 Bing 搜索下载 51 张工地 PPE 图片
  - label_tool.py 语法检查通过
- 遗留：
  - 51 张新图片尚无标注，需人工运行 run_label_tool.bat（或 streamlit run tools/label_tool.py --server.port 8502）逐张标注
  - 标注全部完成后，可将 annotated/ 数据加入 evaluation/datasets/ppe/ 进行模型验证
  - 后续可继续搜索更多 mask+helmet+vest 同框图（当前边际收益递减，51 张+现有 1,613 张已够）

## 2026-07-25 21:56 - 验证钉钉机器人实机发送

- 任务：使用用户本机填写的 Webhook 和加签密钥验证钉钉手机通知链路。
- 改动：未改业务代码；执行独立测试脚本发送一条“隐患预警 - 通信测试”消息。
- 验证：钉钉接口返回成功并接受消息，Webhook、加签和电脑出网链路均有效；本地密钥未输出且继续受 Git 忽略保护。
- 遗留：等待用户确认手机端实际收到消息；确认后再接入图片检测预警。

## 2026-07-25 21:53 - 建立钉钉通知测试链路

- 任务：为电脑端检测服务向手机发送预警建立独立的钉钉机器人通信入口。
- 改动：新增 `src/dingtalk.py` 实现机器人加签、配置校验和文本发送；新增 `tools/test_dingtalk.py` 测试命令及无密钥示例配置；创建被 Git 忽略的本地配置 `config/dingtalk.local.json`，并更新 `.gitignore` 防止密钥入库。
- 验证：Python 语法编译通过；固定时间戳加签 URL 构造通过；空配置按预期在联网前拒绝发送；本地配置已确认被 Git 忽略；`git diff --check` 通过。
- 遗留：需要用户在本地配置中填写 Webhook 和 `SEC` 加签密钥并完成手机实机发送；当前尚未接入图片或实时检测业务。

## 2026-07-25 19:45 - 建立模型精度验证基线

- 任务：为识别精度提升建立固定、可重复、可量化的验证入口。
- 改动：新增 `tools/evaluate_model.py`，检查 YOLO 图片与标注完整性并输出总体及逐类别 Precision、Recall、F1、mAP50、mAP50-95；新增 `evaluation/` 数据集结构、当前模型 10 类配置和标注评估说明；更新 `.gitignore` 排除本地验证图片、标签、缓存和评估产物。
- 验证：脚本语法检查通过；数据集类别顺序与 `models/best.pt` 完全一致；空验证集保护按预期拒绝评估；使用临时图片和标注完成一次 CPU 端到端 `model.val()`，成功生成 `metrics.json` 和 Ultralytics 图表，随后已清理临时数据及产物；`git diff --check` 通过。
- 遗留：尚需收集并人工标注约 50-200 张真实现场图片，才能产出可信的当前模型基线指标并开始对比优化。

## 2026-07-25 19:21 - 补记运行环境与启动链路修复

- 任务：复用电脑已有 Torch/CUDA 环境，修复 Windows 双击启动，并处理 Streamlit 图片参数弃用警告。
- 改动：让 `.venv` 继承系统 site-packages；更新 `setup.bat`、`run.bat`、`run_debug.bat`、`verify_install.py`、`requirements.txt` 和 `使用说明.md`，统一普通 PyPI 依赖使用南京大学源并保留 PyTorch 官方 CUDA 索引；修复批处理 CRLF 和中文路径解析，增加环境自检、重复启动检测及桌面启动脚本；将 `app.py` 的三处 `use_column_width=True` 替换为 `width="stretch"`。
- 验证：虚拟环境成功复用 Python 3.12.8、Torch 2.13.0+cu132 和 RTX 5060；`pip check`、Python 编译、`run.bat --check` 均通过；YOLO 模型在 GPU 上完成示例图推理；Streamlit 健康接口返回 `200 ok`。
- 遗留：`download_torch_gpu.py` 及使用说明中的部分手工恢复命令仍面向 Python 3.13/cu124，后续做全新机器安装验证时需统一；桌面启动脚本位于项目仓库外，不受 Git 跟踪。

## 2026-07-25 19:20 - 归档历史运行文件

- 任务：将散落在项目运行目录中的历史文件集中保存。
- 改动：把历史数据库、上传结果、违规截图、Python 缓存和项目内 `%temp%` 移至本地 `archive/20260725-历史运行文件/`，保留原相对结构；在 `.gitignore` 中排除整个 `archive/`。
- 验证：归档共包含 65 个文件，约 7.25 MB；数据库模块能在原位置重建全新空库，Git 仅显示 `.gitignore` 和本日志改动。
- 遗留：归档仅存在于当前工作区，不纳入 Git；需要历史数据时可从归档目录手动恢复。

## 2026-07-25 19:10 - 建立仓库协作基线

- 任务：将现有可移植包整理为适合持续开发和多对话协作的源码仓库。
- 改动：新增 `README.md`、`AGENTS.md` 和本日志；完善 `.gitignore`，排除虚拟环境、运行数据、缓存、日志和临时目录。
- 验证：扫描项目结构；Python 源码编译通过；`verify_install.py` 全部通过，YOLO 模型成功加载并完成示例图片检测，CUDA 可用。
- 遗留：本地安全策略禁止删除文件，因此已忽略的历史运行数据库、上传结果、缓存和 `%temp%` 目录仍留在工作区磁盘，但不会进入 Git。
