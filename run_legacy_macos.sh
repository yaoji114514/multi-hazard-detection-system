#!/usr/bin/env bash
# macOS launcher for the classic Streamlit interface.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "[错误] run_legacy_macos.sh 仅支持 macOS。" >&2
  exit 1
fi

PYTHON_BIN=".venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "[错误] 未找到 macOS 虚拟环境。请先运行: python3 setup.py" >&2
  exit 1
fi

if ! "$PYTHON_BIN" -c 'import streamlit, torch, ultralytics' >/dev/null 2>&1; then
  echo "[错误] 虚拟环境不完整。请重新运行: python3 setup.py" >&2
  exit 1
fi

if [[ "${1:-}" == "--check" ]]; then
  "$PYTHON_BIN" -c 'import streamlit, torch, ultralytics; print("[OK] Legacy macOS environment is ready")'
  exit 0
fi

if curl --fail --silent --max-time 2 http://localhost:8501/_stcore/health >/dev/null 2>&1; then
  open http://localhost:8501
  echo "[信息] 经典界面已经在运行，已在默认浏览器中打开。"
  exit 0
fi

"$PYTHON_BIN" src/configure_streamlit.py
export PYTORCH_ENABLE_MPS_FALLBACK=1
"$PYTHON_BIN" -m streamlit run app.py --server.headless true &
STREAMLIT_PID=$!
trap 'kill "$STREAMLIT_PID" 2>/dev/null || true' EXIT

for _ in {1..20}; do
  if curl --fail --silent --max-time 2 http://localhost:8501/_stcore/health >/dev/null 2>&1; then
    open http://localhost:8501
    break
  fi
  sleep 0.5
done

wait "$STREAMLIT_PID"
