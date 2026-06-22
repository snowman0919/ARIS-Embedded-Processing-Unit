#!/usr/bin/env python3
"""Summarize repeated ARIS core-pipeline flow reports."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


REQUIRED_STAGES = (
    "mapping",
    "semantic_hd_map",
    "route_graph",
    "localization",
    "goal_based_planning",
    "autonomous_driving",
)


def route_signature(node_path: list[str] | tuple[str, ...] | None) -> list[str]:
    nodes = list(node_path or [])
    for idx, node in enumerate(nodes):
        if str(node).startswith("detour"):
            return nodes[idx:]
    return nodes


def route_signature_stable(signatures: list[tuple[str, ...]], expected_runs: int) -> bool:
    if len(signatures) != expected_runs or not signatures:
        return False
    shortest = min(signatures, key=len)
    if len(shortest) < 2 or shortest[-1] != "goal":
        return False
    return all(len(signature) >= len(shortest) and signature[-len(shortest) :] == shortest for signature in signatures)


def summarize_reports(paths: list[Path], expected_runs: int, workspace: str, logs_dir: str) -> dict[str, Any]:
    run_reports = []
    failures: list[str] = []

    if len(paths) != expected_runs:
        failures.append(f"expected {expected_runs} run reports, found {len(paths)}")

    for index, path in enumerate(paths, start=1):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - preserve validator diagnostics in JSON.
            failures.append(f"run {index} report could not be read: {path}: {exc}")
            continue
        stages = report.get("stages") or {}
        stage_passed = {stage: (stages.get(stage) or {}).get("passed") is True for stage in REQUIRED_STAGES}
        autonomous = stages.get("autonomous_driving") or {}
        route_graph = stages.get("route_graph") or {}
        localization = stages.get("localization") or {}
        planning = stages.get("goal_based_planning") or {}
        node_path = route_graph.get("node_path") or []
        signature = route_signature(node_path)
        run_summary = {
            "run": index,
            "report_path": str(path),
            "valid": report.get("valid") is True,
            "stage_passed": stage_passed,
            "node_path": node_path,
            "route_signature": signature,
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
    scan_cloud_samples = [int(item["scan_cloud_samples"]) for item in run_reports if item.get("scan_cloud_samples") is not None]
    global_path_points = [int(item["global_path_points"]) for item in run_reports if item.get("global_path_points") is not None]
    cmd_samples = [int(item["cmd_samples"]) for item in run_reports if item.get("cmd_samples") is not None]
    signatures = [tuple(item.get("route_signature") or []) for item in run_reports if item.get("route_signature")]
    goal_error_max = max(goal_errors) if goal_errors else math.inf
    goal_error_spread = (max(goal_errors) - min(goal_errors)) if len(goal_errors) >= 2 else math.inf
    signature_stable = route_signature_stable(signatures, expected_runs)

    if len(goal_errors) != expected_runs:
        failures.append("every run must report goal_error_m")
    if len(scan_cloud_samples) != expected_runs:
        failures.append("every run must report scan_cloud_samples")
    if len(global_path_points) != expected_runs:
        failures.append("every run must report global_path_points")
    if len(cmd_samples) != expected_runs:
        failures.append("every run must report cmd_samples")
    if goal_error_max > 1.3:
        failures.append(f"max goal error too high: {goal_error_max:.3f}")
    if goal_error_spread > 0.75:
        failures.append(f"goal error spread too high: {goal_error_spread:.3f}")
    if not signature_stable:
        failures.append(f"route signature changed across runs: {signatures}")

    summary = {
        "runs_requested": expected_runs,
        "runs_completed": len(run_reports),
        "node_path_stable": signature_stable,
        "route_signature_stable": signature_stable,
        "route_signature": list(min(signatures, key=len)) if signatures and signature_stable else (list(signatures[0]) if signatures else []),
        "goal_error_max_m": None if math.isinf(goal_error_max) else goal_error_max,
        "goal_error_spread_m": None if math.isinf(goal_error_spread) else goal_error_spread,
        "scan_cloud_samples_min": min(scan_cloud_samples) if scan_cloud_samples else None,
        "global_path_points_min": min(global_path_points) if global_path_points else None,
        "cmd_samples_min": min(cmd_samples) if cmd_samples else None,
    }
    return {
        "artifact_type": "aris_core_pipeline_repeatability_report",
        "schema_version": 1,
        "workspace": workspace,
        "logs_dir": logs_dir,
        "valid": not failures,
        "summary": summary,
        "runs": run_reports,
        "failures": failures,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports-file", type=Path, required=True)
    parser.add_argument("--expected-runs", type=int, required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--logs-dir", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    paths = [Path(line) for line in args.reports_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    result = summarize_reports(paths, args.expected_runs, args.workspace, args.logs_dir)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = result["summary"]
    print(
        "core_pipeline_repeatability path={} valid={} runs={} goal_error_max={} spread={}".format(
            args.out,
            result["valid"],
            len(result["runs"]),
            summary["goal_error_max_m"],
            summary["goal_error_spread_m"],
        )
    )
    if result["failures"]:
        raise SystemExit("; ".join(result["failures"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
