#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PID_DIR="$PROJECT_ROOT/runtime/pids"

stop_pid_file() {
  local label="$1"
  local pid_file="$2"

  if [[ ! -f "$pid_file" ]]; then
    echo "[$label]  Keine PID-Datei gefunden — übersprungen"
    return
  fi

  local pid
  pid="$(cat "$pid_file")"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    sleep 1
    if kill -0 "$pid" 2>/dev/null; then
      kill -9 "$pid" 2>/dev/null || true
    fi
    echo "[$label]  Gestoppt (PID $pid)"
  else
    echo "[$label]  Verwaiste PID-Datei entfernt"
  fi
  rm -f "$pid_file"
}

stop_pid_file "Flask" "$PID_DIR/manager.pid"
stop_pid_file "Runtime" "$PID_DIR/hotword-service.pid"

pkill -f "uvicorn src.main:app --app-dir" 2>/dev/null || true
pkill -f "python .*app.py" 2>/dev/null || true
