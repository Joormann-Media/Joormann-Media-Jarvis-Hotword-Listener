#!/usr/bin/env bash
set -euo pipefail
"$(cd "$(dirname "$0")" && pwd)/stop-dev.sh"
"$(cd "$(dirname "$0")" && pwd)/start-dev.sh"
