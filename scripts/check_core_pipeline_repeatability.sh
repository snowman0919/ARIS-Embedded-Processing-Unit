#!/usr/bin/env bash
set -euo pipefail

# Re-run the cross-milestone headless pipeline and summarize repeatability.

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
aris_load_env

runs="${ARIS_CORE_PIPELINE_REPEAT_RUNS:-2}"
if ! [[ "$runs" =~ ^[0-9]+$ ]] || (( runs < 2 )); then
  aris_die "ARIS_CORE_PIPELINE_REPEAT_RUNS must be an integer >= 2"
fi

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
report_dir="${ARIS_LOGS}/pipeline"
report_file="${report_dir}/core_pipeline_repeatability_${timestamp}.json"
latest_file="${report_dir}/latest_core_pipeline_repeatability.json"
mkdir -p "$report_dir"

reports_file="$(mktemp)"
trap 'rm -f "$reports_file"' EXIT

base_domain="${ARIS_CORE_PIPELINE_REPEAT_BASE_DOMAIN_ID:-160}"

for run_id in $(seq 1 "$runs"); do
  printf 'core_pipeline_repeatability run=%s/%s\n' "$run_id" "$runs"
  export ARIS_CORE_PIPELINE_ROS_DOMAIN_ID="$((base_domain + run_id))"
  "${ARIS_WS}/scripts/check_core_pipeline_flow.sh"
  latest_report="$(readlink -f "${report_dir}/latest_core_pipeline_flow.json")"
  printf '%s\n' "$latest_report" >>"$reports_file"
done

python3 "${ARIS_WS}/scripts/summarize_core_pipeline_repeatability.py" \
  --reports-file "$reports_file" \
  --expected-runs "$runs" \
  --workspace "$ARIS_WS" \
  --logs-dir "$ARIS_LOGS" \
  --out "$report_file"

ln -sf "$report_file" "$latest_file"
