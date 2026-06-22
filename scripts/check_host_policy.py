#!/usr/bin/env python3
"""Validate host-side no-sudo/no-apt policy for repository entrypoints."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys


SCAN_FILES = ("justfile",)
SCAN_GLOBS = ("scripts/*.sh",)
FORBIDDEN_COMMANDS = (
    "sudo",
    "apt",
    "apt-get",
    "systemctl",
    "udevadm",
    "usermod",
    "groupadd",
    "modprobe",
)
COMMAND_PREFIX_RE = r"(?:^|[;&|]\s*|\bthen\s+|\bdo\s+)"
ALLOWED_EXCEPTIONS = {
    ("scripts/can_create_vcan0.sh", "apt-get"),
    ("scripts/can_create_vcan0.sh", "modprobe"),
}


@dataclass(frozen=True)
class Failure:
    path: Path
    line_no: int
    token: str

    def format(self) -> str:
        return f"{self.path}:{self.line_no}: host policy forbids '{self.token}'"


def validate(workspace: Path) -> list[Failure]:
    failures: list[Failure] = []
    for path in _scan_paths(workspace):
        relative = path.relative_to(workspace).as_posix()
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            for command in FORBIDDEN_COMMANDS:
                pattern = COMMAND_PREFIX_RE + re.escape(command) + r"(?:\s|$)"
                match = re.search(pattern, stripped)
                if not match:
                    continue
                if (relative, command) in ALLOWED_EXCEPTIONS:
                    continue
                failures.append(Failure(Path(relative), line_no, command))
    return failures


def _scan_paths(workspace: Path) -> list[Path]:
    paths = {workspace / file_name for file_name in SCAN_FILES}
    for pattern in SCAN_GLOBS:
        paths.update(path for path in workspace.glob(pattern) if path.is_file())
    return sorted(path for path in paths if path.exists())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)

    workspace = args.workspace.resolve()
    failures = validate(workspace)
    if failures:
        for failure in failures:
            print(failure.format(), file=sys.stderr)
        return 1
    print("host_policy_valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
