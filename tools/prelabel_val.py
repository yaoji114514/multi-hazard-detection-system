# -*- coding: utf-8 -*-
"""Pre-label remaining validation images using the existing model.

Outputs YOLO-format labels so the annotate tool can show draft boxes.
Only processes images that are NOT already marked done in .annotate_progress.json.
"""
from __future__ import annotations

import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ultralytics import YOLO

IMG_DIR = ROOT / "evaluation" / "datasets" / "ppe" / "images" / "val"
LBL_DIR = ROOT / "evaluation" / "datasets" / "ppe" / "labels" / "val"
PROGRESS_FILE = LBL_DIR / ".annotate_progress.json"
MODEL_PATH = ROOT / "models" / "best.pt"

CONF = 0.25
IOU = 0.5

def main():
    progress = json.loads(PROGRESS_FILE.read_text(encoding="utf-8")) if PROGRESS_FILE.exists() else {}
    done = {k for k, v in progress.items() if v.get("done")}

    images = sorted(IMG_DIR.glob("*.jpg"))
    todo = [img for img in images if img.stem not in done]

    if not todo:
        print("All images already annotated.")
        return

    print(f"Loading model: {MODEL_PATH}")
    model = YOLO(str(MODEL_PATH))
    print(f"Pre-labeling {len(todo)} images (model predicted boxes as draft)...")

    total_boxes = 0
    for img_path in todo:
        results = model(str(img_path), conf=CONF, iou=IOU, verbose=False)
        boxes = results[0].boxes

        label_lines = []
        if boxes is not None and len(boxes) > 0:
            for box in boxes:
                cls_id = int(box.cls[0])
                xywh = box.xywhn[0].tolist()
                label_lines.append(f"{cls_id} {xywh[0]:.6f} {xywh[1]:.6f} {xywh[2]:.6f} {xywh[3]:.6f}")
            total_boxes += len(boxes)

        (LBL_DIR / f"{img_path.stem}.txt").write_text("\n".join(label_lines) + "\n", encoding="utf-8")
        progress[img_path.stem] = {"done": False, "count": len(label_lines), "auto_labeled": True}
        print(f"  {img_path.stem:20s} -> {len(label_lines)} boxes")

    PROGRESS_FILE.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDone. {total_boxes} total predicted boxes across {len(todo)} images.")
    print("Now open the annotate tool to review and correct each image.")

if __name__ == "__main__":
    main()
