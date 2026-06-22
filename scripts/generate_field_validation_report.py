#!/usr/bin/env python3
"""Generate a closed-site ARIS field-validation report from an operator manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_MANIFEST_KEYS = (
    "site_id",
    "operator",
    "route_id",
    "field_run_id",
    "odd",
    "metrics",
    "evidence",
    "approvals",
)


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON artifact must be an object: {path}")
    return data


def _latest(paths: list[Path]) -> Path | None:
    existing = [path for path in paths if path.exists()]
    if not existing:
        return None
    return max(existing, key=lambda path: path.stat().st_mtime)


def _latest_json(logs_dir: Path, subdir: str, pattern: str) -> tuple[Path | None, dict[str, Any] | None]:
    path = _latest(list((logs_dir / subdir).glob(pattern)))
    if path is None:
        return None, None
    return path, _read_json(path)


def _bool(value: Any) -> bool:
    return value is True


def _float_value(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int_value(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def generate_report(workspace: Path, logs_dir: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = _read_json(manifest_path)
    latest_hil_path, latest_hil = _latest_json(logs_dir, "hil", "hil_preflight_*.json")
    latest_obstacle_path, latest_obstacle = _latest_json(
        logs_dir,
        "obstacles",
        "v5_obstacle_bag_replay_*.json",
    )

    failures: list[str] = []
    for key in REQUIRED_MANIFEST_KEYS:
        if key not in manifest:
            failures.append(f"manifest missing required key: {key}")

    odd = manifest.get("odd") if isinstance(manifest.get("odd"), dict) else {}
    metrics = manifest.get("metrics") if isinstance(manifest.get("metrics"), dict) else {}
    evidence = manifest.get("evidence") if isinstance(manifest.get("evidence"), dict) else {}
    approvals = manifest.get("approvals") if isinstance(manifest.get("approvals"), dict) else {}

    route_completed = _bool(metrics.get("route_completed"))
    if not route_completed:
        failures.append("field route was not completed")
    if _float_value(metrics.get("goal_error_m"), default=999.0) > _float_value(
        metrics.get("max_goal_error_m"),
        default=1.0,
    ):
        failures.append("goal error exceeds field threshold")
    if _float_value(metrics.get("max_speed_mps"), default=999.0) > _float_value(
        metrics.get("speed_limit_mps"),
        default=1.5,
    ):
        failures.append("speed exceeded field limit")
    if _int_value(metrics.get("estop_count")) != 0:
        failures.append("E-stop occurred during field validation")
    if _int_value(metrics.get("fault_count")) != 0:
        failures.append("vehicle fault occurred during field validation")
    if _int_value(metrics.get("operator_takeover_count")) != 0:
        failures.append("operator takeover occurred during field validation")

    if not _bool(odd.get("closed_site")):
        failures.append("ODD must be closed-site")
    if not _bool(odd.get("pedestrian_separated")):
        failures.append("ODD must separate pedestrians during validation")

    if evidence.get("hil_preflight_report") is None:
        failures.append("manifest must cite a HIL preflight report")
    if evidence.get("v5_obstacle_bag_replay_report") is None:
        failures.append("manifest must cite a V5 obstacle bag replay report")
    if evidence.get("field_bag") is None:
        failures.append("manifest must cite a field rosbag or run log")
    if not _bool(approvals.get("operator_reviewed")):
        failures.append("operator review approval is required")
    if not _bool(approvals.get("safety_reviewed")):
        failures.append("safety review approval is required")

    if latest_hil is None:
        failures.append("latest HIL preflight evidence is missing")
    elif latest_hil.get("ready_for_hil") is not True:
        failures.append("latest HIL preflight is not ready")
    if latest_obstacle is None:
        failures.append("latest V5 obstacle bag replay evidence is missing")
    elif latest_obstacle.get("valid") is not True:
        failures.append("latest V5 obstacle bag replay report is not valid")

    return {
        "artifact_type": "aris_field_validation_report",
        "schema_version": 1,
        "workspace": str(workspace),
        "logs_dir": str(logs_dir),
        "manifest_path": str(manifest_path),
        "valid": not failures,
        "failures": failures,
        "summary": {
            "site_id": manifest.get("site_id"),
            "field_run_id": manifest.get("field_run_id"),
            "route_id": manifest.get("route_id"),
            "operator": manifest.get("operator"),
            "route_completed": route_completed,
            "goal_error_m": metrics.get("goal_error_m"),
            "max_speed_mps": metrics.get("max_speed_mps"),
            "estop_count": metrics.get("estop_count"),
            "fault_count": metrics.get("fault_count"),
            "operator_takeover_count": metrics.get("operator_takeover_count"),
        },
        "manifest": manifest,
        "linked_evidence": {
            "latest_hil_preflight": str(latest_hil_path) if latest_hil_path else None,
            "latest_v5_obstacle_bag_replay": str(latest_obstacle_path) if latest_obstacle_path else None,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--logs-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    report = generate_report(args.workspace, args.logs_dir, args.manifest)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "field_validation_report path={} valid={} failures={}".format(
            args.out,
            report["valid"],
            len(report["failures"]),
        )
    )
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
