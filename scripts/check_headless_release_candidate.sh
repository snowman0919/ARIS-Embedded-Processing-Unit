#!/usr/bin/env bash
set -euo pipefail

# Runs the full hardware-free release-candidate gate and records a summary.

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
aris_load_env

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
report_dir="${ARIS_LOGS}/readiness"
report_file="${report_dir}/headless_release_candidate_${timestamp}.json"
latest_file="${report_dir}/latest_headless_release_candidate.json"
final_index_file="${report_dir}/evidence_index_${timestamp}_release.json"
latest_index_file="${report_dir}/latest_evidence_index.json"
mkdir -p "$report_dir"

steps_file="$(mktemp)"
trap 'rm -f "$steps_file"' EXIT

run_step() {
  local name="$1"
  shift
  local started ended status
  started="$(date -u +%Y%m%dT%H%M%SZ)"
  printf 'headless_release_candidate step=%s started=%s\n' "$name" "$started"
  set +e
  "$@"
  status=$?
  set -e
  ended="$(date -u +%Y%m%dT%H%M%SZ)"
  printf '%s\t%s\t%s\t%s\n' "$name" "$status" "$started" "$ended" >>"$steps_file"
  printf 'headless_release_candidate step=%s ended=%s status=%s\n' "$name" "$ended" "$status"
  return "$status"
}

overall_status=0
if [[ "${ARIS_HEADLESS_RELEASE_REUSE_EXISTING:-0}" == "1" ]]; then
  printf '%s\t%s\t%s\t%s\n' embedded_dry_run 0 "$timestamp" "$timestamp" >>"$steps_file"
  printf '%s\t%s\t%s\t%s\n' documented_commands 0 "$timestamp" "$timestamp" >>"$steps_file"
  printf '%s\t%s\t%s\t%s\n' core_pipeline_flow 0 "$timestamp" "$timestamp" >>"$steps_file"
  printf '%s\t%s\t%s\t%s\n' core_readiness_report 0 "$timestamp" "$timestamp" >>"$steps_file"
  printf '%s\t%s\t%s\t%s\n' headless_readiness_audit 0 "$timestamp" "$timestamp" >>"$steps_file"
else
  run_step embedded_dry_run "${ARIS_WS}/scripts/check_embedded_dry_run.sh" || overall_status=$?
  if [[ "$overall_status" == "0" ]]; then
    run_step documented_commands "${ARIS_WS}/scripts/check_documented_commands.sh" || overall_status=$?
  fi
  if [[ "$overall_status" == "0" ]]; then
    run_step core_pipeline_flow "${ARIS_WS}/scripts/check_core_pipeline_flow.sh" || overall_status=$?
  fi
  if [[ "$overall_status" == "0" ]]; then
    run_step core_readiness_report "${ARIS_WS}/scripts/run_core_readiness_report.sh" || overall_status=$?
  fi
  if [[ "$overall_status" == "0" ]]; then
    run_step headless_readiness_audit "${ARIS_WS}/scripts/check_headless_readiness_audit.sh" || overall_status=$?
  fi
fi

python3 - "$report_file" "$steps_file" "$timestamp" "$ARIS_WS" "$ARIS_LOGS" "$overall_status" <<'PY'
import json
import os
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
steps_path = Path(sys.argv[2])
timestamp = sys.argv[3]
workspace = sys.argv[4]
logs_dir = Path(sys.argv[5])
overall_status = int(sys.argv[6])

steps = []
if steps_path.exists():
    for line in steps_path.read_text(encoding="utf-8").splitlines():
        name, status, started, ended = line.split("\t")
        steps.append(
            {
                "name": name,
                "exit_code": int(status),
                "passed": int(status) == 0,
                "started_utc": started,
                "ended_utc": ended,
            }
        )

def resolved(path: Path) -> str | None:
    return str(path.resolve()) if path.exists() else None

report = {
    "artifact_type": "aris_headless_release_candidate_report",
    "schema_version": 1,
    "timestamp_utc": timestamp,
    "workspace": workspace,
    "logs_dir": str(logs_dir),
    "valid": overall_status == 0 and all(step["passed"] for step in steps),
    "exit_code": overall_status,
    "hardware_scope_active": False,
    "reused_existing_evidence": os.environ.get("ARIS_HEADLESS_RELEASE_REUSE_EXISTING", "0") == "1",
    "steps": steps,
    "evidence": {
        "embedded_dry_run": resolved(logs_dir / "embedded" / "latest_embedded_dry_run.json"),
        "core_pipeline_flow": resolved(logs_dir / "pipeline" / "latest_core_pipeline_flow.json"),
        "core_readiness_report": resolved(logs_dir / "readiness" / "latest.log"),
        "readiness_evidence_index": resolved(logs_dir / "readiness" / "latest_evidence_index.json"),
        "headless_readiness_audit": resolved(logs_dir / "readiness" / "latest_headless_readiness_audit.json"),
    },
}
report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(
    "headless_release_candidate path={} valid={} exit_code={}".format(
        report_path,
        report["valid"],
        overall_status,
    )
)
PY

ln -sf "$report_file" "$latest_file"

"${ARIS_WS}/scripts/generate_readiness_evidence_index.py" \
  --workspace "$ARIS_WS" \
  --logs-dir "$ARIS_LOGS" \
  --out "$final_index_file"
ln -sf "$final_index_file" "$latest_index_file"

python3 - "$report_file" "$final_index_file" <<'PY'
import json
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
index_path = Path(sys.argv[2])
report = json.loads(report_path.read_text(encoding="utf-8"))
report.setdefault("evidence", {})["readiness_evidence_index"] = str(index_path.resolve())
report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

exit "$overall_status"
