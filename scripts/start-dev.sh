#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/runtime/logs"
PID_DIR="$PROJECT_ROOT/runtime/pids"
MANAGER_PID_FILE="$PID_DIR/manager.pid"
HOTWORD_PID_FILE="$PID_DIR/hotword-service.pid"
MANAGER_LOG_FILE="$LOG_DIR/manager.log"
HOTWORD_LOG_FILE="$LOG_DIR/hotword-service.log"

FLASK_PORT="${LAB_PORT:-5103}"
HOTWORD_PORT="${HOTWORD_SERVICE_PORT:-8120}"

get_local_ip() {
  local ip
  ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
  if [[ -z "${ip:-}" ]]; then
    ip="127.0.0.1"
  fi
  echo "$ip"
}

print_status_block() {
  local local_ip="$1"
  cat <<EOT

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Jarvis Hotword-Listener läuft

  Dashboard:  http://${local_ip}:${FLASK_PORT}/
  Link:       http://${local_ip}:${FLASK_PORT}/link
  API-Doku:   http://${local_ip}:${FLASK_PORT}/info
  Health:     http://${local_ip}:${FLASK_PORT}/health

  Manager-Log: ${MANAGER_LOG_FILE}
  Runtime-Log: ${HOTWORD_LOG_FILE}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EOT
}

trigger_panel_sync() {
  local sync_url="http://127.0.0.1:${FLASK_PORT}/api/portal/sync"
  local tmp_json
  tmp_json="$(mktemp)"

  if ! curl -sS --max-time 20 -X POST -H "Content-Type: application/json" -d '{}' "$sync_url" -o "$tmp_json" -w '%{http_code}' >"$tmp_json.code" 2>/dev/null; then
    echo "[Panel]    Auto-Sync übersprungen: Healthcheck/Sync nicht erreichbar. Link prüfen: http://127.0.0.1:${FLASK_PORT}/link"
    rm -f "$tmp_json" "$tmp_json.code"
    return 0
  fi

  local http_code body node_ok node_sync_ok mcp_ok
  http_code="$(cat "$tmp_json.code")"
  body="$(cat "$tmp_json")"

  node_ok="$(printf '%s' "$body" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(str(bool(d.get("node_ok", False))).lower())' 2>/dev/null || echo "false")"
  node_sync_ok="$(printf '%s' "$body" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(str(bool(d.get("node_sync_ok", False))).lower())' 2>/dev/null || echo "false")"
  mcp_ok="$(printf '%s' "$body" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(str(bool(d.get("mcp_ok", False))).lower())' 2>/dev/null || echo "false")"

  if [[ "$http_code" == "200" && "$node_sync_ok" == "true" && "$mcp_ok" == "true" ]]; then
    echo "[Panel]    Auto-Sync erfolgreich."
  elif [[ "$http_code" == "200" && "$node_sync_ok" != "true" ]]; then
    echo "[Panel]    Node ist verknüpft, Service-Sync fehlgeschlagen."
  elif [[ "$http_code" == "200" && "$mcp_ok" != "true" ]]; then
    echo "[Panel]    Node-Sync erfolgreich, MCP-Intent-Sync fehlgeschlagen."
  elif [[ "$http_code" == "502" && "$node_ok" == "true" && "$node_sync_ok" != "true" ]]; then
    echo "[Panel]    Node verknüpft, aber Service-Sync fehlgeschlagen."
  elif [[ "$http_code" == "502" && "$node_ok" == "true" ]]; then
    echo "[Panel]    Node ist verknüpft, aber MCP-Intent-Sync fehlgeschlagen."
  elif [[ "$http_code" == "502" ]]; then
    echo "[Panel]    Auto-Sync übersprungen: Node noch nicht vollständig verknüpft. Link prüfen: http://127.0.0.1:${FLASK_PORT}/link"
  else
    echo "[Panel]    Auto-Sync Fehler (HTTP ${http_code}) auf ${sync_url}"
  fi

  rm -f "$tmp_json" "$tmp_json.code"
}

mkdir -p "$LOG_DIR" "$PID_DIR"

if [[ -f "$PROJECT_ROOT/config/ports.env" ]]; then
  set -a
  source "$PROJECT_ROOT/config/ports.env"
  set +a
fi
if [[ -f "$PROJECT_ROOT/config/ports.local.env" ]]; then
  set -a
  source "$PROJECT_ROOT/config/ports.local.env"
  set +a
fi
FLASK_PORT="${LAB_PORT:-$FLASK_PORT}"
HOTWORD_PORT="${HOTWORD_SERVICE_PORT:-$HOTWORD_PORT}"

VENV_DIR="$PROJECT_ROOT/.venv"
PYTHON_BIN="$VENV_DIR/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

echo "Installiere/aktualisiere Requirements ..."
"$PYTHON_BIN" -m pip install -q --upgrade pip
"$PYTHON_BIN" -m pip install -q -r "$PROJECT_ROOT/requirements.txt"
"$PYTHON_BIN" -m pip install -q -r "$PROJECT_ROOT/services/hotword-service/requirements.txt"

if [[ -f "$MANAGER_PID_FILE" ]]; then
  pid="$(cat "$MANAGER_PID_FILE")"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    local_ip="$(get_local_ip)"
    echo "[Flask]    Bereits aktiv (PID $pid) — übersprungen"
    print_status_block "$local_ip"
    trigger_panel_sync
    exit 0
  fi
fi

if [[ -f "$HOTWORD_PID_FILE" ]]; then
  pid="$(cat "$HOTWORD_PID_FILE")"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    echo "[Runtime]  Bereits aktiv (PID $pid) — übersprungen"
  fi
fi

nohup "$PYTHON_BIN" "$PROJECT_ROOT/app.py" > "$MANAGER_LOG_FILE" 2>&1 &
manager_pid=$!
echo "$manager_pid" > "$MANAGER_PID_FILE"
echo "[Flask]    Gestartet (PID $manager_pid)"

nohup "$PYTHON_BIN" -m uvicorn src.main:app --app-dir "$PROJECT_ROOT/services/hotword-service" --host 0.0.0.0 --port "$HOTWORD_PORT" > "$HOTWORD_LOG_FILE" 2>&1 &
hotword_pid=$!
echo "$hotword_pid" > "$HOTWORD_PID_FILE"
echo "[Runtime]  Gestartet (PID $hotword_pid)"

for _ in {1..20}; do
  if curl -fsS "http://127.0.0.1:${FLASK_PORT}/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

local_ip="$(get_local_ip)"
print_status_block "$local_ip"
trigger_panel_sync
