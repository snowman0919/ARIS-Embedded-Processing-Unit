#!/usr/bin/env bash
set -euo pipefail

# Runs the headless readiness gate and stores timestamped acceptance evidence.

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
aris_load_env

report_dir="${ARIS_LOGS}/readiness"
mkdir -p "$report_dir"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
report_file="${report_dir}/core_readiness_${timestamp}.log"
index_file="${report_dir}/evidence_index_${timestamp}.json"
latest_file="${report_dir}/latest.log"
latest_index_file="${report_dir}/latest_evidence_index.json"

{
  printf 'ARIS Core Readiness Report\n'
  printf 'timestamp_utc=%s\n' "$timestamp"
  printf 'workspace=%s\n' "$ARIS_WS"
  printf 'git_branch=%s\n' "$(git -C "$ARIS_WS" branch --show-current 2>/dev/null || true)"
  printf 'git_commit=%s\n' "$(git -C "$ARIS_WS" rev-parse --short HEAD 2>/dev/null || true)"
  printf 'skip_v3=%s\n' "${ARIS_CORE_READINESS_SKIP_V3:-0}"
  printf 'skip_gazebo=%s\n' "${ARIS_CORE_READINESS_SKIP_GAZEBO:-0}"
  printf 'real_actuation=%s\n' "${ARIS_ENABLE_REAL_ACTUATION:-0}"
  printf '\n'
} | tee "$report_file"

status=0
"${ARIS_WS}/scripts/check_core_readiness.sh" 2>&1 | tee -a "$report_file" || status=${PIPESTATUS[0]}

{
  printf '\n'
  printf 'result=%s\n' "$([[ "$status" == "0" ]] && printf PASS || printf FAIL)"
  printf 'exit_code=%s\n' "$status"
  printf 'report_file=%s\n' "$report_file"
} | tee -a "$report_file"

ln -sf "$report_file" "$latest_file"
"${ARIS_WS}/scripts/generate_readiness_evidence_index.py" \
  --workspace "$ARIS_WS" \
  --logs-dir "$ARIS_LOGS" \
  --out "$index_file" | tee -a "$report_file"
ln -sf "$index_file" "$latest_index_file"
exit "$status"
