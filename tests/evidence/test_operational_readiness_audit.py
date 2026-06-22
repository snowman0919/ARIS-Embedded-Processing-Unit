import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from generate_operational_readiness_audit import generate_audit


def _write_index(logs: Path, *, ready_for_hil: bool) -> None:
    readiness = logs / "readiness"
    readiness.mkdir(parents=True)
    (readiness / "evidence_index_20260101T000000Z.json").write_text(
        json.dumps(
            {
                "readiness": {
                    "path": str(readiness / "core_readiness_20260101T000000Z.log"),
                    "result": "PASS",
                    "exit_code": "0",
                    "skip_gazebo": "0",
                    "skip_v3": "0",
                    "real_actuation": "0",
                },
                "v2_lidar_bag": {
                    "metadata_path": str(logs / "bags" / "bag1" / "metadata.yaml"),
                    "message_count": 12,
                    "topics": {"/scan_cloud": {"count": 12}},
                },
                "core_pipeline_repeatability": {
                    "report": {
                        "valid": True,
                        "summary": {
                            "runs_completed": 2,
                            "node_path_stable": True,
                            "goal_error_max_m": 0.8,
                            "goal_error_spread_m": 0.1,
                        },
                    },
                    "report_path": str(logs / "pipeline" / "core_pipeline_repeatability.json"),
                },
                "v3_semantic_map": {
                    "manifest": {"valid": True},
                    "manifest_path": str(logs / "maps" / "v3.manifest.json"),
                    "compare": {"valid": True, "metric_overlap_ratio": 1.0},
                    "compare_path": str(logs / "maps" / "v3.compare.json"),
                },
                "v5_dynamic_obstacle": {
                    "report": {
                        "valid": True,
                        "metrics": {
                            "track_age": 2,
                            "detour_min_steering": -0.2,
                        },
                    },
                    "report_path": str(logs / "obstacles" / "v5.json"),
                },
                "v5_obstacle_bag_replay": {
                    "report": None,
                    "report_path": None,
                },
                "v6_semantic_review": {
                    "report": {
                        "advisory_only": True,
                        "control_authority": "none",
                    },
                    "report_path": str(logs / "maps" / "v6.json"),
                },
                "hil_preflight": {
                    "report": {
                        "ready_for_hil": ready_for_hil,
                        "safe_to_enable_real_actuation": False,
                        "blockers": [] if ready_for_hil else ["hardware devices missing: serial,video,can"],
                    },
                    "report_path": str(logs / "hil" / "hil.json"),
                },
            }
        ),
        encoding="utf-8",
    )


def test_operational_audit_keeps_goal_unachieved_without_hil_and_field(tmp_path):
    logs = tmp_path / "logs"
    _write_index(logs, ready_for_hil=False)

    report = generate_audit(tmp_path / "workspace", logs)

    assert report["artifact_type"] == "aris_operational_readiness_audit"
    assert report["criteria"]["core_pipeline_3d_sim"]["passed"] is True
    assert report["criteria"]["core_pipeline_repeatability"]["passed"] is True
    assert report["criteria"]["v3_v6_mapping_review"]["passed"] is True
    assert report["criteria"]["v5_obstacle"]["passed"] is True
    assert report["criteria"]["v5_obstacle_bag_replay"]["passed"] is False
    assert report["criteria"]["hil_preflight"]["passed"] is False
    assert report["criteria"]["field_validation"]["passed"] is False
    assert report["achieved"] is False
    assert any("hil_preflight" in blocker for blocker in report["blockers"])
    assert any("v5_obstacle_bag_replay" in blocker for blocker in report["blockers"])
    assert any("field_validation" in blocker for blocker in report["blockers"])


def test_operational_audit_requires_field_and_real_actuation_safety(tmp_path):
    logs = tmp_path / "logs"
    _write_index(logs, ready_for_hil=True)

    report = generate_audit(tmp_path / "workspace", logs)

    assert report["criteria"]["hil_preflight"]["passed"] is True
    assert report["criteria"]["v5_obstacle_bag_replay"]["passed"] is False
    assert report["criteria"]["field_validation"]["passed"] is False
    assert report["safe_to_enable_real_actuation"] is False
    assert report["achieved"] is False


def test_operational_audit_requires_core_pipeline_repeatability(tmp_path):
    logs = tmp_path / "logs"
    _write_index(logs, ready_for_hil=True)
    index_path = logs / "readiness" / "evidence_index_20260101T000000Z.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["core_pipeline_repeatability"] = {"report": None, "report_path": None}
    index_path.write_text(json.dumps(index), encoding="utf-8")

    report = generate_audit(tmp_path / "workspace", logs)

    assert report["criteria"]["core_pipeline_repeatability"]["passed"] is False
    assert any("core_pipeline_repeatability" in blocker for blocker in report["blockers"])


def test_operational_audit_rejects_malformed_repeatability_goal_error(tmp_path):
    logs = tmp_path / "logs"
    _write_index(logs, ready_for_hil=True)
    index_path = logs / "readiness" / "evidence_index_20260101T000000Z.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["core_pipeline_repeatability"]["report"]["summary"]["goal_error_max_m"] = "not-a-number"
    index_path.write_text(json.dumps(index), encoding="utf-8")

    report = generate_audit(tmp_path / "workspace", logs)

    assert report["criteria"]["core_pipeline_repeatability"]["passed"] is False
    assert any("core_pipeline_repeatability" in blocker for blocker in report["blockers"])


def test_operational_audit_falls_back_to_latest_v5_and_hil_artifacts(tmp_path):
    logs = tmp_path / "logs"
    _write_index(logs, ready_for_hil=False)
    index_path = logs / "readiness" / "evidence_index_20260101T000000Z.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["v5_dynamic_obstacle"] = {"report": None, "report_path": None}
    index["hil_preflight"] = {"report": None, "report_path": None}
    index_path.write_text(json.dumps(index), encoding="utf-8")

    obstacles = logs / "obstacles"
    hil = logs / "hil"
    obstacles.mkdir()
    hil.mkdir()
    (obstacles / "v5_dynamic_obstacle_20260101T000001Z.json").write_text(
        json.dumps({"valid": True, "metrics": {"track_age": 2}}),
        encoding="utf-8",
    )
    (hil / "hil_preflight_20260101T000001Z.json").write_text(
        json.dumps({"ready_for_hil": True, "safe_to_enable_real_actuation": False}),
        encoding="utf-8",
    )

    report = generate_audit(tmp_path / "workspace", logs)

    assert report["criteria"]["v5_obstacle"]["passed"] is True
    assert report["criteria"]["hil_preflight"]["passed"] is True
    assert report["criteria"]["field_validation"]["passed"] is False


def test_operational_audit_accepts_latest_v5_obstacle_replay_report(tmp_path):
    logs = tmp_path / "logs"
    _write_index(logs, ready_for_hil=True)
    obstacles = logs / "obstacles"
    obstacles.mkdir()
    (obstacles / "v5_obstacle_bag_replay_20260101T000001Z.json").write_text(
        json.dumps(
            {
                "valid": True,
                "bag_path": "/bags/operator_obstacle",
                "metrics": {"advisory_samples": 3, "action_counts": {"detour": 3}},
            }
        ),
        encoding="utf-8",
    )

    report = generate_audit(tmp_path / "workspace", logs)

    assert report["criteria"]["v5_obstacle_bag_replay"]["passed"] is True
    assert report["criteria"]["v5_obstacle_bag_replay"]["evidence"]["advisory_samples"] == 3


def test_operational_audit_exposes_field_validation_summary(tmp_path):
    logs = tmp_path / "logs"
    _write_index(logs, ready_for_hil=True)
    field = logs / "field"
    field.mkdir()
    (field / "field_validation_20260101T000001Z.json").write_text(
        json.dumps(
            {
                "valid": True,
                "summary": {
                    "field_run_id": "field-001",
                    "route_completed": True,
                    "goal_error_m": 0.4,
                    "estop_count": 0,
                    "fault_count": 0,
                },
            }
        ),
        encoding="utf-8",
    )

    report = generate_audit(tmp_path / "workspace", logs)

    assert report["criteria"]["field_validation"]["passed"] is True
    assert report["criteria"]["field_validation"]["evidence"]["field_run_id"] == "field-001"
