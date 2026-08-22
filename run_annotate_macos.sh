#!/usr/bin/env bash
# macOS launcher for the annotation tool.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "[错误] run_annotate_macos.sh 仅支持 macOS。" >&2
  exit 1
fi

PYTHON_BIN=".venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "[错误] 未找到 macOS 虚拟环境。请先运行: python3 setup.py" >&2
  exit 1
fi

IMAGE_DIR="${1:-evaluation/datasets/ppe/images/val}"
echo "=== YOLO Annotation Tool ==="
echo "Images: $IMAGE_DIR"
echo "Open: http://localhost:8504"
echo "==================================="
"$PYTHON_BIN" tools/annotate_server.py "$IMAGE_DIR" --port 8504
