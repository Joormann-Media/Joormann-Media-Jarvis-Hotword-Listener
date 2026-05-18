#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVICE_SRC="$ROOT_DIR/systemd/joormann-media-jarvis-hotword-listener.service"
SERVICE_DST="/etc/systemd/system/joormann-media-jarvis-hotword-listener.service"
sudo cp "$SERVICE_SRC" "$SERVICE_DST"
sudo systemctl daemon-reload
echo "Installed service"
