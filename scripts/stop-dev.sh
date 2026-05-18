#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"
for p in runtime/pids/manager.pid runtime/pids/hotword-service.pid; do
  if [ -f "$p" ]; then
    pid="$(cat "$p")"
    kill "$pid" 2>/dev/null || true
    rm -f "$p"
  fi
done
pkill -f "uvicorn src.main:app --host 0.0.0.0 --port 8120" 2>/dev/null || true
pkill -f "python app.py" 2>/dev/null || true
echo "Stopped"
