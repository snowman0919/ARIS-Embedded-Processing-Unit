#!/usr/bin/env python3
"""Generate an index of the latest ARIS readiness evidence artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

import yaml


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _latest(paths: list[Path]) -> Path | None:
    existing = [path for path in paths if path.exists()]
    if not existing:
        return None
    return max(existing, key=lambda path: path.stat().st_mtime)


def _read_key_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            if re.fullmatch(r"[A-Za-z0-9_]+", key):
                values[key] = value
    return values


def _read_json(path: Path | None) -> dict[str, Any] | None:
    if not path or not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON artifact must be an object: {path}")
    return data


def _read_v5_dynamic_obstacle(readiness_log: Path | None) -> dict[str, float] | None:
    if not readiness_log or not readiness_log.exists():
        return None
    for line in readiness_log.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("v5_dynamic_obstacle "):
            continue
        metrics: dict[str, float] = {}
        for item in line.split()[1:]:
            if "=" not in item:
                continue
            key, value = item.split("=", 1)
            if re.fullmatch(r"[A-Za-z0-9_]+", key):
                metrics[key] = float(value)
        return metrics or None
    return None


def _latest_bag_metadata(logs_dir: Path) -> Path | None:
    return _latest(list((logs_dir / "bags").glob("*/metadata.yaml")))


def _bag_summary(metadata_path: Path | None) -> dict[str, Any] | None:
    if metadata_path is None:
        return None
    metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
    info = metadata.get("rosbag2_bagfile_information", {}) if isinstance(metadata, dict) else {}
    topics = {}
    for item in info.get("topics_with_message_count", []):
        topic_metadata = item.get("topic_metadata", {})
        name = topic_metadata.get("name")
        if name:
            topics[str(name)] = {
                "type": str(topic_metadata.get("type", "")),
                "count": int(item.get("message_count", 0)),
            }
    return {
        "path": str(metadata_path.parent),
        "metadata_path": str(metadata_path),
        "storage": info.get("storage_identifier"),
        "duration_s": int(info.get("duration", {}).get("nanoseconds", 0)) / 1e9,
        "message_count": int(info.get("message_count", 0)),
        "topics": topics,
        "sha256": _sha256(metadata_path),
    }


def generate_index(workspace: Path, logs_dir: Path) -> dict[str, Any]:
    readiness_log = _latest(list((logs_dir / "readiness").glob("core_readiness_*.log")))
    map_manifest = _latest(list((logs_dir / "maps").glob("v3_semantic_map_*.manifest.json")))
    map_compare = _latest(list((logs_dir / "maps").glob("v3_semantic_map_*.compare.json")))
    semantic_review = _latest(list((logs_dir / "maps").glob("v3_semantic_map_*.v6_review.json")))
    obstacle_report = _latest(list((logs_dir / "obstacles").glob("v5_dynamic_obstacle_*.json")))
    obstacle_replay_report = _latest(list((logs_dir / "obstacles").glob("v5_obstacle_bag_replay_*.json")))
    hil_preflight = _latest(list((logs_dir / "hil").glob("hil_preflight_*.json")))
    field_validation = _latest(list((logs_dir / "field").glob("field_validation_*.json")))
    embedded_dry_run = _latest(list((logs_dir / "embedded").glob("embedded_dry_run_*.json")))
    core_pipeline_flow = _latest(list((logs_dir / "pipeline").glob("core_pipeline_flow_*.json")))
    operational_audit = _latest(list((logs_dir / "readiness").glob("operational_readiness_audit_*.json")))
    headless_audit = _latest(list((logs_dir / "readiness").glob("headless_readiness_audit_*.json")))
    bag_metadata = _latest_bag_metadata(logs_dir)

    readiness_values = _read_key_values(readiness_log) if readiness_log else {}
    index = {
        "artifact_type": "aris_readiness_evidence_index",
        "workspace": str(workspace),
        "logs_dir": str(logs_dir),
        "git": {
            "branch": readiness_values.get("git_branch"),
            "commit": readiness_values.get("git_commit"),
        },
        "readiness": None,
        "v2_lidar_bag": _bag_summary(bag_metadata),
        "v3_semantic_map": {
            "manifest": _read_json(map_manifest),
            "manifest_path": str(map_manifest) if map_manifest else None,
            "compare": _read_json(map_compare),
            "compare_path": str(map_compare) if map_compare else None,
        },
        "v5_dynamic_obstacle": {
            "metrics": _read_v5_dynamic_obstacle(readiness_log),
            "report": _read_json(obstacle_report),
            "report_path": str(obstacle_report) if obstacle_report else None,
        },
        "v5_obstacle_bag_replay": {
            "report": _read_json(obstacle_replay_report),
            "report_path": str(obstacle_replay_report) if obstacle_replay_report else None,
        },
        "v6_semantic_review": {
            "report": _read_json(semantic_review),
            "report_path": str(semantic_review) if semantic_review else None,
        },
        "hil_preflight": {
            "report": _read_json(hil_preflight),
            "report_path": str(hil_preflight) if hil_preflight else None,
        },
        "field_validation": {
            "report": _read_json(field_validation),
            "report_path": str(field_validation) if field_validation else None,
        },
        "embedded_dry_run": {
            "report": _read_json(embedded_dry_run),
            "report_path": str(embedded_dry_run) if embedded_dry_run else None,
        },
        "core_pipeline_flow": {
            "report": _read_json(core_pipeline_flow),
            "report_path": str(core_pipeline_flow) if core_pipeline_flow else None,
        },
        "operational_readiness_audit": {
            "report": _read_json(operational_audit),
            "report_path": str(operational_audit) if operational_audit else None,
        },
        "headless_readiness_audit": {
            "report": _read_json(headless_audit),
            "report_path": str(headless_audit) if headless_audit else None,
        },
    }

    if readiness_log:
        index["readiness"] = {
            "path": str(readiness_log),
            "sha256": _sha256(readiness_log),
            "result": readiness_values.get("result"),
            "exit_code": readiness_values.get("exit_code"),
            "timestamp_utc": readiness_values.get("timestamp_utc"),
            "skip_v3": readiness_values.get("skip_v3"),
            "skip_gazebo": readiness_values.get("skip_gazebo"),
            "real_actuation": readiness_values.get("real_actuation"),
        }
    return index


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--logs-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    index = generate_index(args.workspace, args.logs_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "readiness_evidence_index path={} readiness={} v2_bag={} v3_manifest={} v3_compare={}".format(
            args.out,
            index["readiness"]["result"] if index.get("readiness") else None,
            bool(index.get("v2_lidar_bag")),
            bool(index.get("v3_semantic_map", {}).get("manifest")),
            bool(index.get("v3_semantic_map", {}).get("compare")),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
