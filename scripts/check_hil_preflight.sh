#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
aris_load_env

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
report_dir="${ARIS_LOGS}/hil"
report_file="${report_dir}/hil_preflight_${timestamp}.json"
latest_file="${report_dir}/latest_hil_preflight.json"
mkdir -p "$report_dir"

"${ARIS_WS}/scripts/generate_hil_preflight.py" \
  --workspace "$ARIS_WS" \
  --logs-dir "$ARIS_LOGS" \
  --out "$report_file"

ln -sf "$report_file" "$latest_file"
