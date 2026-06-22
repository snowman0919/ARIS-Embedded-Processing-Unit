#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
aris_load_env

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
report_dir="${ARIS_LOGS}/readiness"
report_file="${report_dir}/operational_readiness_audit_${timestamp}.json"
latest_file="${report_dir}/latest_operational_readiness_audit.json"
mkdir -p "$report_dir"

"${ARIS_WS}/scripts/generate_operational_readiness_audit.py" \
  --workspace "$ARIS_WS" \
  --logs-dir "$ARIS_LOGS" \
  --out "$report_file"

ln -sf "$report_file" "$latest_file"
