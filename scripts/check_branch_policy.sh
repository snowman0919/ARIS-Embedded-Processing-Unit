#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
aris_load_env

report_dir="${ARIS_LOGS}/readiness"
mkdir -p "$report_dir"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
report_file="${report_dir}/branch_policy_${timestamp}.json"
latest_file="${report_dir}/latest_branch_policy.json"

python3 "${ARIS_WS}/scripts/check_branch_policy.py" \
  --workspace "$ARIS_WS" \
  --out "$report_file"

ln -sf "$report_file" "$latest_file"
