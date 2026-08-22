#!/usr/bin/env bash
# macOS launcher for the V3 local React + FastAPI application.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "[错误] run_macos.sh 仅支持 macOS。" >&2
  exit 1
fi

PYTHON_BIN=".venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "[错误] 未找到 macOS 虚拟环境。请先运行: python3 setup.py" >&2
  exit 1
fi

if ! "$PYTHON_BIN" -c 'import fastapi, uvicorn, torch, ultralytics' >/dev/null 2>&1; then
  echo "[错误] V3 运行环境不完整。请重新运行: python3 setup.py" >&2
  exit 1
fi

if [[ ! -f "frontend/dist/index.html" ]]; then
  echo "[错误] 未找到 V3 前端构建产物 frontend/dist/index.html。" >&2
  exit 1
fi

if [[ "${1:-}" == "--check" ]]; then
  "$PYTHON_BIN" -c 'import fastapi, uvicorn, torch, ultralytics; print("[OK] V3 macOS environment is ready")'
  exit 0
fi

if curl --fail --silent --max-time 2 http://127.0.0.1:8501/api/health >/dev/null 2>&1; then
  open http://127.0.0.1:8501
  echo "[信息] V3 已经在运行，已在默认浏览器中打开。"
  exit 0
fi

export PYTORCH_ENABLE_MPS_FALLBACK=1
"$PYTHON_BIN" -m uvicorn src.web_api:app --host 127.0.0.1 --port 8501 &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT

for _ in {1..20}; do
  if curl --fail --silent --max-time 2 http://127.0.0.1:8501/api/health >/dev/null 2>&1; then
    open http://127.0.0.1:8501
    break
  fi
  sleep 0.5
done

wait "$SERVER_PID"
