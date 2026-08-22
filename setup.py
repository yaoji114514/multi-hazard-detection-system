"""Cross-platform installer dispatcher for the local PPE application."""
from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def main() -> int:
    system = platform.system()
    if system == "Windows":
        command = ["cmd", "/c", str(ROOT / "setup.bat")]
    elif system == "Darwin":
        command = ["/bin/bash", str(ROOT / "setup_macos.sh")]
    else:
        print(f"[错误] 暂不支持的操作系统: {system}", file=sys.stderr)
        print("Windows 请运行 setup.bat；macOS 请运行 python3 setup.py。", file=sys.stderr)
        return 1
    return subprocess.run(command, cwd=ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
