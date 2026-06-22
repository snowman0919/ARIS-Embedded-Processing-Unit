#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
aris_load_env

if [[ $# -ne 1 ]]; then
  printf 'Usage: %s <field-validation-manifest.json>\n' "$0" >&2
  exit 2
fi

manifest="$(realpath "$1")"
if [[ ! -f "$manifest" ]]; then
  aris_die "Field validation manifest does not exist: $manifest"
fi

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
report_dir="${ARIS_LOGS}/field"
report_file="${report_dir}/field_validation_${timestamp}.json"
latest_file="${report_dir}/latest_field_validation.json"
mkdir -p "$report_dir"

"${ARIS_WS}/scripts/generate_field_validation_report.py" \
  --workspace "$ARIS_WS" \
  --logs-dir "$ARIS_LOGS" \
  --manifest "$manifest" \
  --out "$report_file"

ln -sf "$report_file" "$latest_file"
