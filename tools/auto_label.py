# -*- coding: utf-8 -*-
"""
自动标注工具：用现有 models/best.pt 模型对 51 张新图片预打标
输出 YOLO 格式标签，人工只需复核修正
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ultralytics import YOLO
import torch

# 配置
MODEL_PATH = ROOT / "models" / "best.pt"
RAW_DIR = ROOT / "data" / "material_library" / "new_candidates" / "raw"
LABEL_DIR = ROOT / "data" / "material_library" / "new_candidates" / "annotated" / "labels"
IMAGE_DIR = ROOT / "data" / "material_library" / "new_candidates" / "annotated" / "images"
LABEL_DIR.mkdir(parents=True, exist_ok=True)
IMAGE_DIR.mkdir(parents=True, exist_ok=True)

# 加载模型
device = 0 if torch.cuda.is_available() else "cpu"
model = YOLO(str(MODEL_PATH))
print(f"模型加载完成 | 设备: {device} | 类别: {model.names}")

# 获取所有新图片
images = sorted(RAW_DIR.glob("*.jpg"))
print(f"待标注图片: {len(images)} 张")

stats = {}
for img_path in images:
    # 推理
    results = model(str(img_path), conf=0.25, iou=0.5, device=device)
    result = results[0]

    # 保存标签 (YOLO格式)
    label_path = LABEL_DIR / f"{img_path.stem}.txt"
    boxes = result.boxes
    if boxes is not None and len(boxes) > 0:
        with open(label_path, "w") as f:
            for box in boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                # YOLO格式: class_id x_center y_center width height
                xywh = box.xywhn[0].tolist()
                f.write(f"{cls_id} {xywh[0]:.6f} {xywh[1]:.6f} {xywh[2]:.6f} {xywh[3]:.6f}\n")
                stats[cls_id] = stats.get(cls_id, 0) + 1
    else:
        # 无检测结果 → 空标签文件
        label_path.write_text("")

    # 复制图片
    from PIL import Image
    img = Image.open(img_path).convert("RGB")
    img.save(IMAGE_DIR / f"{img_path.stem}.jpg", "JPEG", quality=92)

    cls_counts = {}
    if boxes is not None:
        for box in boxes:
            name = model.names[int(box.cls[0])]
            cls_counts[name] = cls_counts.get(name, 0) + 1
    detail = ", ".join(f"{k}={v}" for k, v in cls_counts.items()) if cls_counts else "无检测"
    print(f"  {img_path.stem[:20]:20s} → {detail}")

print(f"\n完成！标签保存至: {LABEL_DIR}")
print(f"类别统计:")
for cls_id, count in sorted(stats.items()):
    print(f"  {model.names[cls_id]}: {count} 个目标")
total_objs = sum(stats.values())
print(f"  总计: {total_objs} 个目标")
