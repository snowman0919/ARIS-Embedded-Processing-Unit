#!/usr/bin/env bash
set -euo pipefail

# Runs the processing-unit embedded-interface dry-run and stores timestamped evidence.

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
aris_load_env

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
report_dir="${ARIS_LOGS}/embedded"
log_file="${report_dir}/embedded_dry_run_${timestamp}.log"
report_file="${report_dir}/embedded_dry_run_${timestamp}.json"
latest_report="${report_dir}/latest_embedded_dry_run.json"
latest_log="${report_dir}/latest_embedded_dry_run.log"
mkdir -p "$report_dir"

status=0
{
  printf 'ARIS Embedded Dry-Run\n'
  printf 'timestamp_utc=%s\n' "$timestamp"
  printf 'workspace=%s\n' "$ARIS_WS"
  printf 'git_branch=%s\n' "$(git -C "$ARIS_WS" branch --show-current 2>/dev/null || true)"
  printf 'git_commit=%s\n' "$(git -C "$ARIS_WS" rev-parse --short HEAD 2>/dev/null || true)"
  printf 'hardware_required=0\n'
  printf '\n'
} | tee "$log_file"

{
  printf 'check=protocol_reference\n'
  python3 -m pytest src/aris_mcu_bridge/test tests/protocol
  printf '\ncheck=pty_serial_loopback\n'
  "${ARIS_WS}/scripts/check_mcu_serial_loopback.sh"
} 2>&1 | tee -a "$log_file" || status=${PIPESTATUS[0]}

python3 - "$report_file" "$log_file" "$timestamp" "$ARIS_WS" "$status" <<'PY'
import json
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
log_path = Path(sys.argv[2])
timestamp = sys.argv[3]
workspace = sys.argv[4]
status = int(sys.argv[5])

report = {
    "artifact_type": "aris_embedded_dry_run_report",
    "schema_version": 1,
    "timestamp_utc": timestamp,
    "workspace": workspace,
    "hardware_required": False,
    "valid": status == 0,
    "exit_code": status,
    "log_path": str(log_path),
    "checks": [
        "aris_mcu_bridge protocol tests",
        "protocol reference tests",
        "PTY serial loopback transport test",
    ],
    "scope_note": (
        "This repository contains the ROS 2 processing-unit MCU bridge and protocol code. "
        "Standalone STM32 firmware is owned by snowman0919/ARIS-Embedded-MCU."
    ),
}
report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"embedded_dry_run path={report_path} valid={report['valid']} exit_code={status}")
PY

ln -sf "$report_file" "$latest_report"
ln -sf "$log_file" "$latest_log"
exit "$status"
