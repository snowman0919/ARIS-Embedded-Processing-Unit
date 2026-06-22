#!/usr/bin/env python3
"""Validate ARIS local and remote-tracking branch policy."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


ALLOWED_BRANCHES = (
    "main",
    "v1-teach-repeat-route-replay",
    "v2-lidar-localization-gazebo",
    "v3-semantic-hd-map",
    "v4-goal-based-navigation",
    "v5-dynamic-obstacle-advisory",
    "v6-headless-simulation-embedded",
)


def validate_refs(
    *,
    current_branch: str | None,
    local_branches: list[str],
    remote_branches: list[str],
) -> list[str]:
    allowed = set(ALLOWED_BRANCHES)
    blockers: list[str] = []

    if current_branch not in allowed:
        blockers.append(f"current branch is not an ARIS vN-context branch: {current_branch or '<detached>'}")

    unexpected_local = sorted(branch for branch in local_branches if branch not in allowed)
    unexpected_remote = sorted(branch for branch in remote_branches if branch not in allowed)

    for branch in unexpected_local:
        blockers.append(f"unexpected local branch: {branch}")
    for branch in unexpected_remote:
        blockers.append(f"unexpected origin branch: {branch}")

    return blockers


def generate_report(workspace: Path) -> dict[str, Any]:
    current_branch = _current_branch(workspace)
    local_branches, remote_branches = _branch_refs(workspace)
    main_sync = _main_sync(workspace)
    blockers = validate_refs(
        current_branch=current_branch,
        local_branches=local_branches,
        remote_branches=remote_branches,
    )
    return {
        "artifact_type": "aris_branch_policy_report",
        "schema_version": 1,
        "workspace": str(workspace),
        "valid": not blockers,
        "allowed_branches": list(ALLOWED_BRANCHES),
        "current_branch": current_branch,
        "local_branches": local_branches,
        "origin_branches": remote_branches,
        "main_sync": main_sync,
        "blockers": blockers,
    }


def _current_branch(workspace: Path) -> str | None:
    result = subprocess.run(
        ["git", "symbolic-ref", "--quiet", "--short", "HEAD"],
        cwd=workspace,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _branch_refs(workspace: Path) -> tuple[list[str], list[str]]:
    local = _git_refs(workspace, "refs/heads")
    remote = []
    for ref in _git_refs(workspace, "refs/remotes/origin"):
        if ref == "HEAD":
            continue
        remote.append(ref)
    return sorted(local), sorted(remote)


def _git_refs(workspace: Path, prefix: str) -> list[str]:
    result = subprocess.run(
        ["git", "for-each-ref", "--format=%(refname)", prefix],
        cwd=workspace,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    names: list[str] = []
    full_prefix = f"{prefix}/"
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith(full_prefix):
            names.append(line.removeprefix(full_prefix))
    return names


def _main_sync(workspace: Path) -> dict[str, Any]:
    base = "refs/remotes/origin/main"
    head = "refs/remotes/origin/v6-headless-simulation-embedded"
    if not _ref_exists(workspace, base) or not _ref_exists(workspace, head):
        return {
            "base": "origin/main",
            "head": "origin/v6-headless-simulation-embedded",
            "available": False,
            "main_ahead": None,
            "v6_ahead": None,
            "main_contains_v6": False,
        }
    result = subprocess.run(
        ["git", "rev-list", "--left-right", "--count", "origin/main...origin/v6-headless-simulation-embedded"],
        cwd=workspace,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    main_ahead_text, v6_ahead_text = result.stdout.split()
    main_ahead = int(main_ahead_text)
    v6_ahead = int(v6_ahead_text)
    return {
        "base": "origin/main",
        "head": "origin/v6-headless-simulation-embedded",
        "available": True,
        "main_ahead": main_ahead,
        "v6_ahead": v6_ahead,
        "main_contains_v6": v6_ahead == 0,
    }


def _ref_exists(workspace: Path, ref: str) -> bool:
    result = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", ref],
        cwd=workspace,
        check=False,
    )
    return result.returncode == 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    report = generate_report(args.workspace)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if report["valid"]:
        main_sync = report["main_sync"]
        print(
            "branch_policy_valid current={} local={} origin={} main_ahead={} v6_ahead={}".format(
                report["current_branch"],
                len(report["local_branches"]),
                len(report["origin_branches"]),
                main_sync["main_ahead"],
                main_sync["v6_ahead"],
            )
        )
        return 0

    for blocker in report["blockers"]:
        print(blocker)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
