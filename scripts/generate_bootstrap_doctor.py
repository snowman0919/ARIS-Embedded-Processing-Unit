#!/usr/bin/env python3
"""Validate ARIS bootstrap assumptions for a new headless development environment."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
from typing import Any


REQUIRED_FILES = (
    "flake.nix",
    "justfile",
    ".env.example",
    "docker/compose.yaml",
    "docker/ros2.Dockerfile",
    "docker/embedded.Dockerfile",
    "scripts/check_host.sh",
    "scripts/check_bootstrap_doctor.sh",
    "scripts/docker_build.sh",
    "scripts/check_branch_policy.sh",
    "scripts/check_headless_release_candidate.sh",
    "scripts/check_embedded_dry_run.sh",
    "scripts/check_documented_commands.sh",
    "scripts/check_architecture_contracts.sh",
    "scripts/check_host_policy.sh",
    "scripts/check_core_readiness.sh",
    "scripts/check_python_tests.sh",
    "scripts/check_mcu_serial_loopback.sh",
    "scripts/check_scan_cloud_contract.sh",
    "scripts/check_operator_goal.sh",
    "scripts/check_v3_semantic_map.sh",
    "scripts/check_v6_semantic_review.sh",
    "scripts/check_v4_goal_nav.sh",
    "scripts/check_v5_dynamic_obstacle.sh",
    "scripts/check_v2_gazebo_stack.sh",
    "scripts/check_v2_gazebo_lidar.sh",
    "scripts/check_v2_gazebo_localization.sh",
    "scripts/check_v2_gazebo_moving_localization.sh",
    "scripts/check_v2_gazebo_physics.sh",
    "scripts/check_v2_gazebo_physics_localization.sh",
    "scripts/check_v2_gazebo_drift_recovery.sh",
    "scripts/check_core_pipeline_flow.sh",
    "scripts/check_core_pipeline_repeatability.sh",
    "scripts/run_core_readiness_report.sh",
    "scripts/check_headless_readiness_audit.sh",
)
REQUIRED_EXECUTABLES = tuple(path for path in REQUIRED_FILES if path.startswith("scripts/"))
REQUIRED_COMMANDS = ("git", "python3", "nix", "docker")
OPTIONAL_COMMANDS = ("just", "jq", "rg")
REQUIRED_ENV = (
    "ARIS_HOME",
    "ARIS_WS",
    "ARIS_DATA",
    "ARIS_LOGS",
    "ARIS_MODELS",
    "ROS_DOMAIN_ID",
    "ROS_LOCALHOST_ONLY",
    "RMW_IMPLEMENTATION",
    "ARIS_ENABLE_REAL_ACTUATION",
)


def generate_report(workspace: Path, env: dict[str, str] | None = None) -> dict[str, Any]:
    env = env or dict(os.environ)
    workspace = workspace.resolve()
    checks: dict[str, Any] = {}
    blockers: list[str] = []

    file_checks = {path: (workspace / path).exists() for path in REQUIRED_FILES}
    checks["required_files"] = file_checks
    blockers.extend(f"missing required file: {path}" for path, ok in file_checks.items() if not ok)

    executable_checks = {path: os.access(workspace / path, os.X_OK) for path in REQUIRED_EXECUTABLES}
    checks["required_executables"] = executable_checks
    blockers.extend(f"required script is not executable: {path}" for path, ok in executable_checks.items() if not ok)

    command_checks = {name: shutil.which(name) is not None for name in REQUIRED_COMMANDS}
    optional_command_checks = {name: shutil.which(name) is not None for name in OPTIONAL_COMMANDS}
    checks["required_commands"] = command_checks
    checks["optional_commands"] = optional_command_checks
    blockers.extend(f"missing required command: {name}" for name, ok in command_checks.items() if not ok)

    env_checks = {name: bool(env.get(name)) for name in REQUIRED_ENV}
    checks["required_env"] = env_checks
    blockers.extend(f"missing required environment variable: {name}" for name, ok in env_checks.items() if not ok)

    path_env = {
        name: env.get(name)
        for name in ("ARIS_WS", "ARIS_HOME", "ARIS_DATA", "ARIS_LOGS", "ARIS_MODELS")
    }
    checks["path_env"] = path_env
    if env.get("ARIS_WS") and Path(env["ARIS_WS"]).resolve() != workspace:
        blockers.append(f"ARIS_WS does not match workspace: {env['ARIS_WS']} != {workspace}")

    dir_checks = {}
    for name in ("ARIS_DATA", "ARIS_LOGS", "ARIS_MODELS"):
        value = env.get(name)
        dir_checks[name] = bool(value and Path(value).exists() and Path(value).is_dir())
    checks["required_dirs"] = dir_checks
    blockers.extend(f"required directory is missing: {name}={env.get(name)}" for name, ok in dir_checks.items() if not ok)

    safety_checks = {
        "not_root": os.geteuid() != 0,
        "real_actuation_disabled": env.get("ARIS_ENABLE_REAL_ACTUATION", "0") != "1",
        "ros_localhost_only": env.get("ROS_LOCALHOST_ONLY") == "1",
        "env_file_not_tracked": not (workspace / ".env").exists(),
    }
    checks["safety"] = safety_checks
    if not safety_checks["not_root"]:
        blockers.append("bootstrap doctor must not be run as root")
    if not safety_checks["real_actuation_disabled"]:
        blockers.append("ARIS_ENABLE_REAL_ACTUATION must remain disabled for headless bootstrap")
    if not safety_checks["ros_localhost_only"]:
        blockers.append("ROS_LOCALHOST_ONLY must be 1 for default headless bootstrap")
    if not safety_checks["env_file_not_tracked"]:
        blockers.append(".env exists; keep local secrets/config untracked and review before sharing logs")

    env_example = workspace / ".env.example"
    env_example_text = env_example.read_text(encoding="utf-8") if env_example.exists() else ""
    checks["env_example"] = {
        "has_ngc_placeholder": "<choose-current-arm64-dgx-spark-compatible-tag>" in env_example_text,
        "real_actuation_default_disabled": "ARIS_ENABLE_REAL_ACTUATION=0" in env_example_text,
    }
    if not checks["env_example"]["real_actuation_default_disabled"]:
        blockers.append(".env.example must default ARIS_ENABLE_REAL_ACTUATION=0")

    return {
        "artifact_type": "aris_bootstrap_doctor_report",
        "schema_version": 1,
        "workspace": str(workspace),
        "valid": not blockers,
        "checks": checks,
        "blockers": blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    report = generate_report(args.workspace)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "bootstrap_doctor_valid valid={} blockers={}".format(
            report["valid"],
            len(report["blockers"]),
        )
    )
    if report["blockers"]:
        for blocker in report["blockers"]:
            print(blocker)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
