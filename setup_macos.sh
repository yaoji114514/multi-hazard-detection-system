#!/usr/bin/env bash
# macOS installer. Use `python3 setup.py` for automatic OS dispatch.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "[错误] setup_macos.sh 仅支持 macOS。请使用与当前系统对应的安装入口。" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "[错误] 未检测到 python3。请先安装 Python 3.9 或更高版本。" >&2
  exit 1
fi

if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)'; then
  echo "[错误] Python 版本过低，需要 Python 3.9 或更高版本。" >&2
  exit 1
fi

if [[ -d .venv && ! -x .venv/bin/python ]]; then
  echo "[错误] 现有 .venv 不是可用的 macOS 虚拟环境。请删除该目录后重新运行安装。" >&2
  exit 1
fi

if [[ ! -d .venv ]]; then
  echo "[1/5] 正在创建独立虚拟环境 (.venv)..."
  python3 -m venv .venv
else
  echo "[1/5] 已找到现有 macOS 虚拟环境。"
fi

PYTHON_BIN=".venv/bin/python"
echo "[2/5] 正在更新 pip..."
"$PYTHON_BIN" -m pip install --upgrade pip

if "$PYTHON_BIN" -c 'import torch, torchvision' >/dev/null 2>&1; then
  echo "[3/5] 已找到 PyTorch，跳过重复安装。"
else
  echo "[3/5] 正在安装 macOS 版 PyTorch..."
  "$PYTHON_BIN" -m pip install torch torchvision
fi

echo "[4/5] 正在安装项目依赖..."
"$PYTHON_BIN" -m pip install -r requirements.txt

echo "[5/5] 正在初始化本地数据目录..."
mkdir -p data/uploads data/db

DEVICE="$($PYTHON_BIN -c 'import torch; mps = getattr(getattr(torch, "backends", None), "mps", None); print("Apple Silicon MPS" if mps and mps.is_available() else "CPU")')"
echo
echo "============================================"
echo "  安装完成！"
echo "  推理模式: $DEVICE"
echo "  启动命令: bash run_macos.sh"
echo "============================================"
