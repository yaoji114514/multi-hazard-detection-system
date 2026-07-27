#!/usr/bin/env python3
"""Deduplicate PPE datasets and keep evaluation images out of training.

Run without --apply to preview the split. With --apply, the previous training
and evaluation workspaces are moved to archive/ before the clean split is
installed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tarfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRAIN_ROOT = ROOT / "data" / "training_dataset"
EVAL_ROOT = ROOT / "evaluation" / "datasets" / "ppe"
CONE_ARCHIVE = (
    ROOT
    / "data"
    / "material_library"
    / "hf_datasets"
    / "traffic_cone"
    / "cone_dataset.tar.gz"
)
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


@dataclass(frozen=True)
class Sample:
    digest: str
    name: str
    suffix: str
    label_text: str
    classes: frozenset[int]
    box_count: int
    source_path: Path | None
    image_bytes: bytes | None
    from_val: bool


def image_digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def parse_label(text: str, source: str) -> tuple[str, frozenset[int], int]:
    normalized = []
    classes = set()
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 5:
            raise ValueError(f"{source}:{line_number}: expected 5 columns")
        try:
            class_id = int(parts[0])
            values = [float(value) for value in parts[1:]]
        except ValueError as exc:
            raise ValueError(f"{source}:{line_number}: invalid number") from exc
        if not 0 <= class_id <= 9:
            raise ValueError(f"{source}:{line_number}: class {class_id} is invalid")
        if any(value < 0 or value > 1 for value in values):
            raise ValueError(f"{source}:{line_number}: coordinate outside [0, 1]")
        if values[2] <= 0 or values[3] <= 0:
            raise ValueError(f"{source}:{line_number}: box size must be positive")
        normalized.append(
            f"{class_id} " + " ".join(f"{value:.6f}" for value in values)
        )
        classes.add(class_id)
    return "\n".join(normalized), frozenset(classes), len(normalized)


def iter_images(directory: Path):
    if not directory.exists():
        return
    for path in sorted(directory.iterdir()):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            yield path


def load_training_samples() -> list[Sample]:
    samples = []
    for split in ("train", "val"):
        image_dir = TRAIN_ROOT / "images" / split
        label_dir = TRAIN_ROOT / "labels" / split
        for image_path in iter_images(image_dir):
            label_path = label_dir / f"{image_path.stem}.txt"
            if not label_path.exists():
                raise FileNotFoundError(f"Missing label for {image_path}")
            label_text, classes, box_count = parse_label(
                label_path.read_text(encoding="utf-8-sig"), str(label_path)
            )
            samples.append(
                Sample(
                    digest=image_digest(image_path),
                    name=image_path.name,
                    suffix=image_path.suffix.lower(),
                    label_text=label_text,
                    classes=classes,
                    box_count=box_count,
                    source_path=image_path,
                    image_bytes=None,
                    from_val=split == "val",
                )
            )
    return samples


def load_hashes(directory: Path) -> dict[str, list[Path]]:
    hashes: dict[str, list[Path]] = defaultdict(list)
    for path in iter_images(directory):
        hashes[image_digest(path)].append(path)
    return hashes


def load_cone_samples() -> list[Sample]:
    if not CONE_ARCHIVE.exists():
        raise FileNotFoundError(f"Missing cone archive: {CONE_ARCHIVE}")
    samples = []
    with tarfile.open(CONE_ARCHIVE, "r:gz") as archive:
        members = {member.name: member for member in archive.getmembers() if member.isfile()}
        images_by_stem: dict[str, str] = {}
        for name in members:
            if Path(name).suffix.lower() in IMAGE_EXTENSIONS:
                images_by_stem.setdefault(Path(name).stem, name)
        for xml_name in sorted(name for name in members if name.endswith(".xml")):
            xml_data = archive.extractfile(members[xml_name]).read()
            root = ET.fromstring(xml_data)
            filename = root.findtext("filename") or Path(xml_name).stem
            image_name = images_by_stem.get(Path(filename).stem)
            if not image_name:
                raise FileNotFoundError(f"No image for {xml_name}")
            width = int(root.findtext("size/width", "0"))
            height = int(root.findtext("size/height", "0"))
            if width <= 0 or height <= 0:
                raise ValueError(f"Invalid image size in {xml_name}")
            lines = []
            classes = set()
            for obj in root.findall("object"):
                class_name = (obj.findtext("name") or "").strip().lower()
                class_id = {"trafficcone": 6, "person": 5}.get(class_name)
                if class_id is None:
                    continue
                box = obj.find("bndbox")
                if box is None:
                    continue
                xmin = max(0.0, float(box.findtext("xmin", "0")))
                ymin = max(0.0, float(box.findtext("ymin", "0")))
                xmax = min(float(width), float(box.findtext("xmax", "0")))
                ymax = min(float(height), float(box.findtext("ymax", "0")))
                if xmin >= xmax or ymin >= ymax:
                    continue
                values = (
                    ((xmin + xmax) / 2) / width,
                    ((ymin + ymax) / 2) / height,
                    (xmax - xmin) / width,
                    (ymax - ymin) / height,
                )
                lines.append(
                    f"{class_id} " + " ".join(f"{value:.6f}" for value in values)
                )
                classes.add(class_id)
            if not lines:
                continue
            image_bytes = archive.extractfile(members[image_name]).read()
            digest = hashlib.sha256(image_bytes).hexdigest()
            samples.append(
                Sample(
                    digest=digest,
                    name=f"cone_{Path(image_name).name}",
                    suffix=Path(image_name).suffix.lower(),
                    label_text="\n".join(lines),
                    classes=frozenset(classes),
                    box_count=len(lines),
                    source_path=None,
                    image_bytes=image_bytes,
                    from_val=False,
                )
            )
    unique: dict[str, Sample] = {}
    for sample in samples:
        current = unique.get(sample.digest)
        if current is None or sample.box_count > current.box_count:
            unique[sample.digest] = sample
    return list(unique.values())


def choose_representatives(samples: list[Sample]) -> tuple[dict[str, Sample], int, int]:
    groups: dict[str, list[Sample]] = defaultdict(list)
    for sample in samples:
        groups[sample.digest].append(sample)
    representatives = {}
    duplicate_files = 0
    label_conflicts = 0
    for digest, group in groups.items():
        duplicate_files += len(group) - 1
        if len({sample.label_text for sample in group}) > 1:
            label_conflicts += 1
        chosen = sorted(
            group,
            key=lambda sample: (-sample.box_count, not sample.from_val, sample.name),
        )[0]
        representatives[digest] = replace(
            chosen, from_val=any(sample.from_val for sample in group)
        )
    return representatives, duplicate_files, label_conflicts


def class_presence(samples: dict[str, Sample], digests: set[str]) -> Counter:
    counts = Counter()
    for digest in digests:
        counts.update(samples[digest].classes)
    return counts


def build_plan() -> dict:
    raw_samples = load_training_samples()
    current_train_hashes = {sample.digest for sample in raw_samples if not sample.from_val}
    current_val_hashes = {sample.digest for sample in raw_samples if sample.from_val}
    samples, duplicate_files, label_conflicts = choose_representatives(raw_samples)
    gold_hashes = set(load_hashes(EVAL_ROOT / "images" / "val"))
    review_hashes = set(load_hashes(EVAL_ROOT / "images" / "review"))
    eval_train_hashes = set(load_hashes(EVAL_ROOT / "images" / "train"))
    reserved_hashes = gold_hashes | review_hashes
    excluded_reserved = set(samples) & reserved_hashes
    samples = {
        digest: sample
        for digest, sample in samples.items()
        if digest not in reserved_hashes
    }
    cone_added = 0
    for sample in load_cone_samples():
        if sample.digest not in reserved_hashes and sample.digest not in samples:
            samples[sample.digest] = sample
            cone_added += 1
    if not samples:
        raise RuntimeError("No training samples remain")

    val_hashes = {
        digest for digest, sample in samples.items() if sample.from_val
    }
    totals = class_presence(samples, set(samples))
    targets = {
        class_id: min(50, max(1, round(totals[class_id] * 0.10)))
        if totals[class_id] >= 2
        else 0
        for class_id in range(10)
    }
    val_counts = class_presence(samples, val_hashes)
    for class_id in sorted(range(10), key=lambda value: (totals[value], value)):
        while val_counts[class_id] < targets[class_id]:
            candidates = [
                sample
                for digest, sample in samples.items()
                if digest not in val_hashes and class_id in sample.classes
            ]
            if not candidates:
                break
            def gain(sample: Sample) -> int:
                return sum(
                    max(targets[value] - val_counts[value], 0)
                    for value in sample.classes
                )
            chosen = sorted(candidates, key=lambda sample: (-gain(sample), sample.digest))[0]
            val_hashes.add(chosen.digest)
            val_counts.update(chosen.classes)

    train_hashes = set(samples) - val_hashes
    train_counts = class_presence(samples, train_hashes)
    review_gold_overlap = gold_hashes & review_hashes
    changes_needed = bool(
        duplicate_files
        or excluded_reserved
        or cone_added
        or current_train_hashes != train_hashes
        or current_val_hashes != val_hashes
        or eval_train_hashes
        or review_gold_overlap
    )
    for class_id in range(10):
        if totals[class_id] and (not train_counts[class_id] or not val_counts[class_id]):
            raise RuntimeError(
                f"Class {class_id} is not represented in both train and val"
            )
    return {
        "samples": samples,
        "train_hashes": train_hashes,
        "val_hashes": val_hashes,
        "gold_hashes": gold_hashes,
        "review_hashes": review_hashes,
        "eval_train_hashes": eval_train_hashes,
        "review_gold_overlap": review_gold_overlap,
        "reserved_hashes": reserved_hashes,
        "changes_needed": changes_needed,
        "duplicate_files": duplicate_files,
        "label_conflicts": label_conflicts,
        "excluded_reserved": excluded_reserved,
        "cone_added": cone_added,
        "targets": targets,
        "train_presence": train_counts,
        "val_presence": val_counts,
    }


def print_plan(plan: dict) -> None:
    print("=== Dataset sanitation plan ===")
    print(f"Changes needed: {plan['changes_needed']}")
    print(f"Unique train: {len(plan['train_hashes'])}")
    print(f"Unique val: {len(plan['val_hashes'])}")
    print(f"Gold images reserved: {len(plan['gold_hashes'])}")
    print(f"Review images reserved: {len(plan['review_hashes'])}")
    print(f"Duplicate files removed: {plan['duplicate_files']}")
    print(f"Duplicate groups with label differences: {plan['label_conflicts']}")
    print(f"Training images excluded by evaluation pool: {len(plan['excluded_reserved'])}")
    print(f"Independent cone images added: {plan['cone_added']}")
    print("Class image presence (train / val / target):")
    for class_id in range(10):
        print(
            f"  {class_id}: {plan['train_presence'][class_id]} / "
            f"{plan['val_presence'][class_id]} / {plan['targets'][class_id]}"
        )


def unique_output_name(sample: Sample, used_stems: set[str]) -> str:
    stem = Path(sample.name).stem
    suffix = sample.suffix or ".jpg"
    candidate = stem
    if candidate.lower() in used_stems:
        candidate = f"{stem}_{sample.digest[:8]}"
    counter = 2
    while candidate.lower() in used_stems:
        candidate = f"{stem}_{sample.digest[:8]}_{counter}"
        counter += 1
    used_stems.add(candidate.lower())
    return f"{candidate}{suffix}"


def materialize_stage(plan: dict) -> tuple[Path, dict]:
    stage = ROOT / "archive" / f".dataset_sanitize_stage_{os.getpid()}"
    if stage.exists():
        raise FileExistsError(f"Stage already exists: {stage}")
    assignment = {}
    for split, digests in (
        ("train", plan["train_hashes"]),
        ("val", plan["val_hashes"]),
    ):
        image_dir = stage / "images" / split
        label_dir = stage / "labels" / split
        image_dir.mkdir(parents=True, exist_ok=True)
        label_dir.mkdir(parents=True, exist_ok=True)
        used_stems: set[str] = set()
        for digest in sorted(digests):
            sample = plan["samples"][digest]
            output_name = unique_output_name(sample, used_stems)
            image_target = image_dir / output_name
            label_target = label_dir / f"{image_target.stem}.txt"
            if sample.source_path is not None:
                try:
                    os.link(sample.source_path, image_target)
                except OSError:
                    shutil.copy2(sample.source_path, image_target)
            else:
                image_target.write_bytes(sample.image_bytes or b"")
            label_target.write_text(
                sample.label_text + ("\n" if sample.label_text else ""),
                encoding="utf-8",
            )
            assignment[digest] = {"split": split, "name": output_name}
    verify_stage(stage, plan)
    return stage, assignment


def verify_stage(stage: Path, plan: dict) -> None:
    split_hashes = {}
    for split in ("train", "val"):
        image_dir = stage / "images" / split
        label_dir = stage / "labels" / split
        hashes = set()
        for image_path in iter_images(image_dir):
            label_path = label_dir / f"{image_path.stem}.txt"
            if not label_path.exists():
                raise FileNotFoundError(f"Stage label missing: {label_path}")
            parse_label(label_path.read_text(encoding="utf-8"), str(label_path))
            digest = image_digest(image_path)
            if digest in hashes:
                raise RuntimeError(f"Duplicate image in staged {split}: {image_path}")
            hashes.add(digest)
        split_hashes[split] = hashes
    if split_hashes["train"] & split_hashes["val"]:
        raise RuntimeError("Staged train and val overlap")
    if (split_hashes["train"] | split_hashes["val"]) & plan["reserved_hashes"]:
        raise RuntimeError("Staged data overlaps evaluation pool")


def next_archive_dir() -> Path:
    base = ROOT / "archive" / f"dataset_sanitize_{datetime.now():%Y%m%d_%H%M%S}"
    candidate = base
    counter = 2
    while candidate.exists():
        candidate = Path(f"{base}_{counter}")
        counter += 1
    return candidate


def move_directory(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.exists():
        shutil.move(str(source), str(target))


def clean_evaluation_workspace(backup: Path, gold_hashes: set[str]) -> list[str]:
    for kind in ("images", "labels"):
        source = EVAL_ROOT / kind / "train"
        target = backup / "evaluation" / kind / "train"
        move_directory(source, target)
        source.mkdir(parents=True, exist_ok=True)

    removed_stems = []
    review_images = EVAL_ROOT / "images" / "review"
    review_labels = EVAL_ROOT / "labels" / "review"
    backup_images = backup / "evaluation" / "images" / "review_gold_overlap"
    backup_labels = backup / "evaluation" / "labels" / "review_gold_overlap"
    for image_path in list(iter_images(review_images)):
        if image_digest(image_path) not in gold_hashes:
            continue
        removed_stems.append(image_path.stem)
        backup_images.mkdir(parents=True, exist_ok=True)
        shutil.move(str(image_path), str(backup_images / image_path.name))
        label_path = review_labels / f"{image_path.stem}.txt"
        if label_path.exists():
            backup_labels.mkdir(parents=True, exist_ok=True)
            shutil.move(str(label_path), str(backup_labels / label_path.name))

    progress_path = review_labels / ".annotate_progress.json"
    if progress_path.exists():
        progress_backup = backup / "evaluation" / "labels" / "review_progress.json"
        progress_backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(progress_path, progress_backup)
        progress = json.loads(progress_path.read_text(encoding="utf-8-sig"))
        for stem in removed_stems:
            progress.pop(stem, None)
        progress_path.write_text(
            json.dumps(progress, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return removed_stems


def apply_plan(plan: dict) -> Path | None:
    if not plan["changes_needed"]:
        return None
    stage, assignment = materialize_stage(plan)
    backup = next_archive_dir()
    backup.mkdir(parents=True)
    try:
        for kind in ("images", "labels"):
            old_path = TRAIN_ROOT / kind
            backup_path = backup / "training_dataset" / kind
            move_directory(old_path, backup_path)
            shutil.move(str(stage / kind), str(old_path))
        stage.rmdir()
        removed_review = clean_evaluation_workspace(backup, plan["gold_hashes"])
        manifest = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "train_images": len(plan["train_hashes"]),
            "val_images": len(plan["val_hashes"]),
            "gold_images": len(plan["gold_hashes"]),
            "review_gold_duplicates_removed": len(removed_review),
            "duplicate_files_removed": plan["duplicate_files"],
            "training_evaluation_leaks_removed": len(plan["excluded_reserved"]),
            "cone_images_added": plan["cone_added"],
            "assignment": assignment,
        }
        (backup / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception:
        if stage.exists():
            print(f"Staged files retained for recovery: {stage}")
        raise
    return backup


def sanitize_dataset(apply: bool = False) -> Path | None:
    plan = build_plan()
    print_plan(plan)
    if not apply:
        return None
    return apply_plan(plan)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="install the clean split and archive the previous directories",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    plan = build_plan()
    print_plan(plan)
    if not args.apply:
        print("Dry run only. Re-run with --apply to update local datasets.")
        return 0
    backup = apply_plan(plan)
    if backup is None:
        print("Dataset is already clean; no files changed.")
    else:
        print(f"Clean dataset installed. Previous state: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
