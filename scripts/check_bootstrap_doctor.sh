#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
aris_load_env

report_dir="${ARIS_LOGS}/readiness"
mkdir -p "$report_dir"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
report_file="${report_dir}/bootstrap_doctor_${timestamp}.json"
latest_file="${report_dir}/latest_bootstrap_doctor.json"

python3 "${ARIS_WS}/scripts/generate_bootstrap_doctor.py" \
  --workspace "$ARIS_WS" \
  --out "$report_file"

ln -sf "$report_file" "$latest_file"
