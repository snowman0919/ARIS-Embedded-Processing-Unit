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

python3 - "$report_file" "$reports_file" "$runs" "$ARIS_WS" "$ARIS_LOGS" <<'PY'
import json
import math
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
reports_path = Path(sys.argv[2])
expected_runs = int(sys.argv[3])
workspace = sys.argv[4]
logs_dir = sys.argv[5]

paths = [Path(line) for line in reports_path.read_text(encoding="utf-8").splitlines() if line.strip()]
run_reports = []
failures = []

def _route_signature(node_path):
    nodes = list(node_path or [])
    for idx, node in enumerate(nodes):
        if str(node).startswith("detour"):
            return nodes[idx:]
    return nodes

if len(paths) != expected_runs:
    failures.append(f"expected {expected_runs} run reports, found {len(paths)}")

for index, path in enumerate(paths, start=1):
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - preserve validator diagnostics in JSON.
        failures.append(f"run {index} report could not be read: {path}: {exc}")
        continue
    stages = report.get("stages") or {}
    required_stages = (
        "mapping",
        "semantic_hd_map",
        "route_graph",
        "localization",
        "goal_based_planning",
        "autonomous_driving",
    )
    stage_passed = {
        stage: (stages.get(stage) or {}).get("passed") is True
        for stage in required_stages
    }
    autonomous = stages.get("autonomous_driving") or {}
    route_graph = stages.get("route_graph") or {}
    localization = stages.get("localization") or {}
    planning = stages.get("goal_based_planning") or {}
    node_path = route_graph.get("node_path") or []
    route_signature = _route_signature(node_path)
    run_summary = {
        "run": index,
        "report_path": str(path),
        "valid": report.get("valid") is True,
        "stage_passed": stage_passed,
        "node_path": node_path,
        "route_signature": route_signature,
        "scan_cloud_samples": localization.get("scan_cloud_samples"),
        "global_path_points": planning.get("global_path_points"),
        "cmd_samples": autonomous.get("cmd_samples"),
        "max_x_m": autonomous.get("max_x_m"),
        "goal_error_m": autonomous.get("goal_error_m"),
    }
    run_reports.append(run_summary)
    if report.get("valid") is not True:
        failures.append(f"run {index} core pipeline report is invalid")
    for stage, passed in stage_passed.items():
        if not passed:
            failures.append(f"run {index} stage failed: {stage}")

goal_errors = [
    float(item["goal_error_m"])
    for item in run_reports
    if item.get("goal_error_m") is not None and math.isfinite(float(item["goal_error_m"]))
]
route_signatures = [
    tuple(item.get("route_signature") or [])
    for item in run_reports
    if item.get("route_signature")
]
goal_error_max = max(goal_errors) if goal_errors else math.inf
goal_error_spread = (max(goal_errors) - min(goal_errors)) if len(goal_errors) >= 2 else math.inf
route_signature_stable = (
    bool(route_signatures)
    and len(set(route_signatures)) == 1
    and len(route_signatures) == expected_runs
)

if len(goal_errors) != expected_runs:
    failures.append("every run must report goal_error_m")
if goal_error_max > 1.3:
    failures.append(f"max goal error too high: {goal_error_max:.3f}")
if goal_error_spread > 0.75:
    failures.append(f"goal error spread too high: {goal_error_spread:.3f}")
if not route_signature_stable:
    failures.append(f"route signature changed across runs: {route_signatures}")

summary = {
    "runs_requested": expected_runs,
    "runs_completed": len(run_reports),
    "node_path_stable": route_signature_stable,
    "route_signature_stable": route_signature_stable,
    "route_signature": list(route_signatures[0]) if route_signatures else [],
    "goal_error_max_m": None if math.isinf(goal_error_max) else goal_error_max,
    "goal_error_spread_m": None if math.isinf(goal_error_spread) else goal_error_spread,
}
result = {
    "artifact_type": "aris_core_pipeline_repeatability_report",
    "schema_version": 1,
    "workspace": workspace,
    "logs_dir": logs_dir,
    "valid": not failures,
    "summary": summary,
    "runs": run_reports,
    "failures": failures,
}
report_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(
    "core_pipeline_repeatability path={} valid={} runs={} goal_error_max={} spread={}".format(
        report_path,
        result["valid"],
        len(run_reports),
        summary["goal_error_max_m"],
        summary["goal_error_spread_m"],
    )
)
if failures:
    raise SystemExit("; ".join(failures))
PY

ln -sf "$report_file" "$latest_file"
