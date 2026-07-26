# 模型精度验证基线

本目录用于建立固定、可重复的模型精度基线，不改变应用当前的检测行为。

## 1. 准备验证集

从真实使用场景中选取约 50-200 张有代表性的图片，优先覆盖远距离、小目标、遮挡、逆光、多人以及 `NO-Hardhat`、`NO-Safety Vest` 等关键隐患。验证集一旦用于模型对比，应保持固定；新收集的数据另行加入训练集或下一版验证集。

将图片放入：

```text
evaluation/datasets/ppe/images/val/
```

使用 CVAT、Label Studio 或 labelImg 按 YOLO 检测格式标注，并将同名 `.txt` 文件放入：

```text
evaluation/datasets/ppe/labels/val/
```

每行标注格式为：

```text
class_id center_x center_y width height
```

后四项是相对图片宽高归一化到 `0-1` 的数值。即使图片中没有任何目标，也要创建同名空 `.txt` 文件，明确表示它是负样本。

类别编号必须与当前 `models/best.pt` 一致：

| ID | 类别 |
|---:|---|
| 0 | Hardhat |
| 1 | Mask |
| 2 | NO-Hardhat |
| 3 | NO-Mask |
| 4 | NO-Safety Vest |
| 5 | Person |
| 6 | Safety Cone |
| 7 | Safety Vest |
| 8 | machinery |
| 9 | vehicle |

验证图片和标注属于本地数据，已被 `.gitignore` 排除，不会提交到仓库。

## 2. 检查标注

```powershell
.\.venv\Scripts\python.exe tools\evaluate_model.py --check-only
```

工具会检查图片和标签是否一一对应、每行是否为 YOLO 格式、类别编号是否越界、坐标是否在 `0-1` 范围内。

## 3. 运行基线评估

```powershell
.\.venv\Scripts\python.exe tools\evaluate_model.py
```

默认使用 `models/best.pt`、`640` 输入尺寸和 GPU（可用时）。结果写入 `evaluation/results/<时间戳>/metrics.json`，同时保留 Ultralytics 生成的混淆矩阵和曲线。报告包含总体及逐类别的 Precision、Recall、F1、mAP50 和 mAP50-95。

对比模型时应使用完全相同的验证集和参数。例如：

```powershell
.\.venv\Scripts\python.exe tools\evaluate_model.py --model models\candidate.pt --name candidate
```

不能仅凭单张图片观感或检测数量宣称精度提升。关键隐患类别应同时查看召回率、误报情况和混淆矩阵。
