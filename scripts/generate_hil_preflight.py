#!/usr/bin/env python3
"""Generate a hardware-in-the-loop preflight report without enabling actuators."""

from __future__ import annotations

import argparse
import grp
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
from typing import Any


REQUIRED_GROUPS = ("docker",)
HARDWARE_GROUPS = ("dialout", "tty", "video", "render", "input")


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


def _groups_for_user(user: str) -> list[str]:
    groups = []
    for group in grp.getgrall():
        if user in group.gr_mem:
            groups.append(group.gr_name)
    primary_gid = pwd.getpwnam(user).pw_gid
    primary = grp.getgrgid(primary_gid).gr_name
    if primary not in groups:
        groups.append(primary)
    return sorted(groups)


def _glob_paths(patterns: list[str]) -> list[str]:
    paths: list[str] = []
    for pattern in patterns:
        paths.extend(str(path) for path in sorted(Path("/").glob(pattern.lstrip("/"))))
    return paths


def generate_preflight(workspace: Path, logs_dir: Path, user: str | None = None) -> dict[str, Any]:
    user = user or pwd.getpwuid(os.getuid()).pw_name
    groups = _groups_for_user(user)
    latest_readiness = _latest(list((logs_dir / "readiness").glob("evidence_index_*.json")))
    readiness = _read_json(latest_readiness)
    latest_v5 = _latest(list((logs_dir / "obstacles").glob("v5_dynamic_obstacle_*.json")))
    latest_v6 = _latest(list((logs_dir / "maps").glob("v3_semantic_map_*.v6_review.json")))

    devices = {
        "serial": _glob_paths(["/dev/serial/by-id/*", "/dev/ttyACM*", "/dev/ttyUSB*"]),
        "video": _glob_paths(["/dev/video*", "/dev/media*"]),
        "gpu": _glob_paths(["/dev/dri/renderD*", "/dev/nvidia*"]),
        "can": _glob_paths(["/dev/can*", "/sys/class/net/can*"]),
        "input": _glob_paths(["/dev/input/js*", "/dev/input/by-id/*"]),
    }
    command_presence = {
        "docker": shutil.which("docker") is not None,
        "git": shutil.which("git") is not None,
        "python3": shutil.which("python3") is not None,
    }
    docker_access = _docker_access()
    env = {
        "ARIS_ENABLE_REAL_ACTUATION": os.environ.get("ARIS_ENABLE_REAL_ACTUATION", "0"),
        "ROS_DOMAIN_ID": os.environ.get("ROS_DOMAIN_ID"),
        "ROS_LOCALHOST_ONLY": os.environ.get("ROS_LOCALHOST_ONLY"),
    }

    checks = {
        "real_actuation_disabled": env["ARIS_ENABLE_REAL_ACTUATION"] != "1",
        "required_commands_present": all(command_presence.values()),
        "docker_access": docker_access,
        "required_groups_present": all(group in groups for group in REQUIRED_GROUPS),
        "hardware_groups_present": {
            group: group in groups
            for group in HARDWARE_GROUPS
        },
        "latest_readiness_passed": bool(
            readiness
            and readiness.get("readiness", {}).get("result") == "PASS"
            and readiness.get("readiness", {}).get("skip_gazebo") == "0"
            and readiness.get("readiness", {}).get("skip_v3") == "0"
        ),
        "latest_v5_report_present": latest_v5 is not None,
        "latest_v6_review_present": latest_v6 is not None,
        "hardware_devices_present": {
            "serial": bool(devices["serial"]),
            "video": bool(devices["video"]),
            "gpu": bool(devices["gpu"]),
            "can": bool(devices["can"]),
            "input": bool(devices["input"]),
        },
    }

    blockers = []
    if not checks["real_actuation_disabled"]:
        blockers.append("ARIS_ENABLE_REAL_ACTUATION must remain 0 during preflight")
    if not checks["required_commands_present"]:
        blockers.append("required host commands are missing")
    if not checks["docker_access"]:
        blockers.append("docker access is unavailable")
    if not checks["required_groups_present"]:
        blockers.append("required user groups are missing")
    if not checks["latest_readiness_passed"]:
        blockers.append("latest no-skip readiness evidence is missing or not PASS")

    hardware_missing = [
        name for name, present in checks["hardware_devices_present"].items() if not present
    ]
    if hardware_missing:
        blockers.append("hardware devices missing: " + ",".join(hardware_missing))

    return {
        "artifact_type": "aris_hil_preflight_report",
        "schema_version": 1,
        "workspace": str(workspace),
        "logs_dir": str(logs_dir),
        "user": user,
        "ready_for_hil": not blockers,
        "safe_to_enable_real_actuation": False,
        "blockers": blockers,
        "checks": checks,
        "commands": command_presence,
        "devices": devices,
        "environment": env,
        "evidence": {
            "latest_readiness_index": str(latest_readiness) if latest_readiness else None,
            "latest_v5_obstacle_report": str(latest_v5) if latest_v5 else None,
            "latest_v6_semantic_review": str(latest_v6) if latest_v6 else None,
        },
    }


def _docker_access() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        result = subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5.0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--logs-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--user")
    args = parser.parse_args()

    report = generate_preflight(args.workspace, args.logs_dir, args.user)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "hil_preflight path={} ready_for_hil={} blockers={}".format(
            args.out,
            report["ready_for_hil"],
            len(report["blockers"]),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
