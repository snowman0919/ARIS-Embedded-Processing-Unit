import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from generate_field_validation_report import generate_report


def _manifest(**overrides):
    data = {
        "site_id": "closed-yard-a",
        "operator": "operator-a",
        "route_id": "route-001",
        "field_run_id": "field-001",
        "odd": {
            "closed_site": True,
            "pedestrian_separated": True,
        },
        "metrics": {
            "route_completed": True,
            "goal_error_m": 0.4,
            "max_goal_error_m": 1.0,
            "max_speed_mps": 0.8,
            "speed_limit_mps": 1.0,
            "estop_count": 0,
            "fault_count": 0,
            "operator_takeover_count": 0,
        },
        "evidence": {
            "hil_preflight_report": "/logs/hil/hil_preflight.json",
            "v5_obstacle_bag_replay_report": "/logs/obstacles/v5_replay.json",
            "field_bag": "/logs/bags/field_run",
        },
        "approvals": {
            "operator_reviewed": True,
            "safety_reviewed": True,
        },
    }
    data.update(overrides)
    return data


def _write_latest_supporting_reports(logs: Path) -> None:
    hil = logs / "hil"
    obstacles = logs / "obstacles"
    hil.mkdir(parents=True)
    obstacles.mkdir()
    (hil / "hil_preflight_20260101T000000Z.json").write_text(
        json.dumps({"ready_for_hil": True}),
        encoding="utf-8",
    )
    (obstacles / "v5_obstacle_bag_replay_20260101T000000Z.json").write_text(
        json.dumps({"valid": True}),
        encoding="utf-8",
    )


def test_field_validation_report_accepts_closed_site_manifest(tmp_path):
    logs = tmp_path / "logs"
    _write_latest_supporting_reports(logs)
    manifest = tmp_path / "field_manifest.json"
    manifest.write_text(json.dumps(_manifest()), encoding="utf-8")

    report = generate_report(tmp_path / "workspace", logs, manifest)

    assert report["artifact_type"] == "aris_field_validation_report"
    assert report["valid"] is True
    assert report["summary"]["field_run_id"] == "field-001"
    assert report["summary"]["route_completed"] is True


def test_field_validation_report_rejects_unsafe_or_incomplete_manifest(tmp_path):
    logs = tmp_path / "logs"
    _write_latest_supporting_reports(logs)
    manifest = tmp_path / "field_manifest.json"
    manifest.write_text(
        json.dumps(
            _manifest(
                odd={"closed_site": False, "pedestrian_separated": False},
                metrics={
                    "route_completed": False,
                    "goal_error_m": 2.0,
                    "max_goal_error_m": 1.0,
                    "max_speed_mps": 1.4,
                    "speed_limit_mps": 1.0,
                    "estop_count": 1,
                    "fault_count": 1,
                    "operator_takeover_count": 1,
                },
            )
        ),
        encoding="utf-8",
    )

    report = generate_report(tmp_path / "workspace", logs, manifest)

    assert report["valid"] is False
    assert "field route was not completed" in report["failures"]
    assert "ODD must be closed-site" in report["failures"]
    assert "E-stop occurred during field validation" in report["failures"]


def test_field_validation_report_requires_latest_supporting_evidence(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    manifest = tmp_path / "field_manifest.json"
    manifest.write_text(json.dumps(_manifest()), encoding="utf-8")

    report = generate_report(tmp_path / "workspace", logs, manifest)

    assert report["valid"] is False
    assert "latest HIL preflight evidence is missing" in report["failures"]
    assert "latest V5 obstacle bag replay evidence is missing" in report["failures"]
