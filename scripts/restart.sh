#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"

echo "[restart] Stoppe Modul ..."
"$SCRIPT_DIR/stop-dev.sh" || true
sleep 1
echo "[restart] Starte Modul ..."
exec "$SCRIPT_DIR/start-dev.sh"
