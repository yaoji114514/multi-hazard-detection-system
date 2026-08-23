"""Build a credential-free, cross-platform demo distribution package."""
from __future__ import annotations

import argparse
import hashlib
import shutil
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOP_LEVEL_FILES = (
    "requirements.txt",
    "使用说明.md",
    "setup.py",
    "setup.bat",
    "run.bat",
    "setup_macos.sh",
    "run_macos.sh",
)
SOURCE_DIRECTORIES = ("src", "frontend/dist")
OPTIONAL_FILES = (
    "config/dingtalk.example.json",
    "data/alert.wav",
    "data/sample_images/test_helmet.jpg",
)
FORBIDDEN_PARTS = (
    ".venv",
    "data/db",
    "data/uploads",
    "config/dingtalk.local.json",
    "archive",
    "runs",
    "evaluation",
    "tests",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _model_files(root: Path) -> tuple[Path, ...]:
    models_dir = root / "models"
    baseline_path = models_dir / "best.pt"
    if not baseline_path.is_file():
        raise FileNotFoundError("缺少初始基线模型 models/best.pt")
    return (baseline_path,)


def release_files(root: Path = PROJECT_ROOT) -> tuple[Path, ...]:
    files = [root / relative for relative in TOP_LEVEL_FILES]
    files.extend(root / relative for relative in OPTIONAL_FILES)
    files.extend(_model_files(root))
    for directory_name in SOURCE_DIRECTORIES:
        files.extend(
            path
            for path in (root / directory_name).rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        )
    missing = [path for path in files if not path.is_file()]
    if missing:
        raise FileNotFoundError("发布文件缺失: " + ", ".join(str(path) for path in missing))
    return tuple(sorted(set(files)))


def archive_paths(target: Path) -> tuple[Path, Path]:
    archive = target.parent / f"{target.name}.zip"
    return archive, target.parent / f"{archive.name}.sha256"


def build_package(target: Path, version: str) -> tuple[Path, Path, Path]:
    target = target.resolve()
    if target == PROJECT_ROOT or target.exists():
        raise ValueError("目标目录必须不存在，且不能是项目根目录")

    files = release_files()
    target.mkdir(parents=True)
    try:
        for source in files:
            destination = target / source.relative_to(PROJECT_ROOT)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

        (target / "models" / "active_model.txt").write_text("best.pt\n", encoding="utf-8")

        forbidden = [part for part in FORBIDDEN_PARTS if (target / part).exists()]
        if forbidden:
            raise ValueError("发布包包含禁止内容: " + ", ".join(forbidden))

        archive, archive_checksum = archive_paths(target)
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for path in sorted(path for path in target.rglob("*") if path.is_file()):
                bundle.write(path, arcname=f"{target.name}/{path.relative_to(target).as_posix()}")
        with zipfile.ZipFile(archive) as bundle:
            broken_name = bundle.testzip()
        if broken_name:
            raise ValueError(f"ZIP 校验失败: {broken_name}")

        archive_checksum.write_text(
            f"{_sha256(archive)}  {archive.name}\n", encoding="utf-8"
        )
    except Exception:
        shutil.rmtree(target, ignore_errors=True)
        raise
    return target, archive, archive_checksum


def main() -> int:
    parser = argparse.ArgumentParser(description="生成无凭据的正式测试版 Demo 包")
    parser.add_argument("--target", required=True, help="新建的发布目录")
    parser.add_argument("--version", required=True, help="发布版本，例如 v0.1.0-test1")
    args = parser.parse_args()

    target, archive, archive_checksum = build_package(Path(args.target), args.version)
    print(f"发布目录: {target}")
    print(f"ZIP: {archive}")
    print(f"ZIP SHA-256: {archive_checksum}")
    print(f"文件数: {sum(1 for path in target.rglob('*') if path.is_file())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
