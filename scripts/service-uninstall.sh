#!/usr/bin/env bash
set -euo pipefail
sudo systemctl disable joormann-media-jarvis-hotword-listener.service || true
sudo rm -f /etc/systemd/system/joormann-media-jarvis-hotword-listener.service
sudo systemctl daemon-reload
