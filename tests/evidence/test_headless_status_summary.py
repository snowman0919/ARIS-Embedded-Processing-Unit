import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from summarize_headless_status import format_text, summarize


def test_headless_status_summary_collects_latest_evidence(tmp_path):
    logs = tmp_path / "logs"
    readiness = logs / "readiness"
    pipeline = logs / "pipeline"
    readiness.mkdir(parents=True)
    pipeline.mkdir()

    release = {
        "artifact_type": "aris_headless_release_candidate_report",
        "valid": True,
        "steps": [
            {"name": "embedded_dry_run", "passed": True, "exit_code": 0},
            {"name": "core_pipeline_repeatability", "passed": True, "exit_code": 0},
        ],
    }
    audit = {
        "artifact_type": "aris_headless_readiness_audit",
        "headless_ready": True,
        "hardware_scope_active": False,
        "safe_to_enable_real_actuation": False,
        "blockers": [],
        "criteria": {
            "core_pipeline_repeatability": {
                "passed": True,
                "blockers": [],
            }
        },
    }
    index = {
        "git": {"branch": "v6", "commit": "abc1234"},
        "core_pipeline_flow": {
            "report": {
                "valid": True,
                "semantic_map_snapshot": "/aris/logs/maps/map.json",
                "stages": {
                    "route_graph": {"passed": True, "node_path": ["approach", "goal"]},
                    "autonomous_driving": {"passed": True, "goal_error_m": 0.4},
                },
            }
        }
    }
    repeat = {
        "artifact_type": "aris_core_pipeline_repeatability_report",
        "valid": True,
        "summary": {
            "runs_completed": 2,
            "node_path_stable": True,
            "goal_error_max_m": 0.5,
            "goal_error_spread_m": 0.1,
            "scan_cloud_samples_min": 12,
            "global_path_points_min": 6,
            "cmd_samples_min": 24,
        },
    }
    (readiness / "latest_headless_release_candidate.json").write_text(json.dumps(release), encoding="utf-8")
    (readiness / "latest_headless_readiness_audit.json").write_text(json.dumps(audit), encoding="utf-8")
    (readiness / "latest_evidence_index.json").write_text(json.dumps(index), encoding="utf-8")
    (pipeline / "latest_core_pipeline_repeatability.json").write_text(json.dumps(repeat), encoding="utf-8")

    summary = summarize(logs)
    text = format_text(summary)

    assert summary["headless_ready"] is True
    assert summary["release_valid"] is True
    assert summary["git"]["evidence_fresh_for_head"] is False
    assert summary["safe_to_enable_real_actuation"] is False
    assert summary["core_pipeline"]["node_path"] == ["approach", "goal"]
    assert summary["repeatability"]["runs_completed"] == 2
    assert summary["repeatability"]["scan_cloud_samples_min"] == 12
    assert summary["repeatability"]["global_path_points_min"] == 6
    assert summary["repeatability"]["cmd_samples_min"] == 24
    assert "headless_ready: yes" in text
    assert "evidence_fresh_for_head: no" in text
    assert "run: just headless-release-candidate" in text
    assert "node_path: approach -> goal" in text
    assert "scan_cloud_samples_min: 12" in text
    assert "global_path_points_min: 6" in text
    assert "cmd_samples_min: 24" in text


def test_headless_status_summary_marks_fresh_evidence_for_matching_head(tmp_path, monkeypatch):
    logs = tmp_path / "logs"
    readiness = logs / "readiness"
    pipeline = logs / "pipeline"
    readiness.mkdir(parents=True)
    pipeline.mkdir()
    (readiness / "latest_headless_release_candidate.json").write_text(
        json.dumps({"valid": True, "steps": [{"name": "ok", "passed": True, "exit_code": 0}]}),
        encoding="utf-8",
    )
    (readiness / "latest_headless_readiness_audit.json").write_text(
        json.dumps({"headless_ready": True, "blockers": []}),
        encoding="utf-8",
    )
    (readiness / "latest_evidence_index.json").write_text(
        json.dumps({"git": {"branch": "v6", "commit": "abc1234"}}),
        encoding="utf-8",
    )
    (pipeline / "latest_core_pipeline_repeatability.json").write_text(
        json.dumps({"valid": True, "summary": {}}),
        encoding="utf-8",
    )

    def fake_git(workspace, *args):
        if args == ("branch", "--show-current"):
            return "v6"
        if args == ("rev-parse", "--short", "HEAD"):
            return "abc1234"
        raise AssertionError(args)

    monkeypatch.setattr("summarize_headless_status._git", fake_git)

    summary = summarize(logs, tmp_path / "workspace")

    assert summary["git"]["evidence_fresh_for_head"] is True


def test_headless_status_summary_accepts_autorun_log_only_changes(tmp_path, monkeypatch):
    logs = tmp_path / "logs"
    readiness = logs / "readiness"
    pipeline = logs / "pipeline"
    readiness.mkdir(parents=True)
    pipeline.mkdir()
    (readiness / "latest_headless_release_candidate.json").write_text(
        json.dumps({"valid": True, "steps": [{"name": "ok", "passed": True, "exit_code": 0}]}),
        encoding="utf-8",
    )
    (readiness / "latest_headless_readiness_audit.json").write_text(
        json.dumps({"headless_ready": True, "blockers": []}),
        encoding="utf-8",
    )
    (readiness / "latest_evidence_index.json").write_text(
        json.dumps({"git": {"branch": "v6", "commit": "abc1234"}}),
        encoding="utf-8",
    )
    (pipeline / "latest_core_pipeline_repeatability.json").write_text(
        json.dumps({"valid": True, "summary": {}}),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "summarize_headless_status._current_git",
        lambda workspace: {"branch": "v6", "commit": "def5678"},
    )
    monkeypatch.setattr(
        "summarize_headless_status._changed_since",
        lambda workspace, evidence_commit: [
            "docs/AUTORUN_LOG.md",
            "scripts/summarize_headless_status.py",
            "tests/evidence/test_headless_status_summary.py",
        ],
    )

    summary = summarize(logs, tmp_path / "workspace")

    assert summary["git"]["evidence_fresh_for_head"] is True
    assert summary["git"]["relevant_changes_since_evidence"] == []


def test_headless_status_summary_rejects_runtime_relevant_changes(tmp_path, monkeypatch):
    logs = tmp_path / "logs"
    readiness = logs / "readiness"
    pipeline = logs / "pipeline"
    readiness.mkdir(parents=True)
    pipeline.mkdir()
    (readiness / "latest_headless_release_candidate.json").write_text(
        json.dumps({"valid": True, "steps": [{"name": "ok", "passed": True, "exit_code": 0}]}),
        encoding="utf-8",
    )
    (readiness / "latest_headless_readiness_audit.json").write_text(
        json.dumps({"headless_ready": True, "blockers": []}),
        encoding="utf-8",
    )
    (readiness / "latest_evidence_index.json").write_text(
        json.dumps({"git": {"branch": "v6", "commit": "abc1234"}}),
        encoding="utf-8",
    )
    (pipeline / "latest_core_pipeline_repeatability.json").write_text(
        json.dumps({"valid": True, "summary": {}}),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "summarize_headless_status._current_git",
        lambda workspace: {"branch": "v6", "commit": "def5678"},
    )
    monkeypatch.setattr(
        "summarize_headless_status._changed_since",
        lambda workspace, evidence_commit: ["scripts/check_core_pipeline_flow.sh"],
    )

    summary = summarize(logs, tmp_path / "workspace")

    assert summary["git"]["evidence_fresh_for_head"] is False
    assert summary["git"]["relevant_changes_since_evidence"] == ["scripts/check_core_pipeline_flow.sh"]


def test_headless_status_summary_reports_missing_evidence_as_not_ready(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()

    summary = summarize(logs)

    assert summary["headless_ready"] is False
    assert summary["release_valid"] is False
    assert summary["evidence"]["headless_release_candidate"] is None
