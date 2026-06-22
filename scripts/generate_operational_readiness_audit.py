#!/usr/bin/env python3
"""Generate an ARIS operational readiness audit from evidence artifacts."""

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


def _readiness_index(logs_dir: Path) -> tuple[Path | None, dict[str, Any] | None]:
    path = _latest(list((logs_dir / "readiness").glob("evidence_index_*.json")))
    return path, _read_json(path)


def _latest_field_report(logs_dir: Path) -> tuple[Path | None, dict[str, Any] | None]:
    path = _latest(list((logs_dir / "field").glob("field_validation_*.json")))
    return path, _read_json(path)


def _latest_json(logs_dir: Path, subdir: str, pattern: str) -> tuple[Path | None, dict[str, Any] | None]:
    path = _latest(list((logs_dir / subdir).glob(pattern)))
    return path, _read_json(path)


def generate_audit(workspace: Path, logs_dir: Path) -> dict[str, Any]:
    index_path, index = _readiness_index(logs_dir)
    field_path, field_report = _latest_field_report(logs_dir)
    v5_path, latest_v5_report = _latest_json(logs_dir, "obstacles", "v5_dynamic_obstacle_*.json")
    v5_replay_path, latest_v5_replay_report = _latest_json(
        logs_dir,
        "obstacles",
        "v5_obstacle_bag_replay_*.json",
    )
    v6_path, latest_v6_report = _latest_json(logs_dir, "maps", "v3_semantic_map_*.v6_review.json")
    hil_path, latest_hil_report = _latest_json(logs_dir, "hil", "hil_preflight_*.json")
    criteria: dict[str, dict[str, Any]] = {}

    readiness = (index or {}).get("readiness") or {}
    readiness_passed = (
        readiness.get("result") == "PASS"
        and readiness.get("exit_code") in ("0", 0)
    )
    no_skip_passed = (
        readiness_passed
        and readiness.get("skip_gazebo") == "0"
        and readiness.get("skip_v3") == "0"
        and readiness.get("real_actuation") == "0"
    )
    criteria["docs_build_run"] = _criterion(
        readiness_passed,
        {
            "readiness_index_path": str(index_path) if index_path else None,
            "readiness_log_path": readiness.get("path"),
            "result": readiness.get("result"),
            "exit_code": readiness.get("exit_code"),
        },
        [] if readiness_passed else ["latest readiness evidence is missing or not PASS"],
    )
    criteria["core_pipeline_3d_sim"] = _criterion(
        no_skip_passed,
        {
            "readiness_index_path": str(index_path) if index_path else None,
            "skip_gazebo": readiness.get("skip_gazebo"),
            "skip_v3": readiness.get("skip_v3"),
            "real_actuation": readiness.get("real_actuation"),
        },
        [] if no_skip_passed else ["latest readiness must PASS with skip_gazebo=0, skip_v3=0, real_actuation=0"],
    )

    v2_bag = (index or {}).get("v2_lidar_bag")
    v2_gazebo_passed = no_skip_passed and bool(v2_bag)
    criteria["v2_gazebo_stack"] = _criterion(
        v2_gazebo_passed,
        {
            "bag_metadata_path": (v2_bag or {}).get("metadata_path") if isinstance(v2_bag, dict) else None,
            "message_count": (v2_bag or {}).get("message_count") if isinstance(v2_bag, dict) else None,
        },
        [] if v2_gazebo_passed else ["latest no-skip Gazebo readiness and V2 LiDAR bag evidence are required"],
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
    criteria["v5_obstacle_bag_replay"] = _criterion(
        replay_passed,
        {
            "report_path": v5_replay.get("report_path") or (str(v5_replay_path) if v5_replay_path else None),
            "valid": replay_report.get("valid"),
            "bag_path": replay_report.get("bag_path"),
            "advisory_samples": replay_metrics.get("advisory_samples"),
            "action_counts": replay_metrics.get("action_counts"),
        },
        [] if replay_passed else ["valid operator or real/replayed V5 obstacle bag score is missing"],
    )

    hil = (index or {}).get("hil_preflight") or {}
    hil_report = hil.get("report") or latest_hil_report or {}
    hil_passed = hil_report.get("ready_for_hil") is True
    criteria["hil_preflight"] = _criterion(
        hil_passed,
        {
            "report_path": hil.get("report_path") or (str(hil_path) if hil_path else None),
            "ready_for_hil": hil_report.get("ready_for_hil"),
            "safe_to_enable_real_actuation": hil_report.get("safe_to_enable_real_actuation"),
            "blockers": hil_report.get("blockers", []),
        },
        [] if hil_passed else ["HIL preflight is not ready"],
    )

    field_passed = field_report is not None and field_report.get("valid") is True
    field_summary = field_report.get("summary", {}) if field_report else {}
    criteria["field_validation"] = _criterion(
        field_passed,
        {
            "report_path": str(field_path) if field_path else None,
            "valid": field_report.get("valid") if field_report else None,
            "field_run_id": field_summary.get("field_run_id"),
            "route_completed": field_summary.get("route_completed"),
            "goal_error_m": field_summary.get("goal_error_m"),
            "estop_count": field_summary.get("estop_count"),
            "fault_count": field_summary.get("fault_count"),
        },
        [] if field_passed else ["closed-site field validation evidence is missing"],
    )

    blockers: list[str] = []
    for name, criterion in criteria.items():
        if criterion["passed"]:
            continue
        blockers.extend(f"{name}: {blocker}" for blocker in criterion["blockers"])

    safe_to_enable = bool(hil_report.get("safe_to_enable_real_actuation")) and field_passed
    achieved = all(criterion["passed"] for criterion in criteria.values()) and safe_to_enable

    return {
        "artifact_type": "aris_operational_readiness_audit",
        "schema_version": 1,
        "workspace": str(workspace),
        "logs_dir": str(logs_dir),
        "achieved": achieved,
        "practical_use_ready": achieved,
        "safe_to_enable_real_actuation": safe_to_enable,
        "criteria": criteria,
        "blockers": blockers,
        "evidence": {
            "readiness_index": str(index_path) if index_path else None,
            "field_validation": str(field_path) if field_path else None,
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
        "operational_readiness_audit path={} achieved={} blockers={}".format(
            args.out,
            report["achieved"],
            len(report["blockers"]),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
