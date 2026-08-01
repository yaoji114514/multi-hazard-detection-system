# -*- coding: utf-8 -*-
"""生成可迁移继续开发包。

复制完整项目(含 .git 历史、模型、数据、日志、工作守则)到目标目录,
自动排除虚拟环境、Python 缓存、Git 临时文件和可重新下载的大型外部数据。

用法: python tools/make_portable.py --target "D:\\迁移目标\\多类隐患检测系统_可移植包\\多类隐患检测系统_可移植包"
"""
import argparse
import shutil
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

ALWAYS_EXCLUDE = {
    ".venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".idea", ".vscode",
}
ALWAYS_EXCLUDE_SUFFIX = {".pyc", ".pyo", ".pyd"}

# 可重新下载的大型外部数据，默认不打包，避免迁移包膨胀。
EXCLUDE_LARGE = {
    PROJECT_ROOT / "data" / "material_library" / "hf_datasets",
}


def _ignore(src, names):
    src_path = Path(src).resolve()
    ignored = set()
    for name in names:
        p = src_path / name
        if p.resolve() in EXCLUDE_LARGE:
            ignored.add(name)
            continue
        if name in ALWAYS_EXCLUDE:
            ignored.add(name)
            continue
        if p.suffix.lower() in ALWAYS_EXCLUDE_SUFFIX:
            ignored.add(name)
            continue
        if src_path == (PROJECT_ROOT / ".git" / "lfs").resolve() and name == "tmp":
            ignored.add(name)
            continue
    return ignored


def main():
    parser = argparse.ArgumentParser(description="生成多类隐患检测系统可迁移继续开发包")
    parser.add_argument("--target", required=True, help="目标目录(会创建/更新, 不能是项目本身)")
    args = parser.parse_args()

    target = Path(args.target).resolve()
    if target == PROJECT_ROOT:
        raise SystemExit("目标目录不能是项目本身")
    try:
        target.relative_to(PROJECT_ROOT)
        raise SystemExit("目标目录不能位于项目内部")
    except ValueError:
        pass

    print(f"源项目: {PROJECT_ROOT}")
    print(f"目标目录: {target}")
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(PROJECT_ROOT, target, ignore=_ignore, dirs_exist_ok=True, copy_function=shutil.copy2)

    files = [p for p in target.rglob("*") if p.is_file()]
    total = sum(f.stat().st_size for f in files if f.is_file())
    manifest = target / "package_manifest.txt"
    manifest.write_text(
        "\n".join([
            f"生成时间: {datetime.now().isoformat(timespec='seconds')}",
            f"源项目: {PROJECT_ROOT}",
            f"文件数: {len(files)}",
            f"总大小: {total / 1024 / 1024:.1f} MB",
            "",
            "已排除: .venv / __pycache__ / *.pyc / .git/lfs/tmp / data/material_library/hf_datasets",
        ]),
        encoding="utf-8",
    )
    print(f"完成: {len(files)} 个文件, {total / 1024 / 1024:.1f} MB")
    print(f"清单: {manifest}")


if __name__ == "__main__":
    main()
