#!/usr/bin/env python3
"""Summarize the latest ARIS headless software-readiness evidence."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
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
    now = datetime.now(timezone.utc)
    readiness_dir = logs_dir / "readiness"
    pipeline_dir = logs_dir / "pipeline"
    release_path = _resolve(readiness_dir / "latest_headless_release_candidate.json")
    audit_path = _resolve(readiness_dir / "latest_headless_readiness_audit.json")
    operational_audit_path = _resolve(readiness_dir / "latest_operational_readiness_audit.json")
    index_path = _resolve(readiness_dir / "latest_evidence_index.json")
    branch_policy_path = _resolve(readiness_dir / "latest_branch_policy.json")
    repeat_path = _resolve(pipeline_dir / "latest_core_pipeline_repeatability.json")

    release = _read_json(release_path)
    audit = _read_json(audit_path)
    operational_audit = _read_json(operational_audit_path)
    index = _read_json(index_path)
    branch_policy = _read_json(branch_policy_path)
    repeat = _read_json(repeat_path)
    current_git = _current_git(workspace) if workspace else {"branch": None, "commit": None}
    upstream_sync = _upstream_sync(workspace) if workspace else {}
    evidence_git = (index or {}).get("git") or {}
    evidence_commit = evidence_git.get("commit")
    current_commit = current_git.get("commit")
    changed_since_evidence = _changed_since(workspace, str(evidence_commit)) if workspace and evidence_commit else []
    worktree_changes = _worktree_changes(workspace) if workspace else []
    relevant_changes_since_evidence = [
        path for path in changed_since_evidence if path not in FRESHNESS_IGNORED_PATHS
    ]
    ignored_changes_since_evidence = [
        path for path in changed_since_evidence if path in FRESHNESS_IGNORED_PATHS
    ]
    relevant_worktree_changes = [
        path for path in worktree_changes if path not in FRESHNESS_IGNORED_PATHS
    ]
    ignored_worktree_changes = [
        path for path in worktree_changes if path in FRESHNESS_IGNORED_PATHS
    ]
    evidence_fresh = bool(
        evidence_commit
        and current_commit
        and not relevant_worktree_changes
        and (str(current_commit).startswith(str(evidence_commit)) or not relevant_changes_since_evidence)
    )

    criteria = (audit or {}).get("criteria") or {}
    acceptance_thresholds = (audit or {}).get("acceptance_thresholds") or {}
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
    release_evidence = {
        str(name): str(path)
        for name, path in ((release or {}).get("evidence") or {}).items()
        if path
    }
    all_release_steps_passed = bool(release_steps) and all(step.get("passed") is True for step in release_steps)
    real_actuation_enabled = os.environ.get("ARIS_ENABLE_REAL_ACTUATION", "0") == "1"
    hardware_scope_active = (audit or {}).get("hardware_scope_active") is True
    safe_to_enable_real_actuation = (audit or {}).get("safe_to_enable_real_actuation") is True
    repeatability = {
        "valid": (repeat or {}).get("valid"),
        "runs_completed": repeat_summary.get("runs_completed"),
        "node_path_stable": repeat_summary.get("node_path_stable"),
        "goal_error_max_m": repeat_summary.get("goal_error_max_m"),
        "goal_error_spread_m": repeat_summary.get("goal_error_spread_m"),
        "scan_cloud_samples_min": repeat_summary.get("scan_cloud_samples_min"),
        "global_path_points_min": repeat_summary.get("global_path_points_min"),
        "cmd_samples_min": repeat_summary.get("cmd_samples_min"),
    }
    core_pipeline = {
        "valid": pipeline.get("valid"),
        "semantic_map_snapshot": pipeline.get("semantic_map_snapshot"),
        "node_path": (pipeline_stages.get("route_graph") or {}).get("node_path"),
        "goal_error_m": (pipeline_stages.get("autonomous_driving") or {}).get("goal_error_m"),
        "stages": {
            name: (stage or {}).get("passed")
            for name, stage in pipeline_stages.items()
            if isinstance(stage, dict)
        },
    }

    return {
        "artifact_type": "aris_headless_status_summary",
        "schema_version": 1,
        "logs_dir": str(logs_dir),
        "workspace": str(workspace) if workspace else None,
        "git": {
            "current": current_git,
            "evidence": evidence_git,
            "upstream_sync": upstream_sync,
            "evidence_fresh_for_head": evidence_fresh,
            "freshness_reason": _freshness_reason(
                current_commit=current_commit,
                evidence_commit=evidence_commit,
                relevant_changes=relevant_changes_since_evidence,
                ignored_changes=ignored_changes_since_evidence,
                relevant_worktree_changes=relevant_worktree_changes,
                ignored_worktree_changes=ignored_worktree_changes,
            ),
            "changed_since_evidence": changed_since_evidence,
            "freshness_ignored_paths": sorted(FRESHNESS_IGNORED_PATHS),
            "ignored_changes_since_evidence": ignored_changes_since_evidence,
            "relevant_changes_since_evidence": relevant_changes_since_evidence,
            "worktree_changes": worktree_changes,
            "ignored_worktree_changes": ignored_worktree_changes,
            "relevant_worktree_changes": relevant_worktree_changes,
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
        "operational_scope": (operational_audit or {}).get("scope_status") or {},
        "blockers": (audit or {}).get("blockers") or [],
        "criteria": {
            name: {
                "passed": criterion.get("passed"),
                "blockers": criterion.get("blockers") or [],
            }
            for name, criterion in criteria.items()
            if isinstance(criterion, dict)
        },
        "acceptance_thresholds": acceptance_thresholds,
        "acceptance_evaluation": _acceptance_evaluation(core_pipeline, repeatability, acceptance_thresholds),
        "core_pipeline": core_pipeline,
        "repeatability": repeatability,
        "main_sync": (branch_policy or {}).get("main_sync") or {},
        "release_steps": release_steps,
        "release_evidence": release_evidence,
        "evidence_age": {
            "headless_release_candidate": _artifact_age(release_path, now),
            "headless_readiness_audit": _artifact_age(audit_path, now),
            "operational_readiness_audit": _artifact_age(operational_audit_path, now),
            "readiness_evidence_index": _artifact_age(index_path, now),
            "branch_policy": _artifact_age(branch_policy_path, now),
            "core_pipeline_repeatability": _artifact_age(repeat_path, now),
        },
        "evidence": {
            "headless_release_candidate": str(release_path) if release_path else None,
            "headless_readiness_audit": str(audit_path) if audit_path else None,
            "operational_readiness_audit": str(operational_audit_path) if operational_audit_path else None,
            "readiness_evidence_index": str(index_path) if index_path else None,
            "branch_policy": str(branch_policy_path) if branch_policy_path else None,
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


def _artifact_age(path: Path | None, now: datetime) -> dict[str, Any]:
    if path is None or not path.exists():
        return {
            "path": None,
            "mtime_utc": None,
            "age_seconds": None,
        }
    mtime = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    return {
        "path": str(path),
        "mtime_utc": mtime.isoformat().replace("+00:00", "Z"),
        "age_seconds": max(0, int((now - mtime).total_seconds())),
    }


def _float_value(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_value(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _acceptance_evaluation(
    core_pipeline: dict[str, Any],
    repeatability: dict[str, Any],
    thresholds: dict[str, Any],
) -> dict[str, Any]:
    pipeline_thresholds = thresholds.get("core_pipeline_flow") or {}
    repeat_thresholds = thresholds.get("core_pipeline_repeatability") or {}
    required_stages = [
        str(stage)
        for stage in pipeline_thresholds.get("required_stages", [])
    ]
    observed_stages = core_pipeline.get("stages") or {}
    missing_or_failed_stages = [
        stage
        for stage in required_stages
        if observed_stages.get(stage) is not True
    ]

    max_goal_error = _float_value(repeat_thresholds.get("max_goal_error_m"))
    goal_error = _float_value(repeatability.get("goal_error_max_m"))
    runs_required = _int_value(repeat_thresholds.get("min_runs_completed"))
    runs_observed = _int_value(repeatability.get("runs_completed"))
    scan_required = _int_value(repeat_thresholds.get("min_scan_cloud_samples"))
    scan_observed = _int_value(repeatability.get("scan_cloud_samples_min"))
    path_required = _int_value(repeat_thresholds.get("min_global_path_points"))
    path_observed = _int_value(repeatability.get("global_path_points_min"))
    cmd_required = _int_value(repeat_thresholds.get("min_cmd_samples"))
    cmd_observed = _int_value(repeatability.get("cmd_samples_min"))

    margins = {
        "runs_completed": _margin_min(runs_observed, runs_required),
        "goal_error_m": _margin_max(goal_error, max_goal_error),
        "scan_cloud_samples": _margin_min(scan_observed, scan_required),
        "global_path_points": _margin_min(path_observed, path_required),
        "cmd_samples": _margin_min(cmd_observed, cmd_required),
    }
    repeatability_passed = all(
        margin is None or margin >= 0
        for margin in margins.values()
    ) and (
        repeat_thresholds.get("node_path_stable") is not True
        or repeatability.get("node_path_stable") is True
    )
    return {
        "core_pipeline_flow": {
            "required_stages": required_stages,
            "missing_or_failed_stages": missing_or_failed_stages,
            "passed": bool(required_stages) and not missing_or_failed_stages,
        },
        "core_pipeline_repeatability": {
            "passed": repeatability_passed,
            "margins": margins,
        },
    }


def _margin_min(observed: int | None, required: int | None) -> int | None:
    if observed is None or required is None:
        return None
    return observed - required


def _margin_max(observed: float | None, maximum: float | None) -> float | None:
    if observed is None or maximum is None:
        return None
    return maximum - observed


def _freshness_reason(
    *,
    current_commit: object,
    evidence_commit: object,
    relevant_changes: list[str],
    ignored_changes: list[str],
    relevant_worktree_changes: list[str],
    ignored_worktree_changes: list[str],
) -> str:
    if not current_commit or not evidence_commit:
        return "missing_git_evidence"
    if relevant_worktree_changes:
        return "runtime_relevant_worktree_changes"
    if str(current_commit).startswith(str(evidence_commit)):
        return "matching_head"
    if relevant_changes:
        return "runtime_relevant_changes_since_evidence"
    if ignored_changes or ignored_worktree_changes:
        return "ignored_changes_only"
    return "no_runtime_relevant_changes_since_evidence"


def _current_git(workspace: Path | None) -> dict[str, str | None]:
    if workspace is None:
        return {"branch": None, "commit": None}
    return {
        "branch": _git(workspace, "branch", "--show-current"),
        "commit": _git(workspace, "rev-parse", "--short", "HEAD"),
    }


def _upstream_sync(workspace: Path | None) -> dict[str, Any]:
    if workspace is None:
        return {}
    upstream = _git(workspace, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    head = _git(workspace, "branch", "--show-current")
    if not upstream or not head:
        return {
            "available": False,
            "upstream": upstream,
            "head": head,
            "upstream_ahead": None,
            "local_ahead": None,
            "local_contains_upstream": False,
        }
    counts = _git(workspace, "rev-list", "--left-right", "--count", f"{upstream}...HEAD")
    try:
        upstream_ahead, local_ahead = [int(part) for part in str(counts).split()]
    except (TypeError, ValueError):
        return {
            "available": False,
            "upstream": upstream,
            "head": head,
            "upstream_ahead": None,
            "local_ahead": None,
            "local_contains_upstream": False,
        }
    return {
        "available": True,
        "upstream": upstream,
        "head": head,
        "upstream_ahead": upstream_ahead,
        "local_ahead": local_ahead,
        "local_contains_upstream": upstream_ahead == 0,
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


def _worktree_changes(workspace: Path) -> list[str]:
    paths: set[str] = set()
    commands = [
        ("diff", "--name-only", "HEAD"),
        ("diff", "--name-only", "--cached"),
        ("ls-files", "--others", "--exclude-standard"),
    ]
    for args in commands:
        try:
            result = subprocess.run(
                ("git", "-C", str(workspace), *args),
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError):
            continue
        paths.update(line for line in result.stdout.splitlines() if line)
    return sorted(paths)


def _format_bool(value: bool) -> str:
    return "yes" if value else "no"


def _format_age(age: dict[str, Any] | None) -> str:
    if not age or age.get("age_seconds") is None:
        return "n/a"
    seconds = int(age["age_seconds"])
    if seconds < 60:
        return f"{seconds}s"
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {seconds}s"
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return f"{hours}h {minutes}m"
    days, hours = divmod(hours, 24)
    return f"{days}d {hours}h"


def _format_margin(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value)


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
        f"  evidence_freshness_reason: {git.get('freshness_reason')}",
        f"  current_git: {current_git.get('branch')}@{current_git.get('commit')}",
        f"  evidence_git: {evidence_git.get('branch')}@{evidence_git.get('commit')}",
        f"  hardware_scope_active: {_format_bool(bool(summary['hardware_scope_active']))}",
        f"  real_actuation_enabled: {_format_bool(bool(summary['real_actuation_enabled']))}",
        f"  safe_to_enable_real_actuation: {_format_bool(bool(summary['safe_to_enable_real_actuation']))}",
        f"  blockers: {len(summary['blockers'])}",
        "",
        "Operational scope",
    ]
    operational_scope = summary.get("operational_scope") or {}
    if operational_scope:
        lines.extend([
            f"  current_scope: {operational_scope.get('current_scope')}",
            "  headless_simulation_embedded_ready: {}".format(
                _format_bool(operational_scope.get("headless_simulation_embedded_ready") is True)
            ),
            "  hardware_evidence_ready: {}".format(
                _format_bool(operational_scope.get("hardware_evidence_ready") is True)
            ),
            "  full_operational_ready: {}".format(
                _format_bool(operational_scope.get("full_operational_ready") is True)
            ),
        ])
        remaining = operational_scope.get("remaining_evidence") or []
        if remaining:
            lines.append(
                "  remaining_evidence: {}".format(
                    ", ".join(str(item.get("criterion")) for item in remaining if isinstance(item, dict))
                )
            )
        else:
            lines.append("  remaining_evidence: none")
    else:
        lines.append("  n/a")
    lines.extend([
        "",
        "Upstream sync",
    ]
    )
    upstream_sync = git.get("upstream_sync") or {}
    if upstream_sync and upstream_sync.get("available") is True:
        lines.extend([
            f"  upstream: {upstream_sync.get('upstream')}",
            f"  head: {upstream_sync.get('head')}",
            f"  upstream_ahead: {upstream_sync.get('upstream_ahead')}",
            f"  local_ahead: {upstream_sync.get('local_ahead')}",
            f"  local_contains_upstream: {_format_bool(upstream_sync.get('local_contains_upstream') is True)}",
        ])
    else:
        lines.append("  n/a")
    lines.extend([
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
        "Acceptance thresholds",
    ])
    thresholds = summary.get("acceptance_thresholds") or {}
    pipeline_thresholds = thresholds.get("core_pipeline_flow") or {}
    repeat_thresholds = thresholds.get("core_pipeline_repeatability") or {}
    required_stages = pipeline_thresholds.get("required_stages") or []
    if required_stages:
        lines.append(f"  required_stages: {' -> '.join(required_stages)}")
    if repeat_thresholds:
        lines.append(
            "  repeatability: min_runs={} max_goal_error_m={} min_scan_cloud_samples={} "
            "min_global_path_points={} min_cmd_samples={}".format(
                repeat_thresholds.get("min_runs_completed"),
                repeat_thresholds.get("max_goal_error_m"),
                repeat_thresholds.get("min_scan_cloud_samples"),
                repeat_thresholds.get("min_global_path_points"),
                repeat_thresholds.get("min_cmd_samples"),
            )
        )
    evaluation = summary.get("acceptance_evaluation") or {}
    repeat_eval = evaluation.get("core_pipeline_repeatability") or {}
    margins = repeat_eval.get("margins") or {}
    if margins:
        lines.append(
            "  repeatability_margins: runs={} goal_error_m={} scan_cloud={} "
            "global_path={} cmd={}".format(
                _format_margin(margins.get("runs_completed")),
                _format_margin(margins.get("goal_error_m")),
                _format_margin(margins.get("scan_cloud_samples")),
                _format_margin(margins.get("global_path_points")),
                _format_margin(margins.get("cmd_samples")),
            )
        )
    if not required_stages and not repeat_thresholds:
        lines.append("  n/a")
    lines.extend([
        "",
        "Main sync",
    ])
    main_sync = summary.get("main_sync") or {}
    if main_sync and main_sync.get("available") is True:
        lines.extend([
            f"  base: {main_sync.get('base')}",
            f"  head: {main_sync.get('head')}",
            f"  main_ahead: {main_sync.get('main_ahead')}",
            f"  v6_ahead: {main_sync.get('v6_ahead')}",
            f"  main_contains_v6: {_format_bool(main_sync.get('main_contains_v6') is True)}",
        ])
    else:
        lines.append("  n/a")
    lines.extend([
        "",
        "Release steps",
    ])
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
        "Release evidence",
    ])
    release_evidence = summary.get("release_evidence") or {}
    if release_evidence:
        for name, path in sorted(release_evidence.items()):
            lines.append(f"  {name}: {path}")
    else:
        lines.append("  n/a")
    lines.extend([
        "",
        "Evidence",
    ])
    for name, path in summary["evidence"].items():
        lines.append(f"  {name}: {path}")
    lines.extend([
        "",
        "Evidence age",
    ])
    for name, age in (summary.get("evidence_age") or {}).items():
        lines.append(f"  {name}: {_format_age(age)} mtime_utc={age.get('mtime_utc') if age else None}")
    if summary["blockers"]:
        lines.append("")
        lines.append("Blockers")
        lines.extend(f"  - {blocker}" for blocker in summary["blockers"])
    if not (git.get("evidence_fresh_for_head")):
        lines.append("")
        lines.append("Freshness")
        lines.append(f"  reason: {git.get('freshness_reason')}")
        if git.get("relevant_worktree_changes"):
            lines.append(
                "  relevant_worktree_changes: {}".format(
                    ", ".join(git.get("relevant_worktree_changes") or [])
                )
            )
        if git.get("relevant_changes_since_evidence"):
            lines.append(
                "  relevant_changes_since_evidence: {}".format(
                    ", ".join(git.get("relevant_changes_since_evidence") or [])
                )
            )
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
