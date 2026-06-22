#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
aris_load_env

python3 "${ARIS_WS}/scripts/summarize_headless_status.py" \
  --logs-dir "$ARIS_LOGS" \
  --workspace "$ARIS_WS" \
  "$@"
