"""Validate a YOLO detection model against the project's fixed PPE dataset."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from ultralytics import YOLO
from ultralytics.utils import YAML


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = ROOT / "models" / "best.pt"
DEFAULT_DATA = ROOT / "evaluation" / "datasets" / "ppe" / "data.yaml"
IMAGE_SUFFIXES = {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check labels and evaluate PPE model accuracy.")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL, help="YOLO weights path")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA, help="YOLO dataset YAML")
    parser.add_argument("--imgsz", type=int, default=640, help="Validation image size")
    parser.add_argument("--conf", type=float, default=0.001, help="Validation confidence threshold")
    parser.add_argument("--iou", type=float, default=0.7, help="NMS IoU threshold")
    parser.add_argument("--device", default=None, help="Device such as 0 or cpu (auto by default)")
    parser.add_argument("--workers", type=int, default=0, help="Validation data-loader workers")
    parser.add_argument("--name", default=None, help="Result directory name")
    parser.add_argument("--check-only", action="store_true", help="Only validate dataset structure and labels")
    return parser.parse_args()


def resolve_dataset(data_file: Path) -> tuple[Path, Path, dict[int, str]]:
    data_file = data_file.resolve()
    if not data_file.is_file():
        raise ValueError(f"Dataset YAML does not exist: {data_file}")

    data = YAML.load(data_file)
    names_value = data.get("names")
    if isinstance(names_value, list):
        names = dict(enumerate(names_value))
    elif isinstance(names_value, dict):
        names = {int(key): str(value) for key, value in names_value.items()}
    else:
        raise ValueError("Dataset YAML must contain a names list or mapping.")

    dataset_root = Path(data.get("path", "."))
    if not dataset_root.is_absolute():
        dataset_root = (data_file.parent / dataset_root).resolve()
    val_value = data.get("val")
    if not isinstance(val_value, str):
        raise ValueError("This baseline expects val to be one image directory.")
    image_dir = (dataset_root / val_value).resolve()
    label_dir = dataset_root / "labels" / Path(val_value).name
    return image_dir, label_dir.resolve(), names


def check_dataset(data_file: Path) -> tuple[int, int, dict[int, str]]:
    image_dir, label_dir, names = resolve_dataset(data_file)
    if not image_dir.is_dir() or not label_dir.is_dir():
        raise ValueError(f"Validation directories are missing: {image_dir} / {label_dir}")

    images = sorted(path for path in image_dir.rglob("*") if path.suffix.lower() in IMAGE_SUFFIXES)
    if not images:
        raise ValueError(f"No validation images found in: {image_dir}")

    expected_labels = {image.relative_to(image_dir).with_suffix(".txt") for image in images}
    actual_labels = {label.relative_to(label_dir) for label in label_dir.rglob("*.txt")}
    errors = []
    for relative in sorted(expected_labels - actual_labels):
        errors.append(f"Missing label: {relative}")
    for relative in sorted(actual_labels - expected_labels):
        errors.append(f"Label has no matching image: {relative}")

    object_count = 0
    for relative in sorted(expected_labels & actual_labels):
        label_path = label_dir / relative
        for line_number, raw_line in enumerate(label_path.read_text(encoding="utf-8-sig").splitlines(), 1):
            line = raw_line.strip()
            if not line:
                continue
            fields = line.split()
            if len(fields) != 5:
                errors.append(f"{relative}:{line_number}: expected 5 fields, got {len(fields)}")
                continue
            try:
                class_value = float(fields[0])
                coordinates = [float(value) for value in fields[1:]]
            except ValueError:
                errors.append(f"{relative}:{line_number}: contains a non-numeric value")
                continue
            class_id = int(class_value)
            if class_value != class_id or class_id not in names:
                errors.append(f"{relative}:{line_number}: invalid class id {fields[0]}")
            if any(value < 0 or value > 1 for value in coordinates):
                errors.append(f"{relative}:{line_number}: coordinates must be within 0-1")
            if coordinates[2] <= 0 or coordinates[3] <= 0:
                errors.append(f"{relative}:{line_number}: width and height must be greater than 0")
            object_count += 1

    if errors:
        preview = "\n".join(f"  - {error}" for error in errors[:30])
        remainder = f"\n  ... and {len(errors) - 30} more" if len(errors) > 30 else ""
        raise ValueError(f"Dataset check failed with {len(errors)} error(s):\n{preview}{remainder}")
    return len(images), object_count, names


def check_model_classes(model: YOLO, dataset_names: dict[int, str]) -> None:
    model_names = {int(key): str(value) for key, value in model.names.items()}
    if model_names != dataset_names:
        raise ValueError(
            "Model classes do not match the validation dataset.\n"
            f"Model: {model_names}\nDataset: {dataset_names}"
        )


def build_report(metrics, args: argparse.Namespace, image_count: int, object_count: int) -> dict:
    overall = metrics.results_dict
    precision = float(overall["metrics/precision(B)"])
    recall = float(overall["metrics/recall(B)"])
    per_class = {}
    for metric_index, class_id in enumerate(metrics.box.ap_class_index):
        p, r, ap50, ap = (float(value) for value in metrics.box.class_result(metric_index))
        per_class[str(int(class_id))] = {
            "name": str(metrics.names[int(class_id)]),
            "precision": p,
            "recall": r,
            "f1": 2 * p * r / (p + r) if p + r else 0.0,
            "mAP50": ap50,
            "mAP50-95": ap,
        }
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "model": str(args.model.resolve()),
        "dataset": str(args.data.resolve()),
        "parameters": {"imgsz": args.imgsz, "conf": args.conf, "iou": args.iou, "device": args.device},
        "dataset_summary": {"images": image_count, "objects": object_count},
        "overall": {
            "precision": precision,
            "recall": recall,
            "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
            "mAP50": float(overall["metrics/mAP50(B)"]),
            "mAP50-95": float(overall["metrics/mAP50-95(B)"]),
        },
        "per_class": per_class,
        "ultralytics_output": str(metrics.save_dir.resolve()),
    }


def main() -> int:
    args = parse_args()
    try:
        image_count, object_count, names = check_dataset(args.data)
        print(f"Dataset check passed: {image_count} images, {object_count} labeled objects.")
        if args.check_only:
            return 0
        if not args.model.is_file():
            raise ValueError(f"Model does not exist: {args.model.resolve()}")

        model = YOLO(str(args.model.resolve()))
        check_model_classes(model, names)
        run_name = args.name or datetime.now().strftime("%Y%m%d_%H%M%S")
        metrics = model.val(
            data=str(args.data.resolve()),
            split="val",
            imgsz=args.imgsz,
            conf=args.conf,
            iou=args.iou,
            device=args.device,
            workers=args.workers,
            project=str(ROOT / "evaluation" / "results"),
            name=run_name,
            plots=True,
        )
        report = build_report(metrics, args, image_count, object_count)
        report_path = Path(metrics.save_dir) / "metrics.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Metrics report: {report_path.resolve()}")
        return 0
    except (OSError, ValueError, KeyError) as error:
        print(f"ERROR: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
