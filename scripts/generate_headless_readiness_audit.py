#!/usr/bin/env python3
"""Generate the current headless simulation and embedded readiness audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _latest(paths: list[Path]) -> Path | None:
    existing = [path for path in paths if path.exists()]
    if not existing:
        return None
    return max(existing, key=lambda path: path.stat().st_mtime)


def _read_json(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON artifact must be an object: {path}")
    return data


def _latest_json(logs_dir: Path, subdir: str, pattern: str) -> tuple[Path | None, dict[str, Any] | None]:
    path = _latest(list((logs_dir / subdir).glob(pattern)))
    return path, _read_json(path)


def _criterion(passed: bool, evidence: dict[str, Any] | None, blockers: list[str]) -> dict[str, Any]:
    return {
        "passed": passed,
        "evidence": evidence or {},
        "blockers": blockers,
    }


def _int_value(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _repeatability_sample_summary(repeat_report: dict[str, Any]) -> dict[str, Any]:
    runs = repeat_report.get("runs")
    if not isinstance(runs, list) or not runs:
        return {
            "runs_with_samples": 0,
            "scan_cloud_samples_min": None,
            "global_path_points_min": None,
            "cmd_samples_min": None,
            "sample_floor_passed": False,
        }
    scan_cloud = [_int_value(run.get("scan_cloud_samples")) for run in runs if isinstance(run, dict)]
    global_path = [_int_value(run.get("global_path_points")) for run in runs if isinstance(run, dict)]
    cmd = [_int_value(run.get("cmd_samples")) for run in runs if isinstance(run, dict)]
    runs_with_samples = min(len(scan_cloud), len(global_path), len(cmd))
    scan_min = min(scan_cloud) if scan_cloud else None
    path_min = min(global_path) if global_path else None
    cmd_min = min(cmd) if cmd else None
    return {
        "runs_with_samples": runs_with_samples,
        "scan_cloud_samples_min": scan_min,
        "global_path_points_min": path_min,
        "cmd_samples_min": cmd_min,
        "sample_floor_passed": (
            runs_with_samples >= 2
            and scan_min is not None
            and scan_min >= 5
            and path_min is not None
            and path_min >= 2
            and cmd_min is not None
            and cmd_min >= 20
        ),
    }


def generate_audit(workspace: Path, logs_dir: Path) -> dict[str, Any]:
    index_path, index = _latest_json(logs_dir, "readiness", "evidence_index_*.json")
    embedded_path, embedded_report = _latest_json(logs_dir, "embedded", "embedded_dry_run_*.json")
    v5_path, latest_v5_report = _latest_json(logs_dir, "obstacles", "v5_dynamic_obstacle_*.json")
    v5_replay_path, latest_v5_replay_report = _latest_json(
        logs_dir,
        "obstacles",
        "v5_obstacle_bag_replay_*.json",
    )
    v6_path, latest_v6_report = _latest_json(logs_dir, "maps", "v3_semantic_map_*.v6_review.json")
    pipeline_path, latest_pipeline_report = _latest_json(logs_dir, "pipeline", "core_pipeline_flow_*.json")
    repeat_path, latest_repeat_report = _latest_json(
        logs_dir,
        "pipeline",
        "core_pipeline_repeatability_*.json",
    )

    criteria: dict[str, dict[str, Any]] = {}
    readiness = (index or {}).get("readiness") or {}
    readiness_passed = readiness.get("result") == "PASS" and readiness.get("exit_code") in ("0", 0)
    no_skip_passed = (
        readiness_passed
        and readiness.get("skip_gazebo") == "0"
        and readiness.get("skip_v3") == "0"
        and readiness.get("real_actuation") == "0"
    )
    criteria["core_readiness_no_skip"] = _criterion(
        no_skip_passed,
        {
            "readiness_index_path": str(index_path) if index_path else None,
            "readiness_log_path": readiness.get("path"),
            "result": readiness.get("result"),
            "exit_code": readiness.get("exit_code"),
            "skip_gazebo": readiness.get("skip_gazebo"),
            "skip_v3": readiness.get("skip_v3"),
            "real_actuation": readiness.get("real_actuation"),
        },
        [] if no_skip_passed else ["latest readiness must PASS with skip_gazebo=0, skip_v3=0, real_actuation=0"],
    )

    v2_bag = (index or {}).get("v2_lidar_bag")
    v2_passed = no_skip_passed and bool(v2_bag)
    criteria["v2_gazebo_stack"] = _criterion(
        v2_passed,
        {
            "bag_metadata_path": (v2_bag or {}).get("metadata_path") if isinstance(v2_bag, dict) else None,
            "message_count": (v2_bag or {}).get("message_count") if isinstance(v2_bag, dict) else None,
        },
        [] if v2_passed else ["latest no-skip Gazebo readiness and V2 LiDAR bag evidence are required"],
    )

    v3 = (index or {}).get("v3_semantic_map") or {}
    v6 = (index or {}).get("v6_semantic_review") or {}
    manifest = v3.get("manifest") or {}
    compare = v3.get("compare") or {}
    review = v6.get("report") or latest_v6_report or {}
    semantic_passed = (
        bool(manifest.get("valid"))
        and bool(compare.get("valid"))
        and review.get("advisory_only") is True
        and review.get("control_authority") == "none"
    )
    criteria["v3_v6_mapping_review"] = _criterion(
        semantic_passed,
        {
            "manifest_path": v3.get("manifest_path"),
            "compare_path": v3.get("compare_path"),
            "review_path": v6.get("report_path") or (str(v6_path) if v6_path else None),
            "advisory_only": review.get("advisory_only"),
            "control_authority": review.get("control_authority"),
        },
        [] if semantic_passed else ["valid V3 manifest/compare and advisory-only V6 review evidence are required"],
    )

    pipeline_index = (index or {}).get("core_pipeline_flow") or {}
    pipeline_report = pipeline_index.get("report") or latest_pipeline_report or {}
    pipeline_stages = pipeline_report.get("stages") or {}
    required_pipeline_stages = (
        "mapping",
        "semantic_hd_map",
        "route_graph",
        "localization",
        "goal_based_planning",
        "autonomous_driving",
    )
    pipeline_passed = pipeline_report.get("valid") is True and all(
        (pipeline_stages.get(stage) or {}).get("passed") is True
        for stage in required_pipeline_stages
    )
    criteria["core_pipeline_flow"] = _criterion(
        pipeline_passed,
        {
            "report_path": pipeline_index.get("report_path") or (str(pipeline_path) if pipeline_path else None),
            "valid": pipeline_report.get("valid"),
            "semantic_map_snapshot": pipeline_report.get("semantic_map_snapshot"),
            "stages": {
                stage: (pipeline_stages.get(stage) or {}).get("passed")
                for stage in required_pipeline_stages
            },
        },
        [] if pipeline_passed else ["valid core pipeline flow report is missing"],
    )

    repeat_index = (index or {}).get("core_pipeline_repeatability") or {}
    repeat_report = repeat_index.get("report") or latest_repeat_report or {}
    repeat_summary = repeat_report.get("summary") or {}
    repeat_samples = _repeatability_sample_summary(repeat_report)
    repeat_passed = (
        repeat_report.get("valid") is True
        and _int_value(repeat_summary.get("runs_completed")) >= 2
        and repeat_summary.get("node_path_stable") is True
        and repeat_summary.get("goal_error_max_m") is not None
        and float(repeat_summary.get("goal_error_max_m")) <= 1.3
        and repeat_samples["sample_floor_passed"] is True
    )
    criteria["core_pipeline_repeatability"] = _criterion(
        repeat_passed,
        {
            "report_path": repeat_index.get("report_path") or (str(repeat_path) if repeat_path else None),
            "valid": repeat_report.get("valid"),
            "runs_completed": repeat_summary.get("runs_completed"),
            "node_path_stable": repeat_summary.get("node_path_stable"),
            "goal_error_max_m": repeat_summary.get("goal_error_max_m"),
            "goal_error_spread_m": repeat_summary.get("goal_error_spread_m"),
            "runs_with_samples": repeat_samples["runs_with_samples"],
            "scan_cloud_samples_min": repeat_samples["scan_cloud_samples_min"],
            "global_path_points_min": repeat_samples["global_path_points_min"],
            "cmd_samples_min": repeat_samples["cmd_samples_min"],
        },
        []
        if repeat_passed
        else ["valid core pipeline repeatability report with at least 2 stable sampled runs is missing"],
    )

    v5 = (index or {}).get("v5_dynamic_obstacle") or {}
    obstacle_report = v5.get("report") or latest_v5_report or {}
    obstacle_metrics = obstacle_report.get("metrics") or v5.get("metrics") or {}
    obstacle_passed = obstacle_report.get("valid") is True and _int_value(obstacle_metrics.get("track_age")) >= 2
    criteria["v5_obstacle"] = _criterion(
        obstacle_passed,
        {
            "report_path": v5.get("report_path") or (str(v5_path) if v5_path else None),
            "valid": obstacle_report.get("valid"),
            "track_age": obstacle_metrics.get("track_age"),
            "detour_min_steering": obstacle_metrics.get("detour_min_steering"),
        },
        [] if obstacle_passed else ["valid V5 dynamic obstacle report with persistent tracking evidence is required"],
    )

    v5_replay = (index or {}).get("v5_obstacle_bag_replay") or {}
    replay_report = v5_replay.get("report") or latest_v5_replay_report or {}
    replay_metrics = replay_report.get("metrics") or {}
    replay_passed = replay_report.get("valid") is True
    criteria["v5_recorded_obstacle_replay"] = _criterion(
        replay_passed,
        {
            "report_path": v5_replay.get("report_path") or (str(v5_replay_path) if v5_replay_path else None),
            "valid": replay_report.get("valid"),
            "bag_path": replay_report.get("bag_path"),
            "advisory_samples": replay_metrics.get("advisory_samples"),
            "action_counts": replay_metrics.get("action_counts"),
        },
        [] if replay_passed else ["valid recorded/replayed V5 obstacle bag score is missing"],
    )

    embedded_report = ((index or {}).get("embedded_dry_run") or {}).get("report") or embedded_report or {}
    embedded_report_path = ((index or {}).get("embedded_dry_run") or {}).get("report_path")
    embedded_passed = embedded_report.get("valid") is True and embedded_report.get("hardware_required") is False
    criteria["embedded_dry_run"] = _criterion(
        embedded_passed,
        {
            "report_path": embedded_report_path or (str(embedded_path) if embedded_path else None),
            "valid": embedded_report.get("valid"),
            "exit_code": embedded_report.get("exit_code"),
            "hardware_required": embedded_report.get("hardware_required"),
            "checks": embedded_report.get("checks"),
        },
        [] if embedded_passed else ["valid hardware-free embedded dry-run report is missing"],
    )

    blockers: list[str] = []
    for name, criterion in criteria.items():
        if criterion["passed"]:
            continue
        blockers.extend(f"{name}: {blocker}" for blocker in criterion["blockers"])

    headless_ready = all(criterion["passed"] for criterion in criteria.values())
    return {
        "artifact_type": "aris_headless_readiness_audit",
        "schema_version": 1,
        "scope": "headless_simulation_embedded",
        "workspace": str(workspace),
        "logs_dir": str(logs_dir),
        "achieved": headless_ready,
        "headless_ready": headless_ready,
        "hardware_scope_active": False,
        "safe_to_enable_real_actuation": False,
        "criteria": criteria,
        "blockers": blockers,
        "future_blockers_not_in_scope": [
            "hil_preflight",
            "field_validation",
        ],
        "evidence": {
            "readiness_index": str(index_path) if index_path else None,
            "embedded_dry_run": str(embedded_path) if embedded_path else None,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--logs-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    report = generate_audit(args.workspace, args.logs_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "headless_readiness_audit path={} headless_ready={} blockers={}".format(
            args.out,
            report["headless_ready"],
            len(report["blockers"]),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
