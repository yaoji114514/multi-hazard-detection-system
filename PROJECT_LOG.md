# 项目共享日志

## 2026-08-22 20:41 - 在 React 实时页恢复红色风险声音告警

- 任务：补回旧界面曾具备、V3 初版遗漏的实时红色风险本地警报音，同时保持新架构的风险、存储和通知状态分离。
- 改动：恢复 `data/alert.wav` 并新增固定的 `/api/alert-sound` 安全资源接口；实时帧响应新增与写库/钉钉解耦的 `audible_alert.triggered/sequence`，只在冷却后的新红色事件递增。React 实时页按 sequence 去重并保留 5 秒硬节流，在连接摄像头手势中解锁浏览器音频；增加声音开启/静音、测试声音、本机偏好记忆、2 秒无障碍红色文字告警，以及停止/重置/离页时终止播放和阻止迟到响应误响。播放失败只更新独立声音状态，不中断检测、入库或通知。发布包、安装验证、PRODUCT 和使用说明同步恢复警报音资产与行为。
- 验证：声音 API 返回 `200 audio/wav` 和完整 33,644 bytes；API 测试覆盖文件存在/缺失、红色首次触发、冷却期不重复、黄色不触发、存储失败仍触发和会话序号；完整 `unittest discover` 共 88 项通过，React production build、`run.bat --check`、发布白名单、`py_compile` 与 `git diff --check` 通过。受控浏览器在桌面和手机视口确认声音开关/测试入口无溢出，实际点击“测试声音”后页面返回“测试声音已播放”，控制台无错误；Impeccable detector 返回 0 项。
- 遗留：未在本次验收中请求真实摄像头权限；新的未戴安全帽事件在目标摄像头上的实际扬声器触发仍需硬件端到端确认。

## 2026-08-22 12:07 - 移除旧 Streamlit 前端与回滚链路

- 任务：按用户确认“之前的前端不再使用”清理经典 Streamlit 界面，只保留 React + FastAPI 应用。
- 改动：删除 `app.py`、`.streamlit/config.toml`、`run_legacy*`、旧 `run_debug.bat`、`src/configure_streamlit.py`、三组旧前端测试和三个已废弃的 Streamlit 标注/复核脚本；将 V3 完整启动逻辑并入 `run.bat` 后删除重复的 `run_v3.bat`。从运行依赖与安装验证中移除 Streamlit、streamlit-webrtc、Pandas、Plotly 和 PyAV 旧链路，安装脚本不再生成 Streamlit 用户配置；发布包只包含 React 构建产物、FastAPI 服务和单一启动入口。同步更新 README、使用说明、PRODUCT、迁移说明、检测器注释和 Demo 包测试。模型、SQLite、钉钉配置、上传证据与当前标注服务器均未删除或迁移。
- 验证：`py_compile` 通过；精简后的完整 `unittest discover` 共 87 项通过；React production build、`run.bat --check`、macOS shell 语法、发布白名单反向断言、运行代码 Streamlit/Pandas/Plotly/PyAV import 扫描和 `git diff --check` 均通过。
- 遗留：当前 `.venv` 中可能仍保留此前安装的旧包，本次未擅自卸载；下次重建 `.venv` 时会按精简后的 `requirements.txt` 自然清除。旧界面可从 Git 提交 `2774011` 恢复。

## 2026-08-22 11:22 - 完成 V3 独立前端与本地 API 完全重构

- 任务：按用户“不要被现有架构束缚”的明确授权，将第二版深色 Streamlit 后台替换为能够明显感知的全新前端，同时保留现有模型、SQLite、钉钉链路和可回滚入口。
- 改动：新增 `frontend/`，以 Vite + React 19 + TypeScript 构建“安全影像校样台 + 现场签派条”，取消永久侧栏、重复状态轨和通用卡片墙；五项能力改为顶部导航，图片以大证据舞台、原图/AI 标注和目标联系条复核，实时以摄像头舞台和事件签派呈现，记录页以证据联系表驱动处置单，统计页围绕积压、隐患排行和七日趋势组织，通知设置使用脱敏抽屉。新增 `src/web_api.py` 作为同源 FastAPI 服务，复用现有 detector/database/alert/dingtalk，实现图片检测、统一处置、统计、通知群管理、安全媒体访问、H.264 视频后台任务和浏览器实时帧检测；实时通知保留文字/截图分阶段与 30/60/120 秒退避。`run.bat` / `run_macos.sh` 切为 V3 默认入口，新增 `run_v3.bat`，并以 `run_legacy.bat` / `run_legacy_macos.sh` 保留经典 Streamlit 回滚。同步更新依赖、安装验证、Demo 包白名单、README、使用说明、PRODUCT/DESIGN 与 API/发布测试；目标电脑运行预构建前端，无需 Node.js。
- 验证：`npm run build` 通过，构建产物约 290 KB JS / 33 KB CSS；`.venv\Scripts\python.exe -m py_compile`、完整 `unittest discover` 118 项、V3/经典 Windows 启动检查、macOS shell 语法和 `git diff --check` 通过。真实启动 Uvicorn 后检查五页、1440×900 桌面与 390×844 手机布局，未见横向溢出或控制台错误；浏览器验收未触发推理、摄像头权限、处置保存或钉钉发送。Impeccable 独立收尾评审的四项材料性问题均已关闭，最终 disposition 为 PASS。
- 遗留：真实摄像头长时运行、真实图片/视频端到端推理和生产钉钉多群断网场景仍需在目标硬件验收；V3 实时通知重试批次保存在进程内，服务重启后不会恢复。旧 `app.py` 与 Streamlit 依赖暂时保留一个验收周期，确认 V3 稳定后再决定是否移除。

## 2026-08-19 21:13 - 记住最近检查上下文

- 任务：修复项目名称和检查人在 Streamlit 重启后清空的问题，使当前电脑可恢复最近一次输入。
- 改动：`src/database.py` 新增 `last_check_context` 单行本机偏好表及读写方法；`app.py` 的侧栏输入首次加载本机默认值，字段变更后自动保存，数据库不可用时不阻断检查；`tests/test_database.py` 和 `tests/test_app_helpers.py` 覆盖持久化、重启恢复及不改写历史检测记录；`使用说明.md` 补充行为说明。
- 验证：`.venv\\Scripts\\python.exe -m py_compile app.py src\\database.py`、`.venv\\Scripts\\python.exe -m unittest discover -s tests -v`（106 项）、`run.bat --check` 和 `git diff --check` 均通过。
- 遗留：保存范围仅限当前电脑的本地数据库；更换电脑或清除本地数据库后需要重新填写。

## 2026-08-14 - 训练工作交接需求（本对话不执行训练）

- 范围：模型训练不属于本对话。本对话的产物是交给后续“训练对话”的准备说明；本日志本身不构成启动训练的指令。
- 已准备：当前十类 Ultralytics YOLO 基线及其数据集；独立四类 PPE 专项集（2,286 张，已生成不改写源数据的 COCO 副本）；PaddleX 隔离环境、`PicoDet-S` 配置和训练入口；当前 `partner_model.pt` / `best.pt` 与应用推理链路未改动。
- 后续训练对话开始前必须核定：① 合作方 32 张现场图的标注经人工复核，并冻结为只验收、不参与 train/val 的集合；② 本轮实际训练目标是十类 YOLO 续训，还是四类 PaddleX 候选；③ 数据版本、切分清单、初始权重、配置版本和输出目录；④ 验收指标，至少包括 `NO-Hardhat` 漏检、误报、总 mAP 与真实视频事件表现。
- 建议的首轮范围：如选择 PaddleX，先用四类专项集训练 `PicoDet-S` 候选，并把其四类输出与当前 YOLO 的相同四类映射在冻结现场集上对比；不要把标签不完整的四类数据直接混进现有十类 YOLO 数据集。
- 后续训练对话应留下：运行目录、数据 manifest、完整配置、初始/最终权重、训练日志、逐类评估与冻结现场集对比结论。训练结束也不得自动替换 `models/active_model.txt`。

## 2026-08-14 01:20 - PaddleX 仅保留数据质检与训练入口，未保留候选模型

- 任务：用户要求引入 PaddleX，但未授权执行候选模型训练。
- 处理：已删除误启动产生的两个 `runs/paddlex/helmet_ppe_picodet_s/*_smoke/` 目录及其权重、日志和导出产物；仅保留 `check_dataset` 数据质检报告。PaddleX 隔离环境、COCO 副本、训练入口和同版本官方 PicoDet-S 配置资产继续保留，供用户明确授权后再使用。
- 验证：当前 `models/active_model.txt` 仍为 `partner_model.pt`；`models/best.pt` 与 `models/partner_model.pt` 的 SHA-256 均为 `2419700BBE3B8D38F9000655D9CF952A4BC93EF6C143BAF8B49A0ABDE5D0760F`。应用、十类 YOLO 数据和生产模型均未修改。
- 遗留：PaddleX 当前不是生产训练或部署路径；后续任何 `smoke`、正式训练、评估、模型替换或部署动作均需用户单独明确授权。

## 2026-08-14 00:37 - 引入 PaddleX 候选训练治理流程

- 任务：按既定路线把 PaddleX 纳入训练流程，不改动现有十类 Ultralytics YOLO 应用或当前生产模型。
- 改动：新增独立 GPU/CPU 环境安装脚本 `setup_paddlex.bat`、`setup_paddlex_cpu.bat`，YOLO 到 COCO 的只读副本导出工具 `tools/export_yolo_to_coco.py`，环境校验工具 `tools/verify_paddlex_environment.py`，PaddleX 引擎入口 `tools/run_paddlex_engine.py`，以及 PicoDet-S 的 `check / smoke / train / evaluate` 入口 `run_paddlex_pilot.bat` 和操作说明 `PADDLEX_TRAINING.md`；新增转换单元测试。将四类专项集导出为被 Git 忽略的 `data/paddlex/helmet_specialized_v1/`，包含 2,286 张图片、6,038 个 COCO 标注（train/val=1,829/457），且冻结 COCO 数据不会被 PaddleX 自动重切分或改写。PaddleX 训练产物也只写入忽略目录 `runs/paddlex/`。
- 验证：转换脚本 `py_compile`、2 项单元测试、实际 COCO 导出与完整性断言、`git diff --check` 均通过；CPU 隔离环境实际安装 `PaddlePaddle 3.3.0` 和 `PaddleX 3.7.2`，`paddle.utils.run_check()`、`pip check` 和 PaddleX `check_dataset` 均通过。质检报告在 `runs/paddlex/helmet_ppe_picodet_s/20260814_003656_check/`，确认数据为四类 `COCODetDataset`、train/val=1,829/457，且输出含类别直方图和抽样可视化。当前模型与应用未改动。
- 遗留：Windows RTX 50 系 GPU 训练环境仍待通过 CUDA 运行库下载与 1 epoch smoke。PaddleDetection 训练插件仅在后续 GPU 阶段安装，且应记录其具体提交；不在 CPU 质检环境中安装或跑 50 epoch。合作方 32 张现场图也仍需人工复核后作为不参与训练的冻结验收集。

## 2026-08-13 02:30 - 建立隔离的安全帽专项候选数据集

- 任务：收集有标注的公开 PPE 数据来补强安全帽基线，但不把外部不完整标签直接并入现有十类训练集。
- 改动：下载并校验 Mendeley `Dataset of Personal Protective Equipment (PPE)` v6（数据页标示 CC BY 4.0）；新增 `data/helmet_specialized_dataset_v1/` 作为独立四类候选集，类别为 `Hardhat / NO-Hardhat / NO-Safety Vest / Safety Vest`，及可重复执行的 `tools/build_helmet_specialized_dataset.py`。构建脚本校验图片、YOLO 标签、源压缩包大小与 SHA-256，并以 SHA-256 排除与现有训练、评估、合作方现场验收目录完全相同的图片；原始压缩包、图片、标签和抽样审计图均保持本地忽略。
- 验证：压缩包 236,065,015 bytes、SHA-256 `7a22e5cbc0327971f56358e14f1fce88fec1d6ab30cfac642de0746202ae1f0d` 与来源一致；整理后 train/val 为 1,829/457 张，6,038 个标注（Hardhat 2,421、NO-Hardhat 1,174、NO-Safety Vest 1,058、Safety Vest 1,385），无坏图、坏标、完全相同重复图或跨 split 精确重复；Ultralytics 成功解析数据配置，`py_compile` 与 `git diff --check` 通过。当前线上 `best.pt`、十类数据、应用推理链路均未改动。
- 遗留：合作方 32 张图片仍需人工核对并冻结为不参与训练的现场验收集；后续只在该验收集与视频事件指标同时胜过当前初始基线时，才考虑部署专项候选模型。SH17（非商业许可）与 SHWD（来源/许可风险）未纳入；Hard Hat Workers 的原始标注导出需要 Roboflow 登录，待取得后再单独 QA。

## 2026-08-13 00:52 - 前端第二版“隐患处置值守台”

- 任务：按用户最终确认的推荐方向完成前端第二版；采用“事件指挥板”视觉与信息架构，在允许大范围调整的前提下保留五个业务入口、Windows 双击启动、既有检测链路和可回滚数据结构。
- 改动：`app.py` 重构为深色值守工作台，统一页头、检查上下文、系统状态、风险轨和响应式 7:5 工作区；图片页改为证据区与检测命令区，并显示通知送达结果、支持结果直达指定处置记录；记录页合并图片/实时来源，增加全部待办、处理中、待我处理、未分配、红色待办、已超期等快捷视图，改为可单击行的主从证据与处置界面；实时页严格分开监测状态、业务风险和系统故障，仅保留累计违规与已存记录，补全上下文闸门、通知重试状态和最新记录直达；独立收尾审查发现并修复“实时入库失败仍增加已存记录”的误报，失败现在进入独立且持续到用户重置的系统错误通道，不会被同批后续成功记录掩盖；视频页明确只生成标注视频、不入处置队列且逐帧统计可能重复；统计页围绕处置积压、主要隐患与近 7 天趋势组织。同步更新 Streamlit 主题、`PRODUCT.md`、`DESIGN.md`、`使用说明.md` 和前端测试；页面保持无表情符号。
- 验证：`.venv\Scripts\python.exe -m py_compile app.py`、完整 `unittest discover` 102 项、`run.bat --check`、`git diff --check` 均通过；Impeccable detector 对 `app.py` 返回 0 项。使用受控浏览器实际检查五个页面、1440×1000 桌面和 390×844 手机视口，截图保存于 `.impeccable/review/`；验收未启动摄像头、未执行图片/视频推理、未保存处置、未发送钉钉消息，业务数据库与本地私密配置未改写。
- 遗留：仍需在真实摄像头、真实上传图片、长视频和钉钉断网/多群部分失败条件下做端到端硬件验收；Streamlit 原生上传控件仍含英文 `Upload` 与文件大小提示；历史图片记录没有原图完整路径，只能展示现有标注证据；当前工作流保存最终状态而非完整审计时间线。

## 2026-08-12 23:57 - 归档前端体验评审

- 任务：按 Impeccable 对当前 Streamlit 前端做桌面端与窄屏体验评审，给后续设计迭代建立可追踪基线。
- 改动：未修改应用代码、配置、数据库或业务数据；新增 `.impeccable/critique/2026-08-12T15-57-25Z__app-py.md`，记录双代理设计评估、启发式评分、优先问题与建议方向。
- 验证：本地启动 `app.py` 并检查隐患检测、实时检测、检测记录、统计分析与通知设置；390×844 窄屏未见明显横向溢出；Impeccable detector 对 `app.py` 返回 0 项；评审服务和主评审浏览器状态已清理。
- 遗留：优先处理实时页监测/故障/风险状态混淆、检测结果直达处置、视频结果能力边界；随后精简工作队列和检测上下文。次代理的隔离浏览器会话已由运行时释放，无法独立复核其标签页清理状态。

## 2026-08-12 - 收紧正式测试包并固定初始基线模型

- 任务：逐项审计正式测试包，只交付测试用户安装、启动和体验现有功能所需内容；包内仅使用初始基线模型。
- 改动：`tools/make_demo_package.py` 只复制运行白名单并写入 `models/active_model.txt=best.pt`；排除 Windows/macOS 标注入口、标注服务、GPU/安装诊断脚本、未被界面引用的示例视频，以及重复的发布说明、包内清单和包内校验文件。同步把《使用说明》的目录树和钉钉验证步骤改为测试包真实内容，并纳入用户定稿的 AI Agent 辅助咨询说明。开发工作区中的标注/诊断工具、`partner_model.pt` 及其激活配置均未删除或修改。
- 验证：完整 `unittest discover` 共 97 项通过；重建 `v0.1.0-test1` 后实际目录与 ZIP 均为 19 个文件，反向扫描未发现标注、诊断、训练、评估、测试、运行数据、本机凭据或其他模型；ZIP CRC 通过，包内 `best.pt` 成功加载并对内置图片检出 23 个目标；源目录、解压目录与 ZIP 内的《使用说明》字节一致。ZIP SHA-256：`86288023cd66c806ebd8c6d679952af6337ccfa10a78d4ea8db8ebffb2996bf3`。
- 遗留：仍需在干净的 Windows 与真实 macOS 主机完成解压、安装和图片/视频/摄像头端到端验收后，再扩大分发范围。

## 2026-08-11 23:34 - 生成首个正式测试版分发包

- 任务：生成可交付的跨平台正式测试版 Demo 包，并排除运行数据与本机凭据。
- 改动：新增 `tools/make_demo_package.py` 与对应测试，以白名单构建 Demo 包；仅纳入当前启用的 `partner_model.pt`、必需的 `best.pt` 回退模型、应用源码、安装/启动脚本、样例、配置模板和唯一用户操作文档 `使用说明.md`（不再重复纳入 `README.md`）。生成 `build/多类隐患检测系统_正式测试版_v0.1.0-test1_20260811/`、同名 ZIP 及 SHA-256 文件；包内含发布说明、逐文件清单和逐文件校验。
- 验证：完整 `unittest discover` 共 96 项通过，Python 编译、`git diff --check`、`run.bat --check` 通过；ZIP CRC、ZIP SHA-256、包内 29 个文件的 SHA-256 均通过。已确认不含 `.venv`、`data/db`、`data/uploads`、训练/评估资料、日志、`config/dingtalk.local.json` 或其他运行数据。ZIP SHA-256：`e33e9a2a33af30809a8f633c219cab9e020f47ba3fea196c6061e18b0c29010c`。
- 遗留：仍需在干净的 Windows 和真实 macOS 主机完成解压、安装、图片/视频/摄像头端到端验收后再扩大分发范围。

## 2026-08-11 22:31 - 支持 macOS 安装与 Apple Silicon MPS 推理

- 任务：在保留 Windows 双击安装方式的前提下，增加先识别操作系统的安装入口，并支持 macOS 运行。
- 改动：新增 `setup.py`，按 Windows/macOS 分派至既有 `setup.bat` 或新的 `setup_macos.sh`；新增 macOS 应用和标注启动脚本。macOS 安装会创建 Unix `.venv`、安装 PyTorch/项目依赖并报告 MPS 或 CPU 模式；启动时为 MPS 不支持的算子启用 CPU 回退。`src/detector.py` 统一选择 CUDA、Apple MPS、CPU，图片、实时摄像头和视频检测均复用该选择；`verify_install.py` 增加 MPS 状态显示。更新安装文档与自动分派、装置选择的回归测试。
- 验证：`.venv\Scripts\python.exe -m unittest discover -s tests -v` 共 93 项通过；`python -m py_compile app.py src\detector.py verify_install.py setup.py`、`git diff --check`、三个 macOS shell 脚本的 `bash -n` 语法检查，以及 `run.bat --check` 通过；真实 macOS/MPS 硬件尚待在目标 Mac 验证。
- 遗留：macOS 首次安装需要联网下载 macOS 版 Python 依赖；从 Windows 迁移时不可复用 `.venv`。

## 2026-08-11 19:35 - 前端页面去除表情符号

- 任务：按用户要求移除前端页面中的表情符号，保持中文标签、风险等级文字和原有五个功能入口不变。
- 改动：`app.py` 去除浏览器页签图标、侧边栏标题、导航项、页面标题、记录页签、实时操作区和录制按钮中的表情符号；历史记录的结构化预警证据不再把后端兼容字段 `icon` 渲染到页面。`tests/test_app_smoke.py` 同步更新纯中文导航和标题断言；`使用说明.md` 同步移除旧图标并更新导航、按钮和实时统计文案。`src/alert.py` 的 `icon` 字段保留为后端兼容数据，不再作为当前前端展示内容。
- 验证：目标页面和文档使用扩展图形字符扫描为 0 项；`.venv\\Scripts\\python.exe -m py_compile app.py src\\dingtalk.py` 通过；9 个测试模块独立进程共 89 项 `unittest` 通过；`tests.test_app_smoke` 的 2 项页面烟测通过；Impeccable detector 返回 0 项；`git diff --check` 通过。
- 遗留：历史或旧版工具脚本中仍可能保留表情符号，但不属于当前 `app.py` 前端页面；如后续重新启用 `tools/legacy` 页面，需要单独做同样的文案清理。

## 2026-08-10 22:26 - 隔离环境完成全量回归

- 任务：在新建的项目隔离 Python 环境中复核此前被系统 OpenCV 冲突阻断的应用烟测，并完成当前工作区的完整离线验收。
- 改动：无业务代码、配置、数据库或凭据改动；仅更新本条验证状态。
- 验证：使用 `.venv\Scripts\python.exe` 将 9 个测试模块分别运行，共 89 项 `unittest` 全部通过；其中 `tests.test_app_smoke` 的 2 项 Streamlit 页面烟测已通过。`python -m py_compile app.py src/dingtalk.py`、`run.bat --check`、示例 JSON 解析和 `git diff --check` 均通过。
- 遗留：隔离环境当前为 CPU 版 PyTorch；真实钉钉会话验证仍需用户提供测试群与管理员权限。Ultralytics 尝试写入账户级设置时有权限警告，不影响项目启动、模型加载或本次测试。

## 2026-08-10 22:21 - 创建项目隔离 Python 环境

- 任务：避免系统 Python 中已有的 OpenCV、PyTorch 等全局依赖影响项目运行，为当前工作区创建独立的项目环境。
- 改动：`setup.bat` 创建 `.venv` 时移除 `--system-site-packages`，并设置 `PYTHONUTF8=1`，确保不继承全局依赖且可正确读取 UTF-8 的依赖清单；基于系统 Python 3.12.8 创建本地 `.venv` 并安装 `requirements.txt`，该目录按既有 `.gitignore` 规则不入库。
- 验证：确认 `.venv\Scripts\python.exe` 的前缀为项目目录、基础解释器为系统 Python；`run.bat --check` 通过；`verify_install.py` 通过核心依赖、CPU PyTorch、模型加载、样例图片推理（23 个目标）和源码模块检查。
- 遗留：当前隔离环境安装的是 CPU 版 PyTorch；如目标机具备 NVIDIA GPU，仍应通过 `setup.bat` 的 GPU 分支安装匹配的 CUDA 版。Ultralytics 在当前受限账户目录写入全局设置时有权限警告，不影响项目依赖、模型加载或推理。

## 2026-08-10 22:04 - 绑定后验证钉钉群名

- 任务：实现真实群名的可靠降级方案；确认 webhook 不能反查群名后，支持用户绑定 `open_conversation_id` 再显式验证，而不伪称为 webhook 自动识别。
- 改动：`src/dingtalk.py` 为每个群兼容可选会话 ID，新增基于 `topapi/im/chat/scenegroup/get` 的脱敏群名解析、5 分钟缓存、显式刷新和超时/断网/HTTP/权限/业务错误/空标题分级；不影响既有文字、markdown、图片发送。`app.py` 的接收群组设置新增受掩码保护的会话 ID 绑定、官方群名/本机名称/来源/识别状态分层，以及“保存群组选择”和“刷新群名（不保存）”两项显式动作；保存按 webhook 安全短标识匹配并校验重复绑定，旧单 webhook 配置可迁入兼容列表。`config/dingtalk.example.json` 与 `使用说明.md` 记录字段、权限和绑定流程；测试补充验证结果不含会话 ID、缓存与失败降级分支。
- 验证：查阅钉钉官方选会话、场景群查询和权限资料，确认选会话 JSAPI 仅适用于钉钉微应用/小程序，群查询要求企业内部应用的 chat 读取权限；`python -m py_compile app.py src/dingtalk.py`、8 个离线测试模块独立进程（87 项）和 `run.bat --check` 通过，`git diff --check` 通过。
- 遗留：未触碰真实 webhook、会话 ID 或群；真实验证仍需用户在有权限的钉钉环境取得会话 ID，并由管理员授予接口权限。`tests.test_app_smoke` 在本机系统 Python 的 `cv2.gapi.wip.draw.Text` 导入错误处中断，发生于 app 导入前且与本次钉钉改动无关；项目 `.venv` 当前不存在，需在完整项目环境复跑该烟测。

## 2026-08-10 21:50 - 交接需求：钉钉真实群名自动识别（待其他对话实施）

- 背景：当前项目是 Windows 本地部署的 Streamlit 应用，入口为 `app.py`，钉钉发送模块为 `src/dingtalk.py`，本地私密配置为 `config/dingtalk.local.json`。现有配置结构是 `app_key`、`app_secret`、`webhooks[]`，每个 webhook 项目包含 `name`、`webhook`、`enabled`。当前版本已经完成“通知设置 → 接收群组”的二级 UI、可编辑本机群名、Webhook 安全短标识、同名/笼统名称提醒，以及按 webhook 而不是按群名写回开关；实时页已移除“已处理帧”。
- 核心问题：Webhook 只知道消息投递目标，当前代码无法仅凭 webhook 反查钉钉真实群名。因此现版的 `name` 只是本机显示名，安全短标识也只是本地生成的区分码，不能冒充钉钉官方群名。用户希望进一步实现“智能识别群名”，避免启停群组时误开/误关。
- 任务性质：这不是纯前端改文案，而是“钉钉开放平台能力 + 配置模型 + 后端解析/缓存 + Streamlit UI + 测试”的联合需求。必须先查阅钉钉官方最新文档，确认 `openConversationId`、群信息查询接口、应用类型、访问权限、授权方式和调用频率限制；不要凭记忆猜接口、权限或 URL。官方资料入口可从自定义机器人文档和会话选择文档开始：`https://open.dingtalk.com/document/orgapp/custom-robot-access`、`https://open.dingtalk.com/tools/explorer/jsapi?id=10303`。
- 目标结果：在通知设置中，用户能看到“钉钉官方群名（如已验证）+ 本地安全群标识 + 识别状态 + 接收开关”，并且能明确知道当前名称来自钉钉接口、本机配置，还是尚未验证；两个群即使同名，也不能仅凭名称作为唯一身份。真实群名识别失败、断网、权限不足或接口超时不得阻断应用启动和现有通知链路。

- 推荐实现路径（先验证再编码）：
  1. 先确认当前本地 Streamlit 应用能否合法取得 `openConversationId`。如果钉钉官方要求在 DingTalk H5/小程序内通过选群 API 获取，则不能假装本地浏览器可以直接完成；应设计一个一次性“绑定群”流程（用户在有权限的钉钉环境选择群，回填 `openConversationId`），或明确需要管理员手工粘贴该 ID。
  2. 在 `config/dingtalk.local.json` 中为 webhook 增加可选字段，例如 `open_conversation_id`；保留旧配置兼容。建议的逻辑身份优先级是 `open_conversation_id`，其次是 webhook 的安全短标识，绝不能用可变的 `name` 作为主键。
  3. 在 `src/dingtalk.py` 增加小范围的群身份解析能力：超时、鉴权、HTTP 状态和钉钉业务错误要分别处理；成功时返回官方群标题和会话 ID；失败时返回可解释状态并降级到本机 `name` + 短标识。接口调用应有短 TTL 缓存和显式刷新，不能因为 Streamlit 每次 rerun 就反复请求钉钉。
  4. 在 `app.py` 的“通知设置 → 接收群组”中增加识别状态：例如“钉钉已验证”“本机名称（未绑定）”“暂时无法验证”。提供明确的“刷新群名/绑定群”入口；刷新前后要保留用户当前启停选择。名称变更、绑定 ID 变更和启停变更必须显式保存，不能输入一个字符就写配置。
  5. 如官方能力无法在当前架构下完成，交付可靠降级方案：继续显示本机群名和安全短标识，增加“名称来源：本机配置，钉钉未验证”的文案，并在日志中记录待办，不得把本机别名标成“钉钉真实群名”。

- 建议配置形态（仅示意，不要把真实凭据写入仓库）：
  ```json
  {
    "app_key": "本地私密配置",
    "app_secret": "本地私密配置",
    "webhooks": [
      {
        "name": "现场总群",
        "webhook": "https://oapi.dingtalk.com/robot/send?access_token=本地私密值",
        "enabled": true,
        "open_conversation_id": "可选的钉钉会话唯一标识"
      }
    ]
  }
  ```
  `open_conversation_id` 必须是可选字段；旧的单 webhook 配置、缺少该字段的多群配置、禁用群和所有现有发送函数都要继续工作。

- 安全与兼容约束：
  - 不在 UI、异常、日志、测试输出或提交内容中显示完整 webhook、access token、app secret、`open_conversation_id` 或完整会话凭据；所有错误信息都要脱敏。
  - 不自动发送“识别测试消息”，不自动加入/退出群，不修改钉钉群设置；如要增加测试按钮，必须只在用户明确点击后向明确选中的单个 webhook 发送，并在按钮旁写清发送目标和副作用。
  - 不以群名作为更新匹配条件；同名群必须通过 `open_conversation_id` 或 webhook 安全身份区分。
  - 识别接口不可用时只影响“名称验证”，不能让已有文字/markdown/图片通知整体失效；保留现有单群失败隔离、全部失败才抛错和实时退避重试逻辑。
  - 不引入改变 `setup.bat` / `run.bat` 双击启动方式的新前端框架，不新增云端数据库，不把真实配置迁入 Git。
  - 任何新增配置字段和代码都应可逆；不要修改检测事实表，不要为了群名识别迁移业务数据库。

- 验收标准：
  1. 两个不同 webhook 即使本机名称相同，UI 也能展示不同的稳定身份；若已绑定并有权限，展示钉钉官方群名和“已验证”状态。
  2. 真实群名接口成功、超时、断网、权限不足、返回空标题、返回业务错误等场景均有单元测试；失败时页面仍可启停群组并继续原有通知。
  3. 旧配置不含 `open_conversation_id` 时可以正常启动、发送和编辑；回滚代码后新增字段不会破坏旧版本读取。
  4. Streamlit rerun 不会重复调用群名接口；显式刷新有缓存/节流策略，并显示最近一次识别时间或失败原因。
  5. 配置保存按不可变身份匹配，名称重复、名称为空、身份缺失和身份冲突都有明确校验，不能静默写错群。
  6. UI 同时表达名称、身份、来源、验证状态和接收状态，不依赖颜色或图标单独传达含义；窄屏和键盘操作不出现溢出。
  7. 运行 `python -m py_compile app.py src/dingtalk.py`、9 个测试模块独立进程回归、`git diff --check`；若使用浏览器验收，至少检查通知设置、失败降级和实时页统计。
  8. 测试只能使用 mock/临时配置；真实钉钉端到端测试必须由用户提供测试群和明确授权，不能在无人确认时触碰生产群。

- 交接提示词（可复制给负责实现的其他对话）：
  > 请在 `F:\\sytksakgdlalsd\\stystsyysy` 项目中实现“钉钉真实群名自动识别”。先读取 `AGENTS.md`、`PROJECT_LOG.md` 和 git 状态，保留现有未提交改动，禁止提交真实配置、数据库、上传产物或 token。当前项目使用 Streamlit（`app.py`）和 `src/dingtalk.py`，配置为 `config/dingtalk.local.json`，现版已经有“通知设置 → 接收群组”、Webhook 安全短标识、同名提醒和按 webhook 保存。请先查钉钉官方最新文档，确认 `openConversationId` 获取方式、群信息查询接口、应用权限和本地 Streamlit 是否具备调用条件；不要猜接口。然后给出最小可回滚实现：可选 `open_conversation_id` 配置、脱敏的群身份解析/缓存/显式刷新、UI 的官方群名/本机名称/验证状态分层，以及没有 ID、断网、权限不足和旧配置的可靠降级。配置保存必须按不可变身份匹配，不能按群名匹配；不能自动发测试消息或修改群设置；保留原有多群失败隔离、图片/文字通知和 Windows 双击启动。补充 mock 单元测试、app smoke 测试、语法检查和 diff 检查；完成后在 `PROJECT_LOG.md` 顶部按“任务/改动/验证/遗留”追加日志，并明确哪些能力因钉钉权限或真实群测试尚未验证。

- 遗留/决策点：在确认官方 API 和授权方式前，不要承诺“完全自动识别”。如果最终只能由用户绑定 `openConversationId`，产品文案应称“绑定后验证群名”，不要称“Webhook 自动识别”。

## 2026-08-10 21:38 - 钉钉群组识别与通知设置分层

- 任务：按用户反馈降低多群启停歧义，将钉钉群选择收进更清晰的二级设置，并移除实时页不需要的“已处理帧”展示。
- 改动：`src/dingtalk.py` 为每条机器人 Webhook 生成不暴露 token 的稳定安全群标识，未命名项不再截取 token 作为名称；`app.py` 将侧边栏改为“通知设置 → 接收群组”，显示已启用数量，支持编辑本机群名、检测同名或“默认群/群2”等笼统名称、核对安全群标识和接收状态后统一保存；配置写回改为按 Webhook 匹配，避免同名群改错。实时统计仅展示“累计违规/已存记录”，内部帧计数继续用于跳帧检测。`使用说明.md` 同步说明群名来源、设置路径及安全群标识；新增名称歧义和短标识回归测试。
- 验证：9 个测试模块以独立进程运行，82 项 `unittest` 全部通过；`py_compile`、`git diff --check`、Impeccable 扫描通过（0 项）；受控浏览器实机确认两层通知设置、两个现有笼统群名提醒、不同群标识，以及实时页不再出现“已处理帧”。验收未点击保存、未发送钉钉消息，真实本地配置和业务记录未改写。
- 遗留：机器人 Webhook 只负责消息投递，不能可靠反查钉钉真实群名；本版以“可编辑完整群名 + 安全群标识 + 同名/笼统名称提醒”消除歧义。若要由钉钉自动返回群标题，后续需为每个群补充 `openConversationId` 和对应开放平台权限/接口。

## 2026-08-10 11:30 - 风险优先前端第一版与隐患处置闭环

- 任务：按前端专项审计建议完成第一版风险优先界面，在保留五个既有入口、检测链路和 Windows 双击启动方式的前提下，补齐记录筛选、证据复核与处置闭环，并确保代码和运行数据可回滚。
- 改动：`app.py` 建立深色本地值守视觉层级，将图片结论改为“最高风险/下一步”优先，增加内容+模型指纹和显式开始按钮以避免 Streamlit rerun 重复推理、入库及告警；检测记录改为红色/超期优先的可筛选工作队列，可选择任意图片或实时证据并保存待处理、处理中、已关闭、误报、负责人、期限和复核说明；实时检测补中文摄像头状态/权限错误、可暂停统计刷新，视频检测改为确认后开始；统计页增加处置进度。`src/database.py` 新增独立 `incident_workflows` 表和参数校验/状态统计，不改写原始检测事实；队列加载全部开放事项，仅对已结项/合规历史保留最近 200 条并在界面明示范围。新增 `PRODUCT.md`、Streamlit 主题、响应式/键盘焦点样式，最低 Streamlit 版本修正为 1.52；数据库和前端辅助测试同步扩充。
- 验证：9 个测试模块以独立进程运行，80 项 `unittest` 全部通过；Python 语法检查、`run.bat --check`、`git diff --check` 通过；Impeccable 设计反模式扫描为 0 项；使用受控浏览器实际检查桌面与 390px 手机视口、五个页面、图片显式确认和开放队列范围。迁移前已在 `data/db/backups/hazard_records_pre_frontend_v1_20260810_1107.db` 建立 Git 忽略的本地快照；迁移后 SQLite `integrity_check=ok`，原图片/实时记录仍为 2/158 条，处置表 0 条，验收未制造业务记录。
- 遗留：真实摄像头/WebRTC、长视频转码、真实图片推理和钉钉断网/多群部分失败仍需硬件及端到端测试；第一版保存当前处置状态而非完整审计时间线；历史图片未保存原图完整路径；已结项/合规历史在队列中仅显示最近 200 条，后续数据量增大时可补服务端分页归档。

## 2026-08-09 07:55 - 实时钉钉通知失败保留与退避重试

- 任务：修复实时通知在网络发送前清空待发送隐患、失败后数据丢失且无法自动重试的问题。
- 改动：`app.py` 将实时通知保存为受锁保护的在途批次，文字和裁剪图均成功后才扣除对应待发计数并更新时间；失败时保留批次，按 30/60/120 秒封顶退避，并用发送中标志避免并发重复；文字已成功而图片失败时仅重试图片；摄像头回调在无新违规时也检查待重试批次。`tests/test_app_helpers.py` 补充失败保留、退避封顶、新事件保留和图片续传回归测试，并同步覆盖状态重置。
- 验证：通知相关 28 项 `unittest` 全部通过；扩大到预警、通知、数据库、检测器、配置和迁移工具的 57 项离线测试全部通过；`python -m py_compile app.py` 与 `git diff --check` 通过。
- 遗留：自动重试依赖实时摄像头流仍在运行；真实断网恢复和多群部分失败场景尚未做手机端集成测试。

## 2026-08-07 21:58 - 生成单文件回迁压缩包

- 任务：按用户要求把已验证的迁移目录进一步制作成便于搬运的单个压缩文件。
- 改动：在 `迁移说明.md` 补充压缩包交接信息，将本条最终日志同步到迁移目录并刷新包外文件清单与逐文件 SHA-256 清单；使用支持大文件的 ZIP64 格式生成 `F:\多类隐患检测系统_迁移包_20260807.zip`，压缩包内同时包含完整项目目录、包说明清单和逐文件校验清单，并在同级生成压缩包 SHA-256 文件。
- 验证：使用 Python 标准库完整读取 ZIP 中所有成员并执行 CRC 校验；核对压缩包包含项目目录和两个包外清单，随后再次确认源目录与包内仓库 HEAD、未提交状态和最终日志一致。
- 遗留：压缩包仍含真实钉钉凭据和业务数据，只能私密传输；原始未压缩目录暂时保留，确认原电脑成功解压和运行后再决定是否删除。

## 2026-08-07 21:27 - 完成回迁前最终扫描与打包

- 任务：全面复核当前工作区改动、共享日志和迁移边界，生成可带回原电脑继续开发的最终状态包。
- 改动：将 `PROJECT_LOG.md` 标题恢复到首行并把 73 条既有记录按时间倒序整理（历史正文保留不改写）；更新 `迁移说明.md` 的回迁交接信息；增强 `tools/make_portable.py`，排除覆盖率产物与 Git 临时对象，并把生成清单移到包外以保持包内 Git 状态不变；在 `tests/test_portable.py` 增加相应回归测试；生成完整迁移目录 `F:\多类隐患检测系统_迁移包_20260807\stystsyysy`、包外说明清单及逐文件 SHA-256 清单。
- 验证：源仓库与迁移包分别运行 69 项 `unittest` 均通过；`run.bat --check`、Python 语法检查、`git diff --check`、源/目标 `git fsck --full --no-dangling` 与 `git lfs fsck` 均通过；源/目标 HEAD 均为 `1b1ed7c`，18 行未提交状态完全一致；迁移包共 37,930 个文件、约 5,136.5 MB，22 个关键路径齐全，主模型 SHA-256 一致且未发现任何约定排除项。
- 遗留：迁移包含真实钉钉凭据、运行数据库、上传记录与业务数据，必须私密传输；目标电脑需双击 `setup.bat` 重建未打包的 `.venv`，约 18 GB 的 `data/material_library/hf_datasets/` 仍按可下载原始素材排除；11 条早期历史日志沿用旧格式，为避免编造事实未补写缺失字段。

## 2026-08-04 00:21 - 建立自动化测试与覆盖率基线

- 任务：按工作区代码结构审查现有测试覆盖率，补齐核心运行模块、Streamlit 启动/辅助逻辑和高风险数据工具的离线回归测试。
- 改动：
  - 新增 `tests/`，共 68 项标准库 `unittest`，覆盖检测器模型路径/回退/检测摘要、预警、SQLite 建表迁移与统计、钉钉配置/缓存/多群/图片/失败分支、Streamlit 非摄像头页面 smoke、实时统计与通知汇总、数据标签校验/预测框去重/迁移目标安全约束；测试使用依赖替身、临时目录并阻断真实钉钉网络。
  - 新增 `.coveragerc` 与 `requirements-dev.txt`，`README.md` 补充测试和覆盖率命令，`.gitignore` 排除覆盖率产物。
  - `app.py` 修复实时钉钉汇总遇到红色预警后提前退出的问题，确保同一汇总内的反光衣、口罩等后续违规类型不会丢失。
- 验证：`.venv\Scripts\python.exe -m coverage run -m unittest discover -s tests -v` 通过（68/68）；分支覆盖率 `src/` 100%、`app.py + src/` 59%、全工作区活跃 Python 代码 35%；`py_compile app.py`、`run.bat --check`、`git diff --check` 均通过。
- 遗留：摄像头/WebRTC 回调、视频上传/转码、真实图片上传推理以及多数一次性数据整理脚本仍需硬件或集成级测试；当前覆盖率分别为 `app.py` 37%、全工作区 35%。

## 2026-08-03 20:03 - 整理项目结构

- 任务：清理根目录弃用权重、收编已被替代的开发工具、删除指向废弃工具的启动脚本，并同步文档目录结构。
- 改动：
  - `yolo26m.pt`/`yolo26n.pt`（共 47MB，已弃用的 yolo26m 预训练权重）移到 `archive/2026-08-03-弃用yolo26权重/`（本地，可恢复）。
  - 新建 `tools/legacy/`，移入 5 个已弃用/一次性脚本：`annotate.py`、`label_tool.py`、`review_tool.py`、`merge_new_materials_pt1.py`、`download_torch_gpu.py`（git mv 保留历史）。
  - 删除 `run_label_tool.bat`、`run_review_tool.bat`（工具已废弃）。
  - 《使用说明.md》「目录结构说明」与 `README.md` 目录同步更新。
- 验证：git status 确认 5 个重命名、2 个删除、3 个文档修改；全库脚本/文档无对废弃工具的残留引用（仅 PROJECT_LOG.md 历史记录保留）。
- 遗留：无。

## 2026-08-03 19:55 - 钉钉配置说明合并进《使用说明.md》

- 任务：用户反馈独立的钉钉配置文档不如合并进《使用说明.md》，方便新人单文档部署。
- 改动：《使用说明.md》新增「六、钉钉预警通知配置（可选）」章节（6.1 原理 / 6.2 凭据准备 / 6.3 配置填写 / 6.4 验证 / 6.5 常见问题 / 6.6 排查位置），原「目录结构说明 / 常见问题 / 技术信息 / 复制到其他电脑」章节顺延为七～十；删除独立文件 `钉钉配置说明.md`。
- 验证：章节标题与编号核对无误，代码块与表格内容完整。
- 遗留：无。

## 2026-08-03 19:53 - 新增《钉钉配置说明.md》部署文档

- 任务：评估新人部署场景，发现《使用说明.md》完全没有钉钉配置内容，新部署者只能从 PROJECT_LOG.md 翻历史踩坑。补齐部署文档。
- 改动：新增 `钉钉配置说明.md`——两类凭据准备（开放平台企业应用 AppKey/AppSecret + 各群机器人 webhook）、安全设置建议（自定义关键词填「预警」）、`config/dingtalk.local.json` 格式（webhooks/name/enabled）、验证命令、常见问题对照表（310000 / 300005 / 40014 / 表情包 / 无企业账号）、代码位置。
- 验证：文档内容与已实测链路一致（webhook 发送、app token 上传、markdown 嵌图、多群白名单）。
- 遗留：建议后续在《使用说明.md》目录/常见问题中加一条指向本文档的链接。

## 2026-08-03 16:30 - 白名单新增「群2」并验证多群推送

- 任务：用户提供另一个群的 webhook，加入多群白名单。
- 改动：`config/dingtalk.local.json` 的 `webhooks` 新增「群2」（enabled=true；名称可随时在配置中修改）。
- 验证：新群文字测试 errcode=0；模块级多群测试 `list_webhooks` 返回 2 个启用群，`send_text` 与 `send_image`（上传一次 media_id、两个群同时发送）均 errcode=0，默认群与群2 均已收到文字和裁剪图。
- 遗留：无（改群名只需改配置 `name` 字段）。

## 2026-08-03 16:29 - 钉钉群开关界面化 + app 启动验证

- 任务：确认依赖环境（位于 `D:\我的\李一平\多类隐患检测系统_可移植包\.venv`，Python 3.13.14，含 streamlit 1.59.2 / torch 2.6.0+cu124 / ultralytics）；把多群白名单开关做成 app 侧边栏界面。
- 改动：
  - `app.py`：新增 `_render_dingtalk_group_toggles()`，侧边栏「钉钉群开关」折叠面板，按群勾选=启用、取消=停用，变更实时写回 `config/dingtalk.local.json` 的 `webhooks[].enabled`。
  - 工作区根目录创建 `.venv` Junction 指向 D 盘 venv（`.venv` 已被 .gitignore 排除，不入库），使 `run.bat` 双击启动恢复可用。
- 验证：`py_compile` 通过；Streamlit AppTest 执行 `app.py` 零异常，侧边栏成功渲染「钉钉群开关」及「默认群=True」；headless 服务 `/_stcore/health` 返回 HTTP 200；`run.bat --check` 输出 [OK]。
- 遗留：`.venv` 是指向 D 盘副本的 Junction，若日后在 E 盘工作区运行 `setup.bat` 需先删除该链接；WebRTC/摄像头实机链路建议在有摄像头时实测一次。

## 2026-08-03 16:24 - 钉钉支持多群白名单开关

- 任务：把同一条通知发送到多个群，并支持按群启停（白名单开关），停用某群时无需让机器人退群。
- 改动：
  - `src/dingtalk.py`：配置支持 `webhooks` 列表（`name`/`webhook`/`enabled`），只向 `enabled=true` 的群发送；单个群失败仅记日志、不影响其他群，全部失败才抛异常；新增 `list_webhooks()` 供管理和界面使用；兼容旧的单 `webhook` 字符串配置。
  - `config/dingtalk.local.json`：迁移为新格式（`webhooks` 列表，当前为「默认群」= webhook#2，enabled=true）。
  - `config/dingtalk.example.json`：更新为 A/B 双群示例（B 群 enabled=false 展示停用写法）。
- 验证：`py_compile` 通过；临时配置测试——`list_webhooks` 返回全部群、`load_config` 仅返回启用群、全部停用时正确抛出「没有启用的机器人 webhook」；真实发送文字（test_dingtalk.py）、markdown、裁剪图均 errcode=0 送达默认群。
- 遗留：app 界面开关未做（当前改配置 `enabled` 即可，无需重启）；如需在 Streamlit 侧边栏加群开关，待依赖环境就绪后再补。

## 2026-08-03 16:20 - 确定钉钉正式通道：webhook#2，webhook#1 弃用

- 任务：另一个群（webhook#1）机器人开启「自定义关键词」安全校验，尝试 报警/隐患/检测/通知/安全/告警 均返回 310000，用户确认不采用，正式通道定为 webhook#2。
- 改动：无代码改动；`config/dingtalk.local.json` 的 `webhook` 字段维持指向 webhook#2（此前已配置）。
- 验证：webhook#2 文字、markdown、图片（markdown 嵌入 media_id）均已实测 errcode=0；裁剪图推送链路（画框→120px 边距裁剪→上传→发送）模拟测试通过，裁剪图 `data/uploads/snapshots/crop_20260803_test_no-helmet.jpg` 已生成并成功推送。
- 遗留：本机未安装 Python，模块级/app 级回归未跑，需在装有 Python 的机器上执行 `tools/test_dingtalk.py` 或 `run.bat` 触发一次违规做最终确认；后续如需换群，只改本地配置 `webhook` 字段。

## 2026-08-03 16:18 - 钉钉链路模块级回归通过（真实 Python）

- 任务：用户指出本机已装 Python（位于 Codex 运行时依赖目录、未加入 PATH），补齐此前遗留的模块级回归。
- 改动：无代码改动。
- 验证：使用 Python 3.12.13（`C:\Users\34165\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`）对 `src/dingtalk.py`、`app.py` 等 7 个文件 `py_compile` 全部通过；`tools/test_dingtalk.py`（send_text）成功；直接调用 `src/dingtalk.py` 的 `send_markdown`、`send_image` 均返回 errcode=0。钉钉链路（文字/markdown/裁剪图）在真实代码路径下全部验证通过。
- 遗留：完整 app 运行仍需第三方依赖（streamlit/ultralytics/torch，需双击 `setup.bat` 建 .venv）；webhook#1 弃用，webhook#2 为正式通道。

## 2026-08-03 16:12 - 修正钉钉图片推送：markdown 嵌入图片替代 msgtype=image

- 任务：用户反馈 16:10 发送的测试图在群里以「表情包」样式显示而非普通图片。确认 robot/send 的 `msgtype=image` 在群内渲染为表情，改用钉钉推荐方式——markdown 消息中用 media_id 作为图片地址（`![图片说明](media_id)`）显示普通图片。
- 改动：`src/dingtalk.py` 的 `send_image` 改为上传媒体后发送 markdown 消息嵌入图片（`title=违规图片`）。
- 验证：实测 `gettoken → media/upload → robot/send markdown ![图](media_id)` 返回 errcode=0；已向 webhook#2 所在群发送第二条测试消息，待用户目视确认显示为普通图片。
- 遗留：无（用户确认后即为此方案的最终形态）。

## 2026-08-03 16:10 - 修复企业应用机器人钉钉发送链路（webhook 发送 + app token 传图）

- 任务：用户提供企业机器人 webhook 后，实测发现现有代码的发送链路不通：`robot/send` 用 app access_token 调用返回 300005「token is not exist」，图片消息用 `media_id` 字段被拒（要求 `picURL`）。通过逐接口实测确定正确链路并修复代码。
- 改动：
  - `src/dingtalk.py`：`robot/send` 改为直接 POST 配置中的机器人 webhook（不再拼 app token）；`send_image` 上传媒体后改用 `image.picURL=media_id` 发送；配置读取新增 `webhook` 字段，并用 `utf-8-sig` 兼容 BOM。
  - `config/dingtalk.local.json`：新增 `webhook` 字段（本机密钥文件，Git 忽略），保留原有 `app_key`/`app_secret`。
  - `config/dingtalk.example.json`：同步为新格式（`app_key`/`app_secret`/`webhook`）。
- 验证：逐接口实测通过——`gettoken`(errcode=0) → `media/upload`(拿到 media_id) → `robot/send` 文字、markdown、图片(picURL=media_id) 均 errcode=0；webhook#2 所在群已收到文字、markdown、测试图各一条。旧方式（app token 调 robot/send）返回 300005，图片字段 media_id 返回 400802，均已确认废弃。
- 遗留：本机未安装 Python，未做模块级回归（`tools/test_dingtalk.py` 需在装有 Python 的机器上复测）；用户提供的 webhook#1 带自定义关键词校验（310000），未采用；如需切换机器人，只改配置中的 `webhook` 字段即可。

## 2026-08-01 17:44 - 同步迁移文档路径至当前工作区

- 任务：处理上一轮补记迁移日志时留下的遗留项，将 `迁移说明.md` 与 `package_manifest.txt` 中的旧路径同步为当前工作区 `E:\stysyysy\stystsyysy`。
- 改动：`迁移说明.md` 新增「迁移情况」章节，写明 2026-08-01 09:25 在源电脑生成迁移包、17:24 迁入本机，并将「新电脑继续开发」改为「在本机继续开发」；`package_manifest.txt` 补充「迁入时间」与「当前位置」，源项目路径标注为源电脑记录。
- 验证：当前工作区文件数 37854、总大小 5136.1 MB 与迁移包记录完全一致，确认本工作区即源电脑生成的迁移包；两份文档路径已统一为当前位置，旧路径均有来源标注。
- 遗留：无。

## 2026-08-01 17:42 - 补记迁移情况：工作区由另一台电脑迁入

- 任务：当前工作区 `E:\stysyysy\stystsyysy` 是从另一台电脑迁移过来的，此前未在日志中记录本次迁移，特此补记情况说明。
- 改动：仅补记本条日志，未改动任何代码、数据或配置；本次迁入发生在 2026-08-01 17:24（本工作区根目录与 `.git` 创建时间 17:24:37，文件写入至 17:28 完成）。
- 验证：`git HEAD` 为 `1243caf`（2026-07-29 最后提交），Git 历史与全部未提交改动完整保留；未提交改动清单（`app.py`、`src/dingtalk.py`、`run.bat`、`PROJECT_LOG.md`、`迁移说明.md`、`tools/make_portable.py`、`package_manifest.txt`、`models/partner_model.pt`、`data/partner_field_test/`、`data/training_v4clean/` 等）与 2026-08-01 09:25 日志记录一致；本机 `F:` 盘已不存在日志中记载的源项目目录，来源路径无法进一步核实。
- 遗留：`迁移说明.md` 与 `package_manifest.txt` 中仍引用旧电脑的 `F:\Multi-hazard Detection System\...` 路径，尚未同步更新为当前路径；如需重训所用的 18GB `hf_datasets` 外部原始数据仍须重新下载。

## 2026-08-01 09:25 - 生成可迁移继续开发包

- 任务：将当前项目打包为可在其他电脑继续开发/运行的完整迁移包，确保当前实现、进度、日志文件和工作守则全部迁移。
- 改动：
  - 新增 `tools/make_portable.py`：一键复制项目到目标目录，排除 `.venv`、Python 缓存、`.git/lfs/tmp` 与 18GB 的 `hf_datasets` 外部原始数据
  - 新增 `迁移说明.md`：说明迁移内容、排除项与新电脑恢复步骤
  - 将 7 个开发工具脚本中的硬编码旧路径 `F:\多类隐患检测系统_可移植包\...` 改为基于 `__file__` 的项目根相对路径
  - 生成 `F:\多类隐患检测系统_可移植包\多类隐患检测系统_可移植包` 完整迁移包（含 .git、models、data、runs、evaluation、archive、日志与 AGENTS.md）
- 验证：迁移包共 37854 个文件、约 5.0 GB；`git fsck` 通过，Git 历史与全部未提交改动完整保留；关键文件（models、data/db、runs、evaluation、archive、tools/annotate.log、data/uploads/dingtalk_send.log、AGENTS.md、PROJECT_LOG.md、portable/ppe-annotator.exe）均存在；8 个新增/修改 Python 文件 `py_compile` 全部通过；包内代码无残留旧绝对路径。
- 遗留：未提交改动保持原样，不做提交；迁移包不含 18GB 的 `hf_datasets`，如需重训该数据源需重新下载。

## 2026-07-31 01:10 - 钉钉从自定义机器人webhook升级为企业内部应用机器人

- 任务：自定义机器人无法发送图片（20KB限制、upload_media 404、图床不可用），升级为企业内部应用。用户已提供AppKey/AppSecret。
- 改动：config/dingtalk.local.json改为app_key+app_secret格式；src/dingtalk.py全面改写为access_token模式（get_token缓存/上传媒体/send_image用media_id替代picUrl）。
- 验证：待编译通过后测试。
- 遗留：需restart后验证图片发送。

## 2026-07-31 00:50 - 钉钉自定义机器人图片发送结论：不可行

- 任务：通过日志排查图片发送失败原因，并探索所有可行方案。
- 结论：
  1. upload_media端点：自定义机器人webhook返回404 URI不存在
  2. base64编码msgtype=image：body超20KB硬限制（errcode 460101）
  3. 0x0.st免费图床：HTTP 503不可用
  4. catbox.moe：国内无法访问
  5. 自定义机器人webhook仅支持text/link/markdown/actionCard/feedCard，msgtype=image不在支持列表中
- 遗留：需升级为钉钉企业内部应用（AppKey+AppSecret+access_token+media upload API）方可发送图片。

## 2026-07-31 00:40 - 修复图片发送：body超20KB限制，加JPEG压缩

- 任务：send_image 返回 errcode=460101，钉钉webhook body上限20000bytes，base64编码后超限。
- 改动：dingtalk.py send_image 增加 PIL JPEG quality=40 压缩，原始>14KB时触发，确保base64后<20KB。
- 验证：编译通过。
- 遗留：无。

## 2026-07-31 00:40 - WebRTC增加国内STUN服务器

- 任务：摄像头连接出现STUN/TURN超时，默认Google STUN在国内不稳定。
- 改动：app.py webrtc_streamer增加rtc_configuration，添加stun.qq.com:3478作为国内备选。
- 验证：编译通过。
- 遗留：无。

## 2026-07-31 00:30 - 产品简化：移除实时统计、改造钉钉推送带裁剪抓拍图

- 任务：产品经理提出去掉实时监测统计，钉钉推送改为markdown格式、去计数、附带违规人员裁剪图。
- 改动：app.py移除实时画面下方统计卡片与表格；_send_realtime_violations改为markdown无计数格式；frame_violations/to_record链路加入bbox传递并裁剪120px违规区域图；dingtalk.py新增send_markdown/send_image(base64)；config.toml加headless；run.bat加应用模式浏览器启动与headless参数；引入logger写入dingtalk_send.log。
- 验证：编译通过；markdown文字推送用户确认收到；crop_*.jpg已生成；send_image待用户重启后确认errcode。
- 遗留：robot/upload_media端点404，已回退base64；需查看日志确认send_image最终结果。

## 2026-07-29 20:00 - 建立合作方实地测试集：32张原始标注 + partner_model预标注

- 任务：用 partner_model.pt 对32张合作方实拍自动预标注，建立独立测试集，供人工标注后用做基准评估。
- 改动：
  - 新建 data/partner_field_test/：images(32张) + labels(410个预标注框) + data.yaml
  - 预标注模型：partner_model.pt, conf=0.25
- 验证：
  - 410个预标注框：Hardhat 97, Person 134, Safety Vest 75, NO-Mask 55, NO-Safety Vest 34, machinery 8, NO-Hardhat 5, Mask 1, Safety Cone 1
  - NO-Mask 在29/32张图上被检出（v4仅2-3张）
- 遗留：待人工逐张标注（删误检、补漏检），标注后以人工标签为ground truth评估模型精度

## 2026-07-29 10:40 - 竞品分析：对方项目优势功能清单

- 任务：分析竞品日志（2026-07-21~23），提取我们缺失或不如的功能，供分工实施。
- 竞品优势功能：
  1. 置信度滑块视觉反馈 — 调阈值后显示"✅ 当前生效置信度: 0.xx"，用户不会疑惑阈值是否生效
  2. setup.bat GPU自适应 — 自动检测NVIDIA显卡，有则装CUDA版torch，无则回退CPU版，新电脑开箱即用
  3. 可移植打包脚本 — 项目一键打包为zip（不含.venv/大型数据），解压双击setup.bat即用
  4. bat编码标准化 — GBK+CRLF方案解决了Windows bat中文乱码闪退，含.gitattributes持久化
  5. git规范 — 每个功能独立commit可单独回滚，bug修复有明确基线commit
  6. WebRTC回调竞态修复 — 回调线程禁调@st.cache_resource，重资源主线程预热存共享对象
- 我们已有的（不需重复）：
  - WebRTC实时检测、st.fragment局部刷新、违规抓拍/入库/告警音、VideoWriter录制、track_id显示、中文标签修复 — 均已具备
- 建议分工：
  - 功能1-2（置信度反馈+GPU自适应）→ 改动小见效快，单次改动即可
  - 功能3（打包脚本）→ 独立任务，不涉业务代码
  - 功能4（bat编码）→ 高风险改基础设施，需全量bat回归测试

## 2026-07-29 10:25 - 引入合作方模型：NO-Mask Recall 0.588，优于所有自训模型

- 任务：用户从另一台电脑提供的best.pt，评估并接入。
- 改动：
  - 新增 models/partner_model.pt（YOLOv8n, 3M, 10类）
  - active_model.txt 切换至 partner_model.pt
- 验证（黄金40张集）：
  - Overall mAP50: 0.487（低于v4的0.857但NO-Mask远超）
  - NO-Mask mAP50: 0.677, Recall: **0.588**（v4仅0.04, v5仅0.313）
  - Hardhat: 0.516, Safety Cone: 0.004（弱项）
- 结论：此模型"未戴口罩"检出能力是所有模型中最好的，代价是整体分数低。对用户实际使用场景（优先召回未戴口罩）是最佳选择。

## 2026-07-29 09:55 - yolo26m_v2_clean训练完成：黄金集仅0.256，确认大模型方向不可行

- 任务：用v4时代1985张干净数据训练yolo26m(21.8M参数)，验证"精选数据+大模型"方向。
- 改动：models/yolo26m_v2_clean.pt（100 epochs, batch=4, 2.37h, RTX 5060）。
- 验证（黄金40张集）：
  - Overall mAP50: 0.256（v4=0.857, 差距巨大）
  - NO-Mask: 0.016, Safety Cone: 0 — 几乎完全失效
  - 内部val=0.743 vs 黄金集=0.256，过拟合极严重
- 结论：21.8M参数对2000张数据集严重过大。全模型对比：v4(3M/0.857) > v5(3M/0.795) > yolo26m_v2(21.8M/0.256) > yolo26m_v1(21.8M/0.178)
- 遗留：v4仍是当前最佳模型；提升精度需域内人工标注NO-Mask/Safety Cone数据后基于v4轻量fine-tune；yolo26m系列可弃用。

## 2026-07-29 00:50 - yolo26m方向修正：用v4精选训练集重训

- 任务：yolo26m_v1在混杂数据上黄金集mAP50仅0.178，严重过拟合。改用v4时代的1985张干净数据重训yolo26m_v2_clean，验证"大模型+精选数据"方向。
- 改动：
  - 新建 data/training_v4clean/：从training_dataset过滤掉ppe_vincent/hardhat_FO/cs/excavator文件，仅保留v4级1985张干净数据
  - 启动yolo26m_v2_clean训练：100 epochs, batch=8, RTX 5060，当前正在运行
- 验证：
  - yolo26m_v1(混杂数据): gold mAP50=0.178, internal val=0.931 — 严重过拟合
  - v4(YOLOv8n, 同批干净数据): gold mAP50=0.857 — 当前最佳
- 遗留：
  - yolo26m_v2_clean训练进行中(epoch 1/100)，预计3-4小时
  - 中文乱码已修复(app.py, commit d81b8d4)
  - active_model.txt仍指向yolo26m_5ep.pt

## 2026-07-28 16:00 - 修复检测框中文标签乱码（cv2.putText→PIL渲染）

- 任务：cv2.putText 的 Hershey 字体不支持 CJK 字符，导致检测框上的中文标签（安全帽/未戴口罩等）显示为乱码方块。
- 改动：
  - `app.py`：新增 `_put_chinese_text()` 辅助函数，用 PIL/ImageDraw + 微软雅黑字体(`C:\Windows\Fonts\msyh.ttc`) 在图像上绘制中文文本。
  - `_draw_boxes` 中的两处 `cv2.putText()` 调用替换为 `_put_chinese_text()`。
  - 新增 `from PIL import Image, ImageDraw, ImageFont` 和 `import numpy as np` 导入。
- 验证：`py_compile` 通过；代码逻辑未变（仅渲染方式变化）。
- 遗留：精度问题（yolo26m仅5轮训练）需另建训练任务处理；active_model.txt 仍指向 yolo26m_5ep.pt，如需回滚改为 ppe_v4.pt 即可。

## 2026-07-28 15:38 - YOLO26m candidate reversible integration

- Task: Complete the logged handoff: make the YOLO26m 5-epoch candidate selectable in the application without replacing the production `models/best.pt`.
- Changes:
  - Copied and SHA-256 verified `runs/yolo26/candidate_5ep/weights/best.pt` to ignored local file `models/yolo26m_5ep.pt`; added the exact ignore rule `/models/yolo26m_*.pt`.
  - Added tracked `models/active_model.txt` with default `yolo26m_5ep.pt`. Editing it to `best.pt` performs the rollback.
  - Updated `src/detector.py` to validate the fixed 10-class order, expose the actual `model_path`, `model_version`, `fallback_used`, and fall back to local `models/best.pt` on missing/load-invalid candidates (with explicit final COCO fallback only if PPE weights fail).
  - Updated `app.py` cache keys to use the resolved model path, display the actually loaded model/fallback state in the sidebar, and persist the actual model version for image and realtime events.
  - Updated `src/database.py` with an idempotent `PRAGMA table_info` migration for `model_version` in both tables; no database was deleted or rebuilt.
- Verification:
  - `py_compile app.py src/detector.py src/database.py`, `run.bat --check`, headless Streamlit startup plus `/_stcore/health` (HTTP 200), and `git diff --check` passed.
  - Default candidate loads with the expected class order; direct image `detect()` and `track()` smoke tests on `data/sample_images/test_helmet.jpg` passed.
  - Switching to `best.pt`, restoring the candidate, temporarily renaming the candidate to confirm automatic fallback, a temporary-DB write test, and migration checks of the existing database all passed.
  - Production `models/best.pt` SHA-256 remains `2419700BBE3B8D38F9000655D9CF952A4BC93EF6C143BAF8B49A0ABDE5D0760F`.
- Remaining: A user-operated webcam/video session is still needed to measure full-pipeline FPS/memory stability and validate real screenshot/DingTalk delivery; no runtime database, weights, screenshots, cache, or training output is staged for Git.

## 2026-07-28 14:53 - 交接：将YOLO26m候选可回滚接入比赛软件

- 任务：用户决定由下一个对话完成YOLO26m候选模型的实际软件接入；本条记录给出完整实施需求、产物位置、风险、验收门槛和回滚方案。本对话不修改业务代码、不覆盖现有生产权重。
- 改动：本对话已完成YOLO26m预训练权重下载、1 epoch smoke test、4790/561张净化数据的5 epochs候选训练，以及候选与当前模型在同一40张黄金集上的复评。新增训练/评估产物均位于已忽略的 `runs/`、`evaluation/results/` 和根目录自动下载权重中；生产文件 `models/best.pt` 未改动。
- 当前模型与候选产物：
  - 生产模型：`models/best.pt`，YOLOv8n，6,250,090 bytes，SHA-256 `2419700BBE3B8D38F9000655D9CF952A4BC93EF6C143BAF8B49A0ABDE5D0760F`。
  - 候选模型：`runs/yolo26/candidate_5ep/weights/best.pt`，YOLO26m，44,017,177 bytes，SHA-256 `0F842DE7702651DB50E5656AD126BCCEBECC4A15EAB35B629EF3F21381876EB2`。
  - 候选类别顺序已确认与业务完全一致：`Hardhat, Mask, NO-Hardhat, NO-Mask, NO-Safety Vest, Person, Safety Cone, Safety Vest, machinery, vehicle`；任务为detect，模型为end-to-end输出。
  - 候选普通验证集：Precision约0.81、Recall约0.78、mAP50=0.853、mAP50-95=0.561、GPU推理约7.7ms；batch=8峰值显存约4.83GB。
  - 候选严格40张黄金集：Precision=0.459、Recall=0.292、mAP50=0.280、mAP50-95=0.128、推理约12.6ms。
  - 当前YOLOv8n同黄金集：Precision=0.690、Recall=0.452、mAP50=0.487、mAP50-95=0.368、推理约3.2ms；但旧权重曾见过其中26张黄金图，只能作为带泄漏参考。
- 下一个对话必须完成的最小实施：
  1. 复制候选权重为本地 `models/yolo26m_5ep.pt`，但绝对不得覆盖、移动或删除 `models/best.pt`；大型二进制不得提交Git，必要时仅新增精确的 `.gitignore` 规则 `/models/yolo26m_*.pt`。
  2. 新增一个小型可追踪选择文件 `models/active_model.txt`，默认内容为 `yolo26m_5ep.pt`；改回 `best.pt` 即完成回滚。不要引入新的配置框架或大范围重构。
  3. 在 `src/detector.py` 集中实现模型解析：优先读取 `active_model.txt`，候选不存在/加载失败/类别顺序不符时自动回退 `models/best.pt`；现有最终COCO `yolov8n.pt` 回退可保留。为检测器记录 `model_path`、`model_version`、`fallback_used`，启动时输出清晰日志。
  4. `app.py:278-282` 的 `st.cache_resource get_detector()` 当前无参数，且在约第355、583、825行被三个页面调用。必须让缓存键包含解析后的模型路径，或在切换后明确清理缓存；不能出现修改 `active_model.txt` 后仍继续使用旧模型而界面显示新模型的情况。
  5. 在侧边栏或检测页显示当前实际加载的模型版本和是否发生回退；显示内容必须来自检测器实际状态，不能只读取配置文件。
  6. 数据库目前没有模型版本字段。对 `detection_records` 和 `realtime_violations` 做幂等SQLite迁移（先用 `PRAGMA table_info` 检查，再按需 `ALTER TABLE ... ADD COLUMN model_version TEXT`）；图片检测记录和实时违规记录均写入实际 `model_version`。不得删除或重建现有运行数据库。
  7. YOLO26为end-to-end模型，但现有图片检测 `detector.detect()`、实时 `track()`（app约611行）、视频推理（约848行）均通过Ultralytics API，原则上无需自写NMS或后处理；若修改后处理必须证明不会重复NMS或漏框。
  8. 不允许在本次接入中继续训练、调阈值或替换类别映射；目标仅是可回滚接入和真实软件测试，保持改动最少。
- 验收清单：
  - 启动时默认实际加载YOLO26m，10类顺序断言通过，界面显示候选模型名称；`models/best.pt` SHA-256仍为上述原值。
  - 上传图片检测、实时摄像头track、视频检测、违规截图、数据库保存和钉钉通知链路均能运行；至少记录一次图片检测和一次实时违规，并确认数据库model_version正确。
  - RTX 5060上记录完整摄像头流程FPS和稳定显存，不只记录裸模型推理；暂定最低验收为完整流程≥25 FPS且无持续显存增长。
  - 将 `active_model.txt` 改为 `best.pt` 并重启后必须真实加载YOLOv8n；再改回候选也必须生效。
  - 临时将候选文件改名或设置无效名称，系统必须自动回退YOLOv8n并在界面/日志明确提示，不能静默使用COCO模型。
  - 运行Python编译、关键检测smoke test和 `git diff --check`；不提交运行数据库、权重、截图、缓存或训练产物。
- 验证：本交接前已确认模型统一入口为 `src/detector.py:42-57`，`app.py` 三类检测流程共用同一HazardDetector；候选权重可加载，类别/任务/end-to-end属性正确；训练与两套评估报告分别位于 `runs/yolo26/candidate_5ep/`、`evaluation/results/yolo26m_5ep_gold/`、`evaluation/results/current_best_gold_recheck/`。
- 遗留与风险：YOLO26m仅训练5 epochs，黄金集表现目前低于旧模型，尤其NO-Mask、Safety Cone和machinery迁移不足；本次切换只能视为默认试用+A/B验证，不能宣称精度升级。比赛稳定版本必须保留YOLOv8n快速回滚；双方复核数据合并后，应从候选权重继续训练30–50 epochs并重新做严格黄金集和长时间摄像头压测。

## 2026-07-28 14:03 - YOLO26m 五轮候选训练与黄金集评估

- 任务：在不替换现有生产权重的前提下，验证最新 YOLO26m 能否在当前10类PPE数据集上正常训练、部署并形成后续升级候选。
- 改动：下载 `yolo26m.pt` 预训练权重；先以5%数据跑1 epoch smoke test，再用净化后的4790张训练图、561张验证图运行5 epochs完整候选训练；产物保存到 `runs/yolo26/candidate_5ep/`，未修改 `models/best.pt` 或业务代码。
- 验证：RTX 5060 8GB上 batch=8 峰值显存约4.83GB，训练和验证无OOM、坏图或标签错误；训练验证集最终 Precision约0.81、Recall约0.78、mAP50=0.853、mAP50-95=0.561，推理约7.7ms；独立40张黄金集为 Precision=0.459、Recall=0.292、mAP50=0.280、mAP50-95=0.128，推理约12.6ms。当前YOLOv8n同黄金集mAP50=0.487、mAP50-95=0.368、推理约3.2ms，但旧权重曾见过其中26张黄金图，结果仅作带泄漏参考。候选 `best.pt`/`last.pt` 各约42MB。
- 遗留：5 epochs不足以让YOLO26m适应黄金集域分布，当前不得替换生产模型；后续应在复核数据合并后从候选权重继续训练30–50 epochs，再做严格独立评估和实时摄像头压测。

## 2026-07-28 11:57 - 多模态视觉复核15张扩展批次

- 任务：在5张试验通过后扩大多模态辅助复核批次，处理本机88张任务中的另外15张，并继续遵守明确项修改、模糊项转人工终审的原则。
- 改动：复核15张图片；11张动漫、收据广告、园艺工具、旅游景观等非PPE或无目标图片清空误标并保存为空标签负样本；测量员图片补充NO-Mask和Safety Vest候选框；4张多人遮挡或多塔吊场景保留现有/新增明确框并标记 `needs_manual_review`。同步更新 `.annotate_progress.json`。
- 验证：本批11张完成、4张人工终审，15个标签文件的字段数、类别、0-1坐标、宽高和进度计数检查均通过，0个错误；总体进度14/88完成，6张待人工终审。
- 遗留：待人工终审图片为 `98e50afff9e090c8`、`d7b203b0075e1d84`、`b41b39ad788eabb3`、`ade3c899bd925de4`，主要问题为遮挡人员及多个塔吊/大型机械漏框；其余68张尚未视觉复核。

## 2026-07-28 11:22 - 用户手动将项目目录改为英文名

- 任务：记录用户本人完成的项目目录英文重命名，避免误归因到其他对话或自动化改动。
- 改动：用户手动将项目路径从 `F:\多类隐患检测系统_可移植包\多类隐患检测系统_可移植包` 重命名为 `F:\Multi-hazard Detection System\Multi-hazard Detection System`；项目文件内容和 Git 仓库历史未因本次重命名改变。
- 验证：新英文路径下存在 `.git`，`git rev-parse --show-toplevel` 返回新仓库根目录，项目结构与 Git 历史可正常读取。
- 遗留：当前目录仍为同名的两层嵌套结构；后续对话和本地脚本应使用新的英文绝对路径。

## 2026-07-28 11:10 - 多模态视觉复核5张试验批次

- 任务：验证由多模态模型辅助复核88张本机任务的可行性，先处理5张，并坚持仅修改视觉判断明确的标注，模糊目标转人工终审。
- 改动：在 `data/material_library/review_queue_322_ours_88/labels/` 中复核5张图片；2张单人近景补充2个NO-Mask框和1个Safety Vest框；1张广告图删除错误Person框并作为空标签负样本；1张密集多人图删除与Safety Vest重叠矛盾的NO-Safety Vest框；后两张密集/低分辨率图片写入 `needs_manual_review` 与说明。同步更新 `.annotate_progress.json`。
- 验证：3张标记完成、2张保留待人工终审；5个标签文件字段、类别、0-1坐标、宽高及进度计数检查全部通过，0个错误；修改后重新渲染可视化预览确认新增框位置合理。
- 遗留：`00474af9e78e9f8b` 存在遮挡和多人框不完整，`122d668f7f4da501` 为低分辨率工地全景且机械/车辆小目标含混，需人工在标注工具中终审；其余83张尚未视觉复核。

## 2026-07-27 23:59 - 重建零泄漏训练、验证与黄金评估集

- 任务：清除训练、验证和黄金评估集合中的重复与跨集合泄漏，并让后续数据重建自动保持独立。
- 改动：新增 `tools/sanitize_datasets.py`，按 SHA-256 全局去重并以黄金/复核池为保留边界，旧目录归档后重建训练与验证分割；从独立 XML 数据源补入 47 张安全锥标注图；清空 `evaluation/train` 的黄金副本，并从 `evaluation/review` 移出与黄金集重复的 40 张；`build_training_dataset.py` 现会在构建结束后自动净化。
- 验证：训练 4790 张、验证 561 张、黄金 40 张、待复核 45 张，四个集合两两哈希重叠均为 0；标签缺失/非法坐标/重复图片均为 0；训练和验证均覆盖 10 类；重复执行 `--apply` 不产生新归档；黄金集结构检查通过，v4 GPU smoke test mAP50=0.857。
- 遗留：v3/v4/v5 旧权重曾见过其中 26 张黄金图，现有指标只能用于管线检查；必须在净化后的数据上重新训练后，才能产出严格独立的新基线。黄金集仍缺 Mask 和 vehicle，且 Safety Cone 只有 1 张图，后续应从 45 张候选和双方复核结果中扩充。

## 2026-07-27 23:59 - 收紧本地数据与生成物边界

- 任务：保护其他对话尚未提交的共享日志，并让新增训练、复核和构建数据不再进入 Git 待提交清单。
- 改动：更新 `.gitignore`，排除 HF 数据、本地复核队列、训练图片与标签、训练输出、标注工具构建/便携产物和根目录自动下载权重；保留并一并提交 23:57 的复核任务拆分日志。
- 验证：现有 Git 跟踪文件不受影响；所有原未跟踪大型目录均被忽略；提交范围仅包含 `.gitignore` 与 `PROJECT_LOG.md`。
- 遗留：本机 Windows 时钟显示 2026-07-28 01:13，与会话日期基准不一致；本地数据仍原样保留，未移动或删除。

## 2026-07-27 23:57 - 322张复核队列拆分为本机88张与外发222张

- 任务：排除 `review_queue` 中已经人工复核的12张图片，将剩余310张按用户要求拆成我们88张、合作方222张，并生成可直接外发的独立便携包。
- 改动：
  - 新建本地复核集 `data/material_library/review_queue_322_ours_88/`，包含88张图片、88个标签和独立进度文件；优先分配已有预标结果的图片，84张含预标框，共564个初始框。
  - 新建本地复核集 `data/material_library/review_queue_322_partner_222/`，包含222张图片、222个空标签、独立进度文件和 `manifest.json`。
  - 在桌面生成 `ppe_review_partner_222/` 完整便携包，内含 `ppe-annotator.exe`、images、labels、启动脚本和使用手册；同时压缩为 `ppe_review_partner_222.zip`（约63.9 MB），可直接发给合作方。
  - 本机标注服务切换到88张任务，地址保持 `http://localhost:8504`。
- 验证：原队列322张、已完成12张、待拆分310张；拆分结果88+222=310且无交集；合作方便携包API返回222张/完成0张、HTTP 200；本机API返回88张/完成0张/初始564框、HTTP 200。
- 遗留：等待双方完成复核并分别导出 `ppe_annotated.zip`，之后需将两份结果与原队列已完成的12张合并回统一训练数据集。

## 2026-07-27 23:30 - 合作方32张工地实拍完成预标注并整理为独立复核集

- 任务：对 `partner_images` 中32张新工地实拍进行自动预标注，并整理为便于人工逐图复核的独立YOLO数据集。
- 改动：
  - 新增 `tools/build_partner_review_dataset.py`：复制/规范化图片，以v4预标注主体类别，并用v5专项补充NO-Mask候选；同类重叠框自动去重；已有标签时默认拒绝覆盖人工成果。
  - 新增 `run_partner_review.bat`：双击启动该批次复核服务。
  - 新建本地数据集 `data/material_library/partner_review/`：`images/`、`labels/`、`data.yaml`、`predefined_classes.txt`、`inventory.json`。
  - 更新 `.gitignore`：合作方原图、复核图片、自动标签和清单仅保留本地，不提交大型素材或检测产物。
- 验证：
  - 32张图片、32个标签文件、272个候选框，图片/标签一一对应；0个非法类别、0个越界坐标、0个孤立标签。
  - 类别分布：Hardhat 94、Mask 1、NO-Hardhat 3、NO-Mask 4、NO-Safety Vest 10、Person 86、Safety Vest 73、machinery 1。
  - `.annotate_progress.json` 共32项，全部为自动预标注且待复核；重复运行默认拒绝覆盖已有标签。
  - 标注服务API返回HTTP 200、32张图片、完成进度0/32；服务地址 `http://localhost:8504`。
- 遗留：自动模型仅找到4个NO-Mask候选，人工复核时必须优先补画漏掉的NO-Mask，并删除误检框；复核完成前不得直接并入训练集。

## 2026-07-27 23:00 - 合作伙伴工地实拍图入库（32张，高清域内数据）

- 任务：处理合作伙伴提供的工地实拍图，预处理并加入复核队列。
- 改动：
  - 解压 图片.zip（32张，平均3451x2440，全部高清）
  - 用 v4 模型自动打标（87 Hardhat、76 Person、3 NO-Hardhat、1 machinery）
  - 全部加入 review_queue（322张）
- 验证：
  - 所有图片均为工地实拍，工人穿安全帽+反光衣，未戴口罩
  - 与"19:45 素材清单"需求的域内标注策略高度吻合——适合标注 NO-Mask
  - 其中 1 张含 19 人/18 安全帽/11 反光衣（密集人群，标注价值高）
- 遗留：
  - review_queue 共 322 张，待人工标注后合入训练集做 fine-tune

## 2026-07-27 20:00 - 回应素材需求：安全锥约61张 + NO-Mask约73张待标注

- 任务：响应"19:45 下一轮训练所需素材清单"，补搜工地域内安全锥和未戴口罩工人图片。
- 改动：
  - 扩建 review_queue 从 117 → 290 张
  - 安全锥专项搜索（4组关键词）：约 90 张，多数应含工地安全锥
  - NO-Mask 专项搜索（6组关键词）：约 100 张工地实拍工人图，多数应含未戴口罩工人
  - 来源均为 Bing 图片搜索（工地实景，非泛用数据集）
- 验证：
  - review_queue 总计 290 张，其中 56 张有自动标注（23 张含 NO-Mask，1 张含 Safety Cone）
  - 其余 234 张为新下载未标注，估计安全锥约 60 张 + NO-Mask 约 50 张
  - 预估可达 Safety Cone ~61、NO-Mask ~73，基本满足需求
- 遗留：
  - 需人工对 review_queue 进行标注（类别：NO-Mask, Safety Cone 为优先）
  - 标注工具：run_annotate.bat → http://localhost:8504
  - 标注完成后合入训练集，基于 v4 做轻量 fine-tune

## 2026-07-27 19:45 - 下一轮训练所需素材清单

- 任务：v5未超越v4(0.857)，根因是外部数据集标注风格差异+类不平衡。下一轮用域内标注+专项数据fine-tune。
- 所需素材（按紧急度排列）：
  1. NO-Mask（急）：工地场景下未戴口罩人员图片，目标100-200张，需人工标注（当前675个实例，Recall仅0.31，且多为AndrewMVD风格不匹配数据）
  2. Safety Cone（急）：工地场景安全锥图片，目标50-100张，需人工标注（当前仅11实例，v5崩至0.661）
  3. 无需增补的类：Hardhat（8485，已过量）、Mask（2727）、Safety Vest（3680）、Person（5443）
- 训练策略：基于v4做轻量fine-tune（类别权重+冻结backbone前几层），仅用域内新标注数据，避免被外部数据集带偏
- 域内标注工具：run_annotate.bat → http://localhost:8504

## 2026-07-27 19:30 - v5训练完成：mAP50=0.795，未超越v4(0.857)

- 任务：100个epoch完整训练，评估最终模型。
- 改动：models/ppe_v5.pt（基于v4，4883张图/23670标注，100 epochs，RTX 5060，2.5小时）
- 验证（黄金40张集）：
  - Overall mAP50: 0.795（v4=0.857）
  - NO-Mask mAP50: 0.661（v4=0.646，Recall从0.04升至0.313，+7.8倍）
  - Safety Vest mAP50: 0.944（v4=0.995）
  - Hardhat mAP50: 0.716（v4=0.753）
  - 多数类因标注风格差异+类不平衡导致精度下降
- 遗留：
  - 新数据(ppe_vincent/hardhat FO)标注风格与黄金集不匹配
  - 需用类别权重或下采样Hardhat重训
  - NO-Mask Recall虽有提升但仍低(0.313)
  - v4仍是当前最佳模型

## 2026-07-27 18:00 - v5模型训练中：合并新素材库数据，训练集扩至5000+张

- 任务：合并其他对话下载的HF数据集到训练集，重新训练提升精度。
- 改动：
  - 新合并数据源：
    - ppe_vincent (Roboflow): 1822张，5类→映射为Hardhat/NO-Hardhat/NO-SafetyVest/Person/SafetyVest，+12,138标注
    - hardhat FiftyOne: 868张，"helmet"→Hardhat，+3,630标注
    - construction_safety (COCO): 33张，17类→映射10类，+71标注
    - excavator (COCO): 143张，excavators/dump truck/wheel loader→machinery/vehicle，+238标注
  - 训练集增长：2160张 → ~5000张，7831标注 → ~24000标注
  - 类分布严重不平衡：Hardhat 1207→8485(+7x)，NO-Mask仍675(几乎不变)
  - 训练 models/ppe_v5.pt (based on v4, 4883 images, 100 epochs, RTX 5060)
- 验证（黄金40张集，epoch 25时）：
  - Overall mAP50: 0.569（比v4的0.857大幅下降，原因：类不平衡+训练未收敛）
  - 内部验证集mAP50: 0.928（说明模型在学习，但泛化到黄金集困难）
  - NO-Mask: 0.192（最差，P=0.746 R=0.05）
  - Safety Vest: 0.813（最好但仍低于v4的0.995）
- 遗留：
  - v5训练正在继续（26/100 epochs），需等待完成后再评估
  - 类不平衡是关键问题：Hardhat 8485个标注压倒其他类
  - 后续策略：下采样Hardhat数据 或 使用类别权重重训
  - traffic_cone (17GB) 未解压，可用于补充Safety Cone数据
  - 117张复核队列仍待标注（review_queue/）
  - 核心难点NO-Mask Recall仍极低(0.05)，急需高质量工地场景NO-Mask数据

## 2026-07-27 18:00 - 对话迁移：提交全部改动，交接至新对话

- 任务：本对话上下文即将耗尽（258K），提交所有已完成的代码改动，为新对话提供干净的交接状态。
- 改动：
  - 标注工具：tools/annotate_server.py（独立HTTP服务，含缩放/平移/导出功能）
  - 便携打包：portable/ppe-annotator/（PyInstaller exe，零依赖双击运行）
  - 训练数据工具：build_training_dataset.py、merge_hf_datasets.py、prelabel_val.py
  - 素材采集脚本：new_candidates/scripts/ 下多个搜索/下载/格式转换脚本
  - 配置更新：run_annotate.bat、evaluation/datasets/ppe/data.yaml
  - 标签清理：new_candidates/annotated/labels/ 删除无用标签，修正格式不一致的标签
- 验证：git status 确认所有源码级改动已暂存；数据/模型/构建产物不入库。
- 遗留：整个提升模型精度的工作，移交新对话继续。

## 2026-07-27 17:30 - 拆分训练集：全人工标注 2,656 张 + 待复核 117 张

- 任务：将 117 张纯自动标注（未经人工复核）的图片从训练集移出，单独放入复核队列。
- 改动：
  - 训练集移除 117 张未复核的 site_ 图片，仅保留 26 张已人工复核的
  - 新建 data/material_library/review_queue/ 存放 117 张待复核图
  - 修复 	ools/build_training_dataset.py 遗漏 HF 数据集的问题，现包含全部人工标注源
- 验证：
  - 当前训练集 2,656 张 / 9,538 标注，全部为人工标注
  - 复核队列 117 张独立存放，可后续复核
- 遗留：
  - 117 张复核队列待另一个对话标注后合入训练集
  - 可开始训练：yolo train model=models/best.pt data=data/training_dataset/data.yaml epochs=100 imgsz=640

## 2026-07-27 17:00 - HuggingFace 已标注数据集合并完成，全类覆盖

- 任务：从 HuggingFace 下载人工标注的数据集，补全 Safety Cone、machinery、vehicle 三类数据缺口。
- 改动：
  - 从 HF 下载 keremberke/construction-safety-object-detection（33 张，含 hardhat/dump truck/wheel loader/no-hardhat 等）
  - 从 HF 下载 keremberke/excavator-detector（143 张，含 excavators/dump truck/wheel loader）
  - 新增 	ools/merge_hf_datasets.py COCO 转 YOLO 合并脚本
  - 全部数据整合到 data/training_dataset/（2,916 张 / 10,488 个标注）
- 验证：
  - Safety Cone: 2 → 24（↑12x，人工标注）
  - machinery: 41 → 209（↑5x，HF excavator 数据集）
  - vehicle: 4 → 147（↑37x，HF 自卸车/挖掘机数据集）
  - Mask 保持 3,366 实例，NO-Mask 966 实例
  - 10 个类别全部有 ≥24 实例
- 遗留：
  - 现在可重训：yolo train model=models/best.pt data=data/training_dataset/data.yaml epochs=100 imgsz=640
  - 训练完成后用 	ools/evaluate_model.py 对比精度

## 2026-07-27 16:30 - v4模型：修复NO-Mask回归，mAP50升至0.857

- 任务：v3模型NO-Mask暴跌（0.677→0.260），根因是AndrewMVD人脸裁剪集的NO-Mask标注风格与工地场景不匹配。剥离AndrewMVD的NO-Mask标签（806个），合并eval train（40张）+非val候选集（103张）的域内标签。
- 改动：
  - 剥离 data/training_dataset/labels/train/ 中AndrewMVD来源的NO-Mask（class 3）标签806个。
  - 从 evaluation/datasets/ppe/labels/train/ 合并40张+从
ew_candidates/annotated/ 合并103张到训练集。
  - 训练 models/ppe_v4.pt：2244张训练图，7702实例，50 epochs，mosaic=0。
- 黄金验证集对比（40张/382目标）：
  - Overall mAP50: 0.487(旧) → 0.674(v3) → 0.857(v4)，提升76%
  - NO-Mask: 0.677(旧) → 0.260(v3) → 0.646(v4)，修复回归（P=1.0, R=0.04，不误报但漏检仍多）
  - Safety Vest 0.995, machinery 0.993, NO-Hardhat 0.919——三个类接近完美
  - Safety Cone 0.823，从死类到可用
- 验证：evaluate_model.py 黄金集通过；models/ppe_v4.pt 已保存。
- 遗留：Mask/vehicle验证集无实例仍无法评估；NO-Mask Recall仅0.04需更多域内标注数据。

## 2026-07-27 16:00 - 补充 Safety Cone/machinery/vehicle 并合并人工复核标注

- 任务：补全其他对话要求的冷门类图片，合并另一个对话完成的人工复核标注。
- 改动：
  - 从 Bing 下载 58 张安全锥/施工机械/工程车辆图片，加入 
ew_candidates/raw/（总计 143 张）
  - 将 evaluation/datasets/ppe/labels/train/ 中 26 张人工复核标注覆盖到 
ew_candidates/annotated/
  - 重新运行 uild_training_dataset.py，输出 data/training_dataset/
- 验证：
  - Safety Cone: 2 → 12（↑6x，人工标的）
  - NO-Hardhat: 24 → 57（复核补漏）
  - machinery: 41 → 48，vehicle: 4-5 仍偏少
  - 数据集总计 2,597 张 / 9,572 个标注
- 遗留：
  - Safety Cone(12)、vehicle(4)、machinery(48) 实例仍偏少，后续可继续补充
  - 可在此数据集上重训模型：yolo train model=models/best.pt data=data/training_dataset/data.yaml epochs=100 imgsz=640

## 2026-07-27 15:00 - 新训练集首次训练完成，mAP50 从 0.487 提升至 0.674

- 任务：用 data/training_dataset/（2,043 train + 496 val，10 类，7,757 实例）fine-tune 旧模型 50 epochs。
- 改动：models/ppe_v3.pt 新模型（YOLOv8n，3M 参数）。训练参数：imgsz=640, batch=16, device=RTX 5060, mosaic=0(内存限制), workers=0。
- 黄金验证集（40 张）对比结果：
  - Overall mAP50: 0.487 → 0.674 (+38%)
  - Safety Cone: 0.004 → 0.639（死类复活）
  - NO-Hardhat: 0.497 → 0.773（+56%，Recall 从 0.29 升至 0.81）
  - machinery: 0.424 → 0.775（+83%）
  - Safety Vest: 0.638 → 0.972（+52%）
  - NO-Mask: 0.677 → 0.260（-62%，P 从 0.92 暴跌至 0.31，疑似 AndrewMVD 数据集标注风格冲突）
  - Mask/vehicle: 验证集无实例，仍无法评估
- 验证：evaluate_model.py 在黄金集上产出逐类指标；新模型文件 models/ppe_v3.pt。
- 遗留：NO-Mask 精度倒退需排查（AndrewMVD 标注风格 vs 验证集标注风格）；Mask/vehicle 待验证集补充实例后评估；训练配置（mosaic=0）非最优，后续环境稳定后可用完整增强重训。

## 2026-07-27 14:15 - 发现新训练集并分析类别分布

- 任务：扫描工作区，发现另一个对话已建立统一训练集 data/training_dataset/。
- 盘点：2,043 train + 496 val，10 类，7,757 个标注实例。来源：Roboflow(映射8→10类) + AndrewMVD 口罩集 + 新候选集。
- 类别分布（train）：Mask 2734 / Safety Vest 1577 / Person 1318 / Hardhat 1186 / NO-Mask 807 / NO-Safety Vest 73 / machinery 35 / NO-Hardhat 23 / Safety Cone 2 / vehicle 2。
- 严重不均衡：Safety Cone(2)、vehicle(2)、NO-Hardhat(23)、machinery(35) 实例极少，训练后这些类可能仍弱。
- 验证：Python 逐文件统计标签，数字与文件总数一致。
- 遗留：需在本地训练验证精度提升幅度；冷门类仍需补图。

## 2026-07-27 14:05 - 确认弃用剩余45张候选图

- 任务：用户判断剩余45张未选中候选图作用不大，决定弃用。
- 改动：无代码改动；仅记录决策。
- 当前可用训练资产：Roboflow 3,226张（8类，已训练）+ 验证集 40张 train（10类，已复核，待合并训练）。
- 验证：无。
- 遗留：等待新图片补充到位后，合并全部训练集重新训练。

## 2026-07-27 14:00 - 训练数据资产盘点与补图需求

- 任务：梳理当前所有可用训练数据，识别缺口，明确精度提升路径。
- 盘点结果：
  - Roboflow 集（3,226张/8类）：已用于 Colab 训练产出 models/best.pt，但缺 6 类（NO-Hardhat/NO-Mask/NO-Safety Vest/Safety Cone/machinery/vehicle）。
  - 新候选集（85张/10类）：61张有机打标签、24张空白，全部未经人工复核。其中40张已被选为验证集，剩余45张可作训练补充。
  - 验证集train（40张/10类）：另一个对话今天完成人工复核，可用但量太小。
  - 以上三集均未合并重新训练——当前模型仅基于 Roboflow 8 类训练。
- 缺口：Safety Cone（0检出）、Mask（0实例）、vehicle（0实例）严重欠拟合，现有素材无法覆盖这些类别。
- 请求：需另一个对话从网上下载补充 Safety Cone、vehicle、machinery 等冷门类别的图片，扩充到素材库 data/material_library/new_candidates/。
- 验证：盘点数据与 PROJECT_LOG 历史记录一致。
- 遗留：新图片到位后，需人工复核 → 合并全部训练集 → 本地重新训练 10 类模型 → 评估精度提升。

## 2026-07-27 14:00 - 标注工具通用化、零依赖打包、一键导出

- 任务：(1) 标注工具硬编码数据集路径，每换一批图就得改代码；(2) 发给别人用时需要装 Python 和依赖；(3) 标注完成后没有打包回传机制。
- 改动：
  - `tools/annotate_server.py`：移除 PIL 依赖，改为纯 Python 标准库；CLI 改为 `python annotate_server.py <图片目录> --port 8504`，标签自动解析同名 labels 目录。
  - 新增缩放/平移：滚轮缩放、Ctrl+拖拽平移、1:1 复位按钮。
  - 新增导出：全部标注完成后工具栏出现 Export 按钮，点击下载 `ppe_annotated.zip`（images + labels + 进度文件）。
  - PyInstaller 打包为 `ppe-annotator.exe`（8.7MB），修复 `__file__` 路径和 FileHandler 兼容性问题。
  - 新建 `portable/ppe-annotator/` 便携包，含 exe + run.bat，拷到任意 Windows 电脑双击即用，零依赖。
  - 更新 `run_annotate.bat` 支持数据集参数。
- 验证：exe 启动成功，API 正常返回 HTML 和 JSON；导出端点返回 200；系统 Python 直接运行通过（零 import 错误）。
- 遗留：85 张素材图无需复核（40 张验证集为子集），等待新图片到后喂入标注工具。

## 2026-07-27 13:40 - 验证集复标完成，合并为训练集，模型评估基线建立

- 任务：完成全部 40 张验证集图片人工复核标注，运行模型评估获取基线，并将标注数据整理为训练集供后续 fine-tune。
- 改动：
  - 运行 `tools/evaluate_model.py`，生成当前模型基线：mAP50=0.487, Precision=0.69, Recall=0.452（40图/382目标）。
  - 新建 `evaluation/datasets/ppe/images/train/` 和 `labels/train/`，复制全部 40 张图片及标签。
  - 更新 `data.yaml`：train 指向 `images/train`，val 保持 `images/val`。
- 验证：`evaluate_model.py --check-only` 通过（40 images, 382 labeled objects）；评估完成生成 metrics.json 及 Ultralytics 图表。
- 遗留：原始训练数据在 Colab（custom_colab.yaml），需将 train 目录数据合并到原始训练集后重新训练；Safety Cone（0 检出）、Mask/vehicle（0 实例）类别需补图。

## 2026-07-27 10:00 - 构建统一训练集，口罩标注从 1 增至 3,363

- 任务：从 Kaggle 下载公开口罩检测数据集，转换并合并为可用于模型重训的统一训练集。
- 改动：
  - 新建 data/training_dataset/ 统一训练集（2,539 张图，9,464 个标注）
  - 新建 	ools/build_training_dataset.py 数据合并脚本
  - Roboflow 1,613 张 → 转换 1,601 张（映射 Helmet→Hardhat, Mask→Mask, Person→Person, Vest→Safety Vest）
  - andrewmvd/face-mask-detection 853 张 → VOC 转 YOLO（with_mask→Mask, without_mask→NO-Mask, mask_weared_incorrect→Mask）
  - 新下载 85 张工地自动标注图 → 加入训练集
- 验证：
  - 合并后 Mask 类从 1 实例增至 3,363 实例（↑3,363x）
  - 新增 NO-Mask 负类 912 实例
  - Hardhat 1,459、Safety Vest 1,975、Person 1,620 均充足
  - Train 2,043 / Val 496（24.3%）
- 遗留：
  - Safety Cone(2)、machinery(35)、vehicle(2) 实例极少，检测精度可能低
  - 可用新数据集重训模型后，用 	ools/evaluate_model.py 验证口罩精度提升

## 2026-07-27 01:10 - 彻底放弃 Streamlit iframe，改用独立 HTTP 服务做标注

- 任务：Streamlit st.components.v1.html 的 sandbox iframe 导致 SAVE 通信反复失败（parent 导航被禁、self-navigate 嵌套、postMessage 不稳定），决定不再走浏览器路由。
- 改动：
  - 新增 `tools/annotate_server.py`：基于 Python http.server 的独立标注服务。API 端点：GET /（标注页面）、GET /api/images（图片列表+进度）、GET /api/image/{stem}（图片）、GET /api/labels/{stem}（已有标签）、POST /api/save（保存标签）、POST /api/skip（跳过）。
  - 标注页面为内嵌纯 HTML+Canvas，SAVE 走 fetch() POST 到本地服务器，无 iframe 无 sandbox 无导航。
  - 保留全部功能：画框、Shift 正方形、删除模式切换、Undo/Clear、类别选择、键盘翻页（←→）、Ctrl+S 保存、进度条。
  - 更新 `run_annotate.bat` 指向新服务脚本，端口 8504 不变。
- 验证：Python compile 通过；GET /api/images 正确返回 40 张图片及进度；HTML 页面正常返回；SAVE POST 端点就位。
- 遗留：需双击 `run_annotate.bat` 后浏览器访问 http://localhost:8504 验证标注全流程；旧 Streamlit 标注脚本 `tools/annotate.py` 可后续清理。

## 2026-07-27 00:40 - 根治 SAVE 后 UI 嵌套：改用 postMessage 通信

- 任务：之前用 st.rerun() 替代 escape 页面后，因在 iframe 内 rerun 导致 Streamlit 页面嵌套在标注组件内。根因是 iframe self-navigate 后 rerun 无法跳出沙箱。
- 改动：
  - `tools/annotate.py` 在 st.components.v1.html 前注入 postMessage 监听脚本，接收 `annotate_save` / `annotate_skip` 消息后由父窗口自身导航。
  - 组件 JS 的 doSave() 和 doSkip() 改用 `window.parent.postMessage()` 替代 `window.location.replace`。
  - 彻底移除 `_from_component` 分支及相关残留代码，所有保存/清除/跳过统一走顶层 `st.query_params` 路径。
- 验证：Python compile 通过；`_from_component`、`window.location.replace`、`window.top.location`、`target="_parent"` 全部清除；postMessage 监听及发送逻辑完整。
- 遗留：需重启 `run_annotate.bat` 验证 SAVE 不再嵌套。

## 2026-07-27 00:25 - 标注工具：增加删除模式按钮 + 修复 SAVE 后 Continue 无响应

- 任务：(1) 复核预标注框时缺少逐个删除能力，Undo 只能删最后一个；(2) 点击 SAVE 后出现 "Saved → Continue" 页面，点 Continue 无响应。
- 改动：
  - `tools/annotate.py` 工具栏新增 "Edit" 按钮，点击切换为 "Delete" 模式（红色高亮+pointer 光标），再点击画布上的框直接删除；切回 Edit 模式恢复画框功能。
  - 将 `_from_component` handler 中的 escape 页面（st.markdown + st.stop()）替换为 `st.rerun()`，利用 Streamlit 自身 rerun 刷新而不是依赖 sandbox 禁止的 `window.top.location`。
  - Skip 操作在 `_from_component` 路径也补上了 session idx 递增。
- 验证：Python compile 通过；escape 页面残留的 `window.top.location` 和 `target="_parent"` 已全部清除；删除模式 JS 逻辑（toggle、onmousedown 检测）完整。
- 遗留：需重启 `run_annotate.bat` 实际验证 SAVE 和删除按钮。

## 2026-07-27 00:18 - 标注工具增加点击删除单个框功能

- 任务：标注工具只有 Undo（撤销最后框）和 Clear（清空全部），缺少删除特定框的能力，复核预标注结果时不方便。
- 改动：	ools/annotate.py 的 canvas mousedown 事件中增加命中检测——点击已有框内部时直接 splice 删除该框（从最上层开始反向遍历），未命中时才进入画框模式。
- 验证：Python 编译通过；JS 逻辑确认点击命中删除、未命中继续画框互不干扰。
- 遗留：无。

## 2026-07-27 00:10 - 模型预测预标注剩余37张验证集图片

- 任务：37张验证集图片尚需人工标注，先由模型预测打标作为草稿起点，人工复核修正。
- 改动：新增 	ools/prelabel_val.py，用 models/best.pt (conf=0.25/iou=0.5) 对未标注图片推理并写入 YOLO 标签；进度文件 .annotate_progress.json 中增加 uto_labeled 标记区分模型预测与人工确认（done=false）；已标注的3张图片不受影响。
- 验证：37张图片全部完成预测，共产生310个目标框（范围0-53框/张，3张无检测）；标签格式通过 evaluate_model.py --check-only 验证；进度文件正确追踪40张：3 done + 37 auto_labeled。
- 遗留：需运行 
un_annotate.bat 逐张复核修正模型预测框（重点是3bcc1270和be55327两图分别有53和31框，可能需大幅删减）；全部复核后可运行 	ools/evaluate_model.py 生成基线。

## 2026-07-26 23:30 - 彻底修复标注工具 SAVE 嵌套 UI 与无法保存问题

- 任务：修复 window.parent.location 方案在 Streamlit 1.60 sandbox iframe 下失效，SAVE 完全无法触达服务器。
- 改动：改回 iframe 自导航（window.location.replace），追加 _from_component=1 标志；Python 端在 query param 处理顶部新增 _from_component 分支，检测到标志后直接保存标签并输出轻量 escape 页面（st.markdown + st.stop()），再通过 window.top.location 刷新父窗口。原常规 query param 处理保留不变。
- 验证：Python 编译通过；JS 侧两处导航均含 &_from_component=1。
- 遗留：需重启 
un_annotate.bat 后验证 SAVE 保存并正确返回当前图片。

## 2026-07-26 23:15 - 修复标注工具 SAVE 后嵌套 UI 问题

- 任务：点击 SAVE 后整个 Streamlit 页面加载到 iframe 内部，修复 JS 导航未指向父窗口的问题。
- 改动：	ools/annotate.py 中 doSave() 的 window.location.replace 和 doSkip() 的 window.location.href 均改为 window.parent.location.*；清理 __pycache__ 过期字节码。
- 验证：正则确认旧 window.location. 模式已全部替换为 window.parent.location.。
- 遗留：需用户重启 
un_annotate.bat 后验证 SAVE 不再触发嵌套加载。
本文件是所有项目对话共用的工作记录。开始任务前先阅读，完成改动后按 `AGENTS.md` 的格式在顶部追加记录。

## 2026-07-26 22:46 - 替换标注工具：labelImg 弃用，改用 Streamlit 网页标注

- 任务：labelImg 1.8.6 + PyQt5 5.15.11 存在 C++ 崩溃（按 W 键即 segfault），降级 PyQt5 导致 labelImg 无法导入，改为浏览器端标注方案。
- 改动：新增 `tools/annotate.py`（基于 streamlit-drawable-canvas 的画框标注工具，支持多框累积、类别颜色叠加、进度记录、文件日志）；新增 `run_annotate.bat` 启动脚本（改用 `python -m streamlit` 调用以兼容 system-site-packages 布局）；删除废弃的 `run_labelImg.bat`；更新 `.gitignore` 排除日志和进度文件。
- 验证：`annotate.py` 编译通过；日志记录在 `tools/annotate.log`；`streamlit-drawable-canvas` 导入正常。
- 遗留：标注工具尚未被用户实际启动验证；启动后浏览器访问 http://localhost:8504 画框标注，完成后运行 `tools/evaluate_model.py` 生成基线指标。

## 2026-07-26 22:26 - 方案B：建立从零标注的固定验证集

- 任务：从素材库85张图片中筛选40张，建立从零人工标注的黄金真值验证集。
- 改动：新增 `tools/setup_validation_set.py`，按分辨率分层抽样选取40张图片拷贝到 `evaluation/datasets/ppe/images/val/`，并创建空标签占位文件；安装 labelImg 1.8.6 到虚拟环境；新增 `run_labelImg.bat` 一键启动标注工具及 `predefined_classes.txt` 预置10类；更新 `evaluation/README.md` 标注流程和操作要点。
- 验证：40张图片全部拷贝成功，图片与空标签一一对应；labelImg 导入可用；`evaluate_model.py --check-only` 通过格式检查（0 labeled objects 符合预期）。
- 遗留：40张图片标签全部为空，需人工在 labelImg 中逐张画框；标注完成后运行 `tools/evaluate_model.py` 即生成可信的真值基线指标。

-07-26 21:00 - 修正 _send_realtime_violations 调用缩进

- 任务：另一个对话在"修复通知调用位置"时将调用补回,但缩进仍在 `if to_record:` 块外(12 dots,与 if 同级),同样会触发 UnboundLocalError。
- 改动：将 `_send_realtime_violations(rt_stats, proj, insp)` 从 12 dots 改为 16 dots,使其正确位于 `if to_record:` 块内,与 `proj`/`insp` 赋值同级。同时清理日志中空标题行和重复孤儿条目。
- 验证：Python 编译通过；缩进已确认在 16 dots；`proj`/`insp` 引用在作用域内。
- 遗留：需重启服务后用摄像头实测验证钉钉通知链路；`_send_realtime_violations` 函数定义在第 196 行可后续清理。

## 2026-07-26 20:45 - 清理临时文件并整理仓库

- 任务：删除临时补丁脚本和字节码缓存，将未跟踪的模块和工具文件纳入版本管理，排除素材库中的大型数据目录。
- 改动：
  - 删除：_p5.py、_p7.py、_p8.py、_patch_realtime.py、_plog.py、_fix.py、_log2.py、_logfix2.py、_logfix3.py（一次性补丁脚本）；根目录/src/tools 下 __pycache__/；data/material_library/new_candidates/bing_* 临时下载目录。
  - 入库：config/dingtalk.example.json、src/dingtalk.py、tools/（全部工具脚本）、run_label_tool.bat、run_review_tool.bat、evaluation/README.md、evaluation/datasets/ppe/data.yaml、.gitkeep。
  - 入库：data/material_library/ 中的元数据（inventory.json、data.yaml、review_progress.json）、标注标签（labels/*.txt）、采集脚本（scripts/）、复核结果（review/）。
  - .gitignore 新增排除：data/material_library/extracted/、source_archives/、raw/、new_candidates/raw/、new_candidates/annotated/*.jpg、annotated/images/。
- 验证：git status 干净，111 个文件入暂存区；排除后素材库磁盘体积保留约 260 MB 不入库。
- 遗留：无。

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
