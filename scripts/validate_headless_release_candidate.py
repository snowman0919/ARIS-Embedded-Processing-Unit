#!/usr/bin/env python3
"""Validate the final headless release-candidate report closure."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_STEPS = (
    "bootstrap_doctor",
    "embedded_dry_run",
    "documented_commands",
    "architecture_contracts",
    "host_policy",
    "core_pipeline_flow",
    "core_pipeline_repeatability",
    "core_readiness_report",
    "headless_readiness_audit",
)


def validate(report_path: Path, index_path: Path | None = None) -> list[str]:
    report = _read_json(report_path)
    failures: list[str] = []

    if report.get("artifact_type") != "aris_headless_release_candidate_report":
        failures.append("report artifact_type must be aris_headless_release_candidate_report")
    if report.get("valid") is not True:
        failures.append("report valid must be true")
    if report.get("exit_code") != 0:
        failures.append("report exit_code must be 0")
    if report.get("hardware_scope_active") is not False:
        failures.append("hardware_scope_active must be false")

    steps = report.get("steps")
    if not isinstance(steps, list):
        failures.append("steps must be a list")
        steps_by_name: dict[str, dict[str, Any]] = {}
    else:
        steps_by_name = {
            str(step.get("name")): step
            for step in steps
            if isinstance(step, dict) and step.get("name") is not None
        }

    for required in REQUIRED_STEPS:
        step = steps_by_name.get(required)
        if step is None:
            failures.append(f"missing required step: {required}")
            continue
        if step.get("passed") is not True or step.get("exit_code") != 0:
            failures.append(f"required step did not pass: {required}")

    evidence = report.get("evidence")
    if not isinstance(evidence, dict):
        failures.append("evidence must be an object")
        evidence = {}

    required_evidence = (
        "bootstrap_doctor",
        "embedded_dry_run",
        "core_pipeline_flow",
        "core_pipeline_repeatability",
        "core_readiness_report",
        "headless_readiness_audit",
        "readiness_evidence_index",
    )
    for key in required_evidence:
        value = evidence.get(key)
        if not value:
            failures.append(f"missing evidence path: {key}")
            continue
        if not Path(str(value)).exists():
            failures.append(f"evidence path does not exist: {key}={value}")

    report_index = evidence.get("readiness_evidence_index")
    if index_path is not None and report_index:
        if Path(str(report_index)).resolve() != index_path.resolve():
            failures.append("report readiness_evidence_index must point to the final index")

    if index_path is not None:
        index = _read_json(index_path)
        rc = index.get("headless_release_candidate") if isinstance(index, dict) else None
        indexed_report_path = (rc or {}).get("report_path") if isinstance(rc, dict) else None
        if not indexed_report_path:
            failures.append("final index must include headless_release_candidate.report_path")
        elif Path(str(indexed_report_path)).resolve() != report_path.resolve():
            failures.append("final index headless_release_candidate.report_path must point back to report")

    return failures


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON artifact must be an object: {path}")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--index", type=Path)
    args = parser.parse_args(argv)

    failures = validate(args.report, args.index)
    if failures:
        for failure in failures:
            print(failure)
        return 1
    print("headless_release_candidate_valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
