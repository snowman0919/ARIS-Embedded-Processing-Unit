#!/usr/bin/env python3
"""Validate static ARIS architecture contract guardrails."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys


CMD_DRIVE_ALLOWED = {
    "src/aris_planning/aris_planning/local_planner_node.py",
    "src/aris_bringup/aris_bringup/teleop_node.py",
}
CMD_DRIVE_TEST_PREFIXES = (
    "scripts/",
    "tests/",
)
AI_FORBIDDEN_PATTERNS = (
    "/cmd_drive",
    "AckermannDriveStamped",
    "CMD_CONTROL",
    "encode_control",
    "ARIS_ENABLE_REAL_ACTUATION",
    "create_publisher",
)
AI_REQUIRED_PATTERNS = (
    '"advisory_only": True',
    '"control_authority": "none"',
)
SOURCE_GLOBS = ("src/**/*.py", "scripts/*.py")


@dataclass(frozen=True)
class Failure:
    path: Path
    line_no: int
    message: str

    def format(self) -> str:
        return f"{self.path}:{self.line_no}: {self.message}"


def _line_matches_any(line: str, patterns: tuple[str, ...]) -> bool:
    return any(pattern in line for pattern in patterns)


def _is_test_or_script(path: str) -> bool:
    return path.startswith(CMD_DRIVE_TEST_PREFIXES)


def validate(workspace: Path) -> list[Failure]:
    failures: list[Failure] = []
    for path in _source_files(workspace):
        relative = path.relative_to(workspace).as_posix()
        lines = path.read_text(encoding="utf-8").splitlines()
        for line_no, line in enumerate(lines, start=1):
            if 'create_publisher(AckermannDriveStamped, "/cmd_drive"' in line:
                if relative not in CMD_DRIVE_ALLOWED and not _is_test_or_script(relative):
                    failures.append(
                        Failure(
                            Path(relative),
                            line_no,
                            "/cmd_drive publisher outside planner/teleop or test/smoke scope",
                        )
                    )
            if relative.startswith("src/aris_ai_semantics/") and _line_matches_any(line, AI_FORBIDDEN_PATTERNS):
                failures.append(
                    Failure(
                        Path(relative),
                        line_no,
                        "AI advisory package must not publish/control vehicle or MCU authority",
                    )
                )

    review_report = workspace / "src/aris_ai_semantics/aris_ai_semantics/review_report.py"
    review_text = review_report.read_text(encoding="utf-8")
    for pattern in AI_REQUIRED_PATTERNS:
        if pattern not in review_text:
            failures.append(
                Failure(
                    review_report.relative_to(workspace),
                    1,
                    f"AI review report missing required advisory marker {pattern}",
                )
            )
    return failures


def _source_files(workspace: Path) -> list[Path]:
    paths: set[Path] = set()
    for pattern in SOURCE_GLOBS:
        paths.update(path for path in workspace.glob(pattern) if path.is_file())
    return sorted(paths)


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
    print("architecture_contracts_valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
