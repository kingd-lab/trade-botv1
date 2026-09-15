#!/usr/bin/env bash
set -euo pipefail
DATA_DIR="${PAPER_BOT_DATA_DIR:-/data}"
mkdir -p "$DATA_DIR"
export PAPER_BOT_DATA_DIR="$DATA_DIR"
PORT="${PORT:-8501}"

python runner.py &
BOT_PID=$!

streamlit run dashboard.py --server.address 0.0.0.0 --server.port "$PORT" --server.headless true &
WEB_PID=$!

cleanup() {
  kill "$BOT_PID" "$WEB_PID" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

wait -n "$BOT_PID" "$WEB_PID"
STATUS=$?
cleanup
exit "$STATUS"
