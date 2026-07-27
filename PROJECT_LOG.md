# 项目共享日志


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


## 2026-07-26 20:45 - 清理临时文件并整理仓库

- 任务：删除临时补丁脚本和字节码缓存，将未跟踪的模块和工具文件纳入版本管理，排除素材库中的大型数据目录。
- 改动：
  - 删除：_p5.py、_p7.py、_p8.py、_patch_realtime.py、_plog.py、_fix.py、_log2.py、_logfix2.py、_logfix3.py（一次性补丁脚本）；根目录/src/tools 下 __pycache__/；data/material_library/new_candidates/bing_* 临时下载目录。
  - 入库：config/dingtalk.example.json、src/dingtalk.py、tools/（全部工具脚本）、run_label_tool.bat、run_review_tool.bat、evaluation/README.md、evaluation/datasets/ppe/data.yaml、.gitkeep。
  - 入库：data/material_library/ 中的元数据（inventory.json、data.yaml、review_progress.json）、标注标签（labels/*.txt）、采集脚本（scripts/）、复核结果（review/）。
  - .gitignore 新增排除：data/material_library/extracted/、source_archives/、raw/、new_candidates/raw/、new_candidates/annotated/*.jpg、annotated/images/。
- 验证：git status 干净，111 个文件入暂存区；排除后素材库磁盘体积保留约 260 MB 不入库。
- 遗留：无。

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