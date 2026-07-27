# -*- coding: utf-8 -*-
"""Build a review-ready YOLO dataset from partner-provided site images."""
from __future__ import annotations

import argparse
import gc
import json
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path

from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "data" / "material_library" / "partner_images"
DEFAULT_OUTPUT = ROOT / "data" / "material_library" / "partner_review"
DEFAULT_PRIMARY_MODEL = ROOT / "models" / "ppe_v4.pt"
DEFAULT_NOMASK_MODEL = ROOT / "models" / "ppe_v5.pt"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
CLASSES = [
    "Hardhat", "Mask", "NO-Hardhat", "NO-Mask", "NO-Safety Vest",
    "Person", "Safety Cone", "Safety Vest", "machinery", "vehicle",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Copy partner images into a review dataset and pre-label them."
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--primary-model", type=Path, default=DEFAULT_PRIMARY_MODEL)
    parser.add_argument("--nomask-model", type=Path, default=DEFAULT_NOMASK_MODEL)
    parser.add_argument("--primary-conf", type=float, default=0.15)
    parser.add_argument("--nomask-conf", type=float, default=0.05)
    parser.add_argument("--iou", type=float, default=0.5)
    parser.add_argument("--device", default="0")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing draft labels. Never use after manual review has started.",
    )
    return parser.parse_args()


def box_iou(a: list[float], b: list[float]) -> float:
    ax1, ay1 = a[0] - a[2] / 2, a[1] - a[3] / 2
    ax2, ay2 = a[0] + a[2] / 2, a[1] + a[3] / 2
    bx1, by1 = b[0] - b[2] / 2, b[1] - b[3] / 2
    bx2, by2 = b[0] + b[2] / 2, b[1] + b[3] / 2
    intersection = max(0.0, min(ax2, bx2) - max(ax1, bx1)) * max(
        0.0, min(ay2, by2) - max(ay1, by1)
    )
    union = a[2] * a[3] + b[2] * b[3] - intersection
    return intersection / union if union > 0 else 0.0


def merge_predictions(predictions: list[dict]) -> list[dict]:
    kept: list[dict] = []
    for prediction in sorted(predictions, key=lambda item: item["conf"], reverse=True):
        duplicate = any(
            prediction["class"] == existing["class"]
            and box_iou(prediction["coords"], existing["coords"]) >= 0.6
            for existing in kept
        )
        if not duplicate:
            kept.append(prediction)
    return sorted(kept, key=lambda item: (item["class"], -item["conf"]))


def predict(
    model_path: Path,
    image_paths: list[Path],
    conf: float,
    iou: float,
    device: str,
    classes: list[int] | None = None,
) -> dict[str, list[dict]]:
    model = YOLO(str(model_path))
    predictions: dict[str, list[dict]] = {path.stem: [] for path in image_paths}
    results = model.predict(
        source=[str(path) for path in image_paths],
        conf=conf,
        iou=iou,
        device=device,
        classes=classes,
        stream=True,
        verbose=False,
    )
    for image_path, result in zip(image_paths, results, strict=True):
        stem = image_path.stem
        if result.boxes is None:
            continue
        class_ids = result.boxes.cls.cpu().tolist()
        confidences = result.boxes.conf.cpu().tolist()
        coordinates = result.boxes.xywhn.cpu().tolist()
        predictions[stem].extend(
            {
                "class": int(class_id),
                "conf": float(confidence),
                "coords": [float(value) for value in coords],
            }
            for class_id, confidence, coords in zip(
                class_ids, confidences, coordinates, strict=True
            )
        )
    del model
    gc.collect()
    return predictions


def main() -> None:
    args = parse_args()
    source = args.source.resolve()
    output = args.output.resolve()
    image_dir = output / "images"
    label_dir = output / "labels"

    image_paths = sorted(
        path for path in source.iterdir() if path.suffix.lower() in IMAGE_SUFFIXES
    )
    if not image_paths:
        raise SystemExit(f"No images found in {source}")
    if not args.primary_model.exists() or not args.nomask_model.exists():
        raise SystemExit("Required model file is missing.")

    existing_labels = list(label_dir.glob("*.txt")) if label_dir.exists() else []
    if existing_labels and not args.force:
        raise SystemExit(
            f"Found {len(existing_labels)} existing labels in {label_dir}. "
            "Refusing to overwrite possible manual work; pass --force only for a fresh rebuild."
        )

    image_dir.mkdir(parents=True, exist_ok=True)
    label_dir.mkdir(parents=True, exist_ok=True)
    if args.force:
        for label_path in label_dir.glob("*.txt"):
            label_path.unlink()

    copied_images: list[Path] = []
    for source_path in image_paths:
        destination = image_dir / f"{source_path.stem}.jpg"
        if source_path.suffix.lower() == ".jpg":
            shutil.copy2(source_path, destination)
        else:
            from PIL import Image

            with Image.open(source_path) as image:
                image.convert("RGB").save(destination, quality=95)
        copied_images.append(destination)

    print(f"Primary pre-label model: {args.primary_model}")
    primary = predict(
        args.primary_model, copied_images, args.primary_conf, args.iou, args.device
    )
    print(f"NO-Mask supplement model: {args.nomask_model}")
    nomask = predict(
        args.nomask_model,
        copied_images,
        args.nomask_conf,
        args.iou,
        args.device,
        classes=[3],
    )

    progress = {}
    class_counts: Counter[int] = Counter()
    inventory_images = []
    total_boxes = 0
    for image_path in copied_images:
        merged = merge_predictions(primary[image_path.stem] + nomask[image_path.stem])
        lines = []
        for prediction in merged:
            class_id = prediction["class"]
            x, y, w, h = prediction["coords"]
            lines.append(f"{class_id} {x:.6f} {y:.6f} {w:.6f} {h:.6f}")
            class_counts[class_id] += 1
        (label_dir / f"{image_path.stem}.txt").write_text(
            "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8"
        )
        progress[image_path.stem] = {
            "done": False,
            "count": len(lines),
            "auto_labeled": True,
        }
        inventory_images.append(
            {"filename": image_path.name, "status": "pending", "boxes": len(lines)}
        )
        total_boxes += len(lines)

    (label_dir / ".annotate_progress.json").write_text(
        json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output / "predefined_classes.txt").write_text(
        "\n".join(CLASSES) + "\n", encoding="utf-8"
    )
    (output / "data.yaml").write_text(
        "path: .\ntrain: images\nval: images\n\n"
        f"nc: {len(CLASSES)}\n"
        "names:\n"
        + "".join(f"  {index}: {name}\n" for index, name in enumerate(CLASSES)),
        encoding="utf-8",
    )
    inventory = {
        "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "description": "Partner site images pre-labeled for manual review",
        "source": str(source),
        "total_images": len(copied_images),
        "total_boxes": total_boxes,
        "primary_model": str(args.primary_model),
        "nomask_model": str(args.nomask_model),
        "primary_conf": args.primary_conf,
        "nomask_conf": args.nomask_conf,
        "class_counts": {
            CLASSES[index]: class_counts[index] for index in range(len(CLASSES))
        },
        "images": inventory_images,
    }
    (output / "inventory.json").write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"Dataset ready: {output}")
    print(f"Images: {len(copied_images)}, draft boxes: {total_boxes}")
    for index, class_name in enumerate(CLASSES):
        if class_counts[index]:
            print(f"  {class_name}: {class_counts[index]}")
    print(f'Run: run_annotate.bat "{image_dir}"')


if __name__ == "__main__":
    main()
