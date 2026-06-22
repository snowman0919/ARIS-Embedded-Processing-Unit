#!/usr/bin/env python3
"""Summarize the latest ARIS headless software-readiness evidence."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
from typing import Any


FRESHNESS_IGNORED_PATHS = {
    "docs/AUTORUN_LOG.md",
    "scripts/summarize_headless_status.py",
    "tests/evidence/test_headless_status_summary.py",
}


def summarize(logs_dir: Path, workspace: Path | None = None) -> dict[str, Any]:
    readiness_dir = logs_dir / "readiness"
    pipeline_dir = logs_dir / "pipeline"
    release_path = _resolve(readiness_dir / "latest_headless_release_candidate.json")
    audit_path = _resolve(readiness_dir / "latest_headless_readiness_audit.json")
    index_path = _resolve(readiness_dir / "latest_evidence_index.json")
    repeat_path = _resolve(pipeline_dir / "latest_core_pipeline_repeatability.json")

    release = _read_json(release_path)
    audit = _read_json(audit_path)
    index = _read_json(index_path)
    repeat = _read_json(repeat_path)
    current_git = _current_git(workspace) if workspace else {"branch": None, "commit": None}
    evidence_git = (index or {}).get("git") or {}
    evidence_commit = evidence_git.get("commit")
    current_commit = current_git.get("commit")
    changed_since_evidence = _changed_since(workspace, str(evidence_commit)) if workspace and evidence_commit else []
    relevant_changes_since_evidence = [
        path for path in changed_since_evidence if path not in FRESHNESS_IGNORED_PATHS
    ]
    evidence_fresh = bool(
        evidence_commit
        and current_commit
        and (
            str(current_commit).startswith(str(evidence_commit))
            or not relevant_changes_since_evidence
        )
    )

    criteria = (audit or {}).get("criteria") or {}
    pipeline = (index or {}).get("core_pipeline_flow", {}).get("report") or {}
    pipeline_stages = pipeline.get("stages") or {}
    repeat_summary = (repeat or {}).get("summary") or {}
    release_steps = [
        {
            "name": step.get("name"),
            "passed": step.get("passed"),
            "exit_code": step.get("exit_code"),
        }
        for step in (release or {}).get("steps", [])
        if isinstance(step, dict)
    ]
    all_release_steps_passed = bool(release_steps) and all(step.get("passed") is True for step in release_steps)
    real_actuation_enabled = os.environ.get("ARIS_ENABLE_REAL_ACTUATION", "0") == "1"
    hardware_scope_active = (audit or {}).get("hardware_scope_active") is True
    safe_to_enable_real_actuation = (audit or {}).get("safe_to_enable_real_actuation") is True

    return {
        "artifact_type": "aris_headless_status_summary",
        "schema_version": 1,
        "logs_dir": str(logs_dir),
        "workspace": str(workspace) if workspace else None,
        "git": {
            "current": current_git,
            "evidence": evidence_git,
            "evidence_fresh_for_head": evidence_fresh,
            "changed_since_evidence": changed_since_evidence,
            "freshness_ignored_paths": sorted(FRESHNESS_IGNORED_PATHS),
            "relevant_changes_since_evidence": relevant_changes_since_evidence,
        },
        "headless_ready": (audit or {}).get("headless_ready") is True,
        "release_valid": (release or {}).get("valid") is True and all_release_steps_passed,
        "hardware_scope_active": hardware_scope_active,
        "real_actuation_enabled": real_actuation_enabled,
        "safe_to_enable_real_actuation": safe_to_enable_real_actuation,
        "execution_scope": {
            "hardware_scope_active": hardware_scope_active,
            "real_actuation_enabled": real_actuation_enabled,
            "safe_to_enable_real_actuation": safe_to_enable_real_actuation,
        },
        "blockers": (audit or {}).get("blockers") or [],
        "criteria": {
            name: {
                "passed": criterion.get("passed"),
                "blockers": criterion.get("blockers") or [],
            }
            for name, criterion in criteria.items()
            if isinstance(criterion, dict)
        },
        "core_pipeline": {
            "valid": pipeline.get("valid"),
            "semantic_map_snapshot": pipeline.get("semantic_map_snapshot"),
            "node_path": (pipeline_stages.get("route_graph") or {}).get("node_path"),
            "goal_error_m": (pipeline_stages.get("autonomous_driving") or {}).get("goal_error_m"),
            "stages": {
                name: (stage or {}).get("passed")
                for name, stage in pipeline_stages.items()
                if isinstance(stage, dict)
            },
        },
        "repeatability": {
            "valid": (repeat or {}).get("valid"),
            "runs_completed": repeat_summary.get("runs_completed"),
            "node_path_stable": repeat_summary.get("node_path_stable"),
            "goal_error_max_m": repeat_summary.get("goal_error_max_m"),
            "goal_error_spread_m": repeat_summary.get("goal_error_spread_m"),
            "scan_cloud_samples_min": repeat_summary.get("scan_cloud_samples_min"),
            "global_path_points_min": repeat_summary.get("global_path_points_min"),
            "cmd_samples_min": repeat_summary.get("cmd_samples_min"),
        },
        "release_steps": release_steps,
        "evidence": {
            "headless_release_candidate": str(release_path) if release_path else None,
            "headless_readiness_audit": str(audit_path) if audit_path else None,
            "readiness_evidence_index": str(index_path) if index_path else None,
            "core_pipeline_repeatability": str(repeat_path) if repeat_path else None,
        },
    }


def _resolve(path: Path) -> Path | None:
    return path.resolve() if path.exists() else None


def _read_json(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON artifact must be an object: {path}")
    return data


def _current_git(workspace: Path | None) -> dict[str, str | None]:
    if workspace is None:
        return {"branch": None, "commit": None}
    return {
        "branch": _git(workspace, "branch", "--show-current"),
        "commit": _git(workspace, "rev-parse", "--short", "HEAD"),
    }


def _git(workspace: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ("git", "-C", str(workspace), *args),
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def _changed_since(workspace: Path, evidence_commit: str) -> list[str]:
    try:
        result = subprocess.run(
            ("git", "-C", str(workspace), "diff", "--name-only", f"{evidence_commit}..HEAD"),
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return []
    return [line for line in result.stdout.splitlines() if line]


def _format_bool(value: bool) -> str:
    return "yes" if value else "no"


def format_text(summary: dict[str, Any]) -> str:
    pipeline = summary["core_pipeline"]
    repeat = summary["repeatability"]
    git = summary.get("git") or {}
    current_git = git.get("current") or {}
    evidence_git = git.get("evidence") or {}
    lines = [
        "ARIS headless status",
        f"  headless_ready: {_format_bool(bool(summary['headless_ready']))}",
        f"  release_valid: {_format_bool(bool(summary['release_valid']))}",
        f"  evidence_fresh_for_head: {_format_bool(bool(git.get('evidence_fresh_for_head')))}",
        f"  current_git: {current_git.get('branch')}@{current_git.get('commit')}",
        f"  evidence_git: {evidence_git.get('branch')}@{evidence_git.get('commit')}",
        f"  hardware_scope_active: {_format_bool(bool(summary['hardware_scope_active']))}",
        f"  real_actuation_enabled: {_format_bool(bool(summary['real_actuation_enabled']))}",
        f"  safe_to_enable_real_actuation: {_format_bool(bool(summary['safe_to_enable_real_actuation']))}",
        f"  blockers: {len(summary['blockers'])}",
        "",
        "Core pipeline",
        f"  valid: {_format_bool(pipeline.get('valid') is True)}",
        "  node_path: {}".format(" -> ".join(pipeline.get("node_path") or []) or "n/a"),
        f"  goal_error_m: {pipeline.get('goal_error_m')}",
        "  stages: {}".format(
            ", ".join(
                f"{name}={_format_bool(value is True)}"
                for name, value in sorted((pipeline.get("stages") or {}).items())
            )
            or "n/a"
        ),
        "",
        "Repeatability",
        f"  valid: {_format_bool(repeat.get('valid') is True)}",
        f"  runs_completed: {repeat.get('runs_completed')}",
        f"  node_path_stable: {_format_bool(repeat.get('node_path_stable') is True)}",
        f"  goal_error_max_m: {repeat.get('goal_error_max_m')}",
        f"  goal_error_spread_m: {repeat.get('goal_error_spread_m')}",
        f"  scan_cloud_samples_min: {repeat.get('scan_cloud_samples_min')}",
        f"  global_path_points_min: {repeat.get('global_path_points_min')}",
        f"  cmd_samples_min: {repeat.get('cmd_samples_min')}",
        "",
        "Release steps",
    ]
    release_steps = summary.get("release_steps") or []
    if release_steps:
        for step in release_steps:
            lines.append(
                "  {}: {} exit_code={}".format(
                    step.get("name"),
                    "pass" if step.get("passed") is True else "fail",
                    step.get("exit_code"),
                )
            )
    else:
        lines.append("  n/a")
    lines.extend([
        "",
        "Evidence",
    ])
    for name, path in summary["evidence"].items():
        lines.append(f"  {name}: {path}")
    if summary["blockers"]:
        lines.append("")
        lines.append("Blockers")
        lines.extend(f"  - {blocker}" for blocker in summary["blockers"])
    if not (git.get("evidence_fresh_for_head")):
        lines.append("")
        lines.append("Freshness")
        lines.append("  latest evidence was not generated from the current HEAD")
        lines.append("  run: just headless-release-candidate")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--logs-dir", type=Path, required=True)
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args(argv)

    summary = summarize(args.logs_dir, args.workspace)
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(format_text(summary))
    return 0 if summary["headless_ready"] and summary["release_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
