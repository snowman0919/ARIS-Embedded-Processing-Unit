#!/usr/bin/env python3
"""Validate current documentation command references against justfile and scripts."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys


DOC_GLOBS = ("README.md", "docs/*.md")
SKIPPED_DOCS = {"docs/AUTORUN_LOG.md"}
JUST_RE = re.compile(r"(?<![\w-])just\s+([A-Za-z0-9_-]+)")
SCRIPT_RE = re.compile(r"(?<![\w./-])\./(scripts/[A-Za-z0-9_./-]+)")
RECIPE_RE = re.compile(r"^([A-Za-z0-9_-]+)(?:\s+[^:]*)?:\s*$")


@dataclass(frozen=True)
class Reference:
    kind: str
    name: str
    path: Path
    line_no: int


def load_just_recipes(justfile: Path) -> set[str]:
    recipes: set[str] = set()
    for line in justfile.read_text(encoding="utf-8").splitlines():
        if line.startswith((" ", "\t", "#")):
            continue
        match = RECIPE_RE.match(line)
        if match:
            recipes.add(match.group(1))
    return recipes


def iter_docs(workspace: Path) -> list[Path]:
    docs: list[Path] = []
    for pattern in DOC_GLOBS:
        docs.extend(workspace.glob(pattern))
    return sorted(
        {
            path
            for path in docs
            if path.is_file() and path.relative_to(workspace).as_posix() not in SKIPPED_DOCS
        }
    )


def iter_references(workspace: Path) -> list[Reference]:
    references: list[Reference] = []
    for path in iter_docs(workspace):
        relative = path.relative_to(workspace)
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for match in JUST_RE.finditer(line):
                references.append(Reference("just", match.group(1), relative, line_no))
            for match in SCRIPT_RE.finditer(line):
                script = match.group(1).rstrip("`),.;:")
                references.append(Reference("script", script, relative, line_no))
    return references


def validate(workspace: Path) -> list[str]:
    recipes = load_just_recipes(workspace / "justfile")
    failures: list[str] = []
    for reference in iter_references(workspace):
        if reference.kind == "just":
            if reference.name not in recipes:
                failures.append(
                    f"{reference.path}:{reference.line_no}: unknown just recipe '{reference.name}'"
                )
        elif reference.kind == "script":
            if not (workspace / reference.name).exists():
                failures.append(
                    f"{reference.path}:{reference.line_no}: missing script './{reference.name}'"
                )
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)

    workspace = args.workspace.resolve()
    failures = validate(workspace)
    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1
    print(
        "documented_commands_valid docs={} references={}".format(
            len(iter_docs(workspace)),
            len(iter_references(workspace)),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
