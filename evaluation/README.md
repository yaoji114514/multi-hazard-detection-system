# 模型精度验证基线

## 当前状态

已从素材库中筛选 40 张图片放入 `images/val/`，空标签占位文件在 `labels/val/`。
这些标签尚未标注，必须从零人工画框后才能用于精度评估。

## 方案 B：从零人工标注（当前流程）

### 启动标注工具

双击 `run_labelImg.bat`，或在终端执行：

```powershell
.\.venv\Scripts\labelImg.exe evaluation\datasets\ppe\images\val evaluation\datasets\ppe\predefined_classes.txt
```

### labelImg 操作要点

| 快捷键 | 功能 |
|---|---|
| `W` | 创建矩形框 |
| `D` | 下一张图片 |
| `A` | 上一张图片 |
| `Ctrl+S` | 保存当前标注 |
| `Del` | 删除选中框 |

启动后在界面中：
1. 点击左侧 **Open Dir**，选择 `evaluation/datasets/ppe/images/val/`
2. 点击左侧 **Change Save Dir**，选择 `evaluation/datasets/ppe/labels/val/`
3. 确认格式为 **YOLO**（底部状态栏显示）
4. 标注完成后切换到下一张，labelImg 自动保存

类别已预置在 `predefined_classes.txt`，与模型 10 类一致。

### 标注规范

- 框紧贴目标边缘，不画得太松
- 仅框可见部分，被遮挡超过 50% 的目标跳过
- 小于 10x10 像素的目标可不标
- 即使图片中无任何目标，也保存空标签（labelImg 会在切换图片时自动保存）

### 标注完成后的评估

```powershell
.\.venv\Scripts\python.exe tools\evaluate_model.py --check-only   # 检查格式
.\.venv\Scripts\python.exe tools\evaluate_model.py                # 生成基线指标
```

---

## 类别编号

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

## 检查标注

```powershell
.\.venv\Scripts\python.exe tools\evaluate_model.py --check-only
```

工具会检查图片和标签是否一一对应、每行是否为 YOLO 格式、类别编号是否越界、坐标是否在 `0-1` 范围内。

## 运行基线评估

```powershell
.\.venv\Scripts\python.exe tools\evaluate_model.py
```

默认使用 `models/best.pt`、`640` 输入尺寸和 GPU（可用时）。结果写入 `evaluation/results/<时间戳>/metrics.json`，同时保留 Ultralytics 生成的混淆矩阵和曲线。报告包含总体及逐类别的 Precision、Recall、F1、mAP50 和 mAP50-95。

对比模型时应使用完全相同的验证集和参数。例如：

```powershell
.\.venv\Scripts\python.exe tools\evaluate_model.py --model models\candidate.pt --name candidate
```

不能仅凭单张图片观感或检测数量宣称精度提升。关键隐患类别应同时查看召回率、误报情况和混淆矩阵。
