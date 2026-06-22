import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from validate_headless_release_candidate import REQUIRED_STEPS, validate


def _write_report(tmp_path: Path, *, omit_step: str | None = None) -> tuple[Path, Path]:
    logs = tmp_path / "logs"
    readiness = logs / "readiness"
    embedded = logs / "embedded"
    pipeline = logs / "pipeline"
    readiness.mkdir(parents=True)
    embedded.mkdir()
    pipeline.mkdir()

    evidence_paths = {
        "bootstrap_doctor": readiness / "bootstrap.json",
        "embedded_dry_run": embedded / "embedded.json",
        "core_pipeline_flow": pipeline / "pipeline.json",
        "core_pipeline_repeatability": pipeline / "repeatability.json",
        "core_readiness_report": readiness / "core.log",
        "headless_readiness_audit": readiness / "audit.json",
        "readiness_evidence_index": readiness / "index.json",
    }
    for path in evidence_paths.values():
        path.write_text("{}\n", encoding="utf-8")

    report_path = readiness / "release.json"
    steps = [
        {"name": name, "passed": True, "exit_code": 0, "started_utc": "t0", "ended_utc": "t1"}
        for name in REQUIRED_STEPS
        if name != omit_step
    ]
    report = {
        "artifact_type": "aris_headless_release_candidate_report",
        "valid": True,
        "exit_code": 0,
        "hardware_scope_active": False,
        "steps": steps,
        "evidence": {key: str(path) for key, path in evidence_paths.items()},
    }
    report_path.write_text(json.dumps(report), encoding="utf-8")

    index = {
        "headless_release_candidate": {
            "report_path": str(report_path),
            "report": report,
        }
    }
    evidence_paths["readiness_evidence_index"].write_text(json.dumps(index), encoding="utf-8")
    return report_path, evidence_paths["readiness_evidence_index"]


def test_headless_release_candidate_validator_accepts_closed_report(tmp_path):
    report_path, index_path = _write_report(tmp_path)

    assert validate(report_path, index_path) == []


def test_headless_release_candidate_validator_rejects_missing_required_step(tmp_path):
    report_path, index_path = _write_report(tmp_path, omit_step="host_policy")

    failures = validate(report_path, index_path)

    assert "missing required step: host_policy" in failures


def test_headless_release_candidate_validator_requires_final_index_backlink(tmp_path):
    report_path, index_path = _write_report(tmp_path)
    index_path.write_text(json.dumps({"headless_release_candidate": {}}), encoding="utf-8")

    failures = validate(report_path, index_path)

    assert "final index must include headless_release_candidate.report_path" in failures
