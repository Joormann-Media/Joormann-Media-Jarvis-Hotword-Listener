#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p runtime/logs runtime/pids

python3 -m venv .venv || true
source .venv/bin/activate
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt
python -m pip install -q -r services/hotword-service/requirements.txt

# Manager
nohup .venv/bin/python app.py > runtime/logs/manager.log 2>&1 &
echo $! > runtime/pids/manager.pid

# Hotword service
(cd services/hotword-service && nohup ../../.venv/bin/python -m uvicorn src.main:app --host 0.0.0.0 --port 8120 > ../../runtime/logs/hotword-service.log 2>&1 &)
echo $! > runtime/pids/hotword-service.pid

sleep 2
curl -fsS http://127.0.0.1:5103/api/portal/status >/dev/null || true
curl -fsS -X POST http://127.0.0.1:5103/api/portal/sync >/dev/null || true

echo "Manager: http://127.0.0.1:5103"
echo "Hotword Service: http://127.0.0.1:8120"
