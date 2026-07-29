# 项目共享日志


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
