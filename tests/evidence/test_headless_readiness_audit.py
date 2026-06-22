import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from generate_headless_readiness_audit import generate_audit


def _write_index(logs: Path, *, embedded: bool = True) -> None:
    readiness = logs / "readiness"
    readiness.mkdir(parents=True)
    index = {
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
        "v3_semantic_map": {
            "manifest": {"valid": True},
            "manifest_path": str(logs / "maps" / "v3.manifest.json"),
            "compare": {"valid": True},
            "compare_path": str(logs / "maps" / "v3.compare.json"),
        },
        "v5_dynamic_obstacle": {
            "report": {"valid": True, "metrics": {"track_age": 2, "detour_min_steering": -0.2}},
            "report_path": str(logs / "obstacles" / "v5.json"),
        },
        "v5_obstacle_bag_replay": {
            "report": {
                "valid": True,
                "bag_path": "/bags/obstacle",
                "metrics": {"advisory_samples": 4, "action_counts": {"detour": 4}},
            },
            "report_path": str(logs / "obstacles" / "v5_replay.json"),
        },
        "v6_semantic_review": {
            "report": {"advisory_only": True, "control_authority": "none"},
            "report_path": str(logs / "maps" / "v6.json"),
        },
        "core_pipeline_flow": {
            "report": {
                "valid": True,
                "semantic_map_snapshot": str(logs / "maps" / "pipeline.json"),
                "stages": {
                    "mapping": {"passed": True},
                    "semantic_hd_map": {"passed": True},
                    "route_graph": {"passed": True},
                    "localization": {"passed": True},
                    "goal_based_planning": {"passed": True},
                    "autonomous_driving": {"passed": True},
                },
            },
            "report_path": str(logs / "pipeline" / "core_pipeline_flow.json"),
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
                "runs": [
                    {
                        "scan_cloud_samples": 12,
                        "global_path_points": 6,
                        "cmd_samples": 24,
                    },
                    {
                        "scan_cloud_samples": 11,
                        "global_path_points": 6,
                        "cmd_samples": 23,
                    },
                ],
            },
            "report_path": str(logs / "pipeline" / "core_pipeline_repeatability.json"),
        },
        "hil_preflight": {
            "report": None,
            "report_path": None,
        },
        "field_validation": {
            "report": None,
            "report_path": None,
        },
    }
    if embedded:
        index["embedded_dry_run"] = {
            "report": {
                "artifact_type": "aris_embedded_dry_run_report",
                "valid": True,
                "exit_code": 0,
                "hardware_required": False,
                "checks": ["cargo test", "cargo fmt --check"],
            },
            "report_path": str(logs / "embedded" / "embedded_dry_run.json"),
        }
    (readiness / "evidence_index_20260101T000000Z.json").write_text(json.dumps(index), encoding="utf-8")


def test_headless_audit_passes_without_hil_or_field(tmp_path):
    logs = tmp_path / "logs"
    _write_index(logs)

    report = generate_audit(tmp_path / "workspace", logs)

    assert report["artifact_type"] == "aris_headless_readiness_audit"
    assert report["scope"] == "headless_simulation_embedded"
    assert report["headless_ready"] is True
    assert report["achieved"] is True
    assert report["hardware_scope_active"] is False
    assert report["safe_to_enable_real_actuation"] is False
    assert report["blockers"] == []
    assert report["acceptance_thresholds"]["core_pipeline_flow"]["required_stages"] == [
        "mapping",
        "semantic_hd_map",
        "route_graph",
        "localization",
        "goal_based_planning",
        "autonomous_driving",
    ]
    assert report["acceptance_thresholds"]["core_pipeline_repeatability"] == {
        "min_runs_completed": 2,
        "node_path_stable": True,
        "max_goal_error_m": 1.3,
        "min_runs_with_samples": 2,
        "min_scan_cloud_samples": 5,
        "min_global_path_points": 2,
        "min_cmd_samples": 20,
    }
    assert report["criteria"]["embedded_dry_run"]["passed"] is True
    assert report["future_blockers_not_in_scope"] == ["hil_preflight", "field_validation"]


def test_headless_audit_requires_embedded_dry_run(tmp_path):
    logs = tmp_path / "logs"
    _write_index(logs, embedded=False)

    report = generate_audit(tmp_path / "workspace", logs)

    assert report["headless_ready"] is False
    assert report["criteria"]["embedded_dry_run"]["passed"] is False
    assert any("embedded_dry_run" in blocker for blocker in report["blockers"])


def test_headless_audit_requires_core_pipeline_flow(tmp_path):
    logs = tmp_path / "logs"
    _write_index(logs)
    index_path = logs / "readiness" / "evidence_index_20260101T000000Z.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["core_pipeline_flow"] = {"report": None, "report_path": None}
    index_path.write_text(json.dumps(index), encoding="utf-8")

    report = generate_audit(tmp_path / "workspace", logs)

    assert report["headless_ready"] is False
    assert report["criteria"]["core_pipeline_flow"]["passed"] is False
    assert any("core_pipeline_flow" in blocker for blocker in report["blockers"])


def test_headless_audit_requires_core_pipeline_repeatability(tmp_path):
    logs = tmp_path / "logs"
    _write_index(logs)
    index_path = logs / "readiness" / "evidence_index_20260101T000000Z.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["core_pipeline_repeatability"] = {"report": None, "report_path": None}
    index_path.write_text(json.dumps(index), encoding="utf-8")

    report = generate_audit(tmp_path / "workspace", logs)

    assert report["headless_ready"] is False
    assert report["criteria"]["core_pipeline_repeatability"]["passed"] is False
    assert any("core_pipeline_repeatability" in blocker for blocker in report["blockers"])


def test_headless_audit_requires_sampled_repeatability_runs(tmp_path):
    logs = tmp_path / "logs"
    _write_index(logs)
    index_path = logs / "readiness" / "evidence_index_20260101T000000Z.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["core_pipeline_repeatability"]["report"]["runs"][0]["cmd_samples"] = 3
    index_path.write_text(json.dumps(index), encoding="utf-8")

    report = generate_audit(tmp_path / "workspace", logs)

    assert report["headless_ready"] is False
    criterion = report["criteria"]["core_pipeline_repeatability"]
    assert criterion["passed"] is False
    assert criterion["evidence"]["cmd_samples_min"] == 3
    assert any("core_pipeline_repeatability" in blocker for blocker in report["blockers"])


def test_headless_audit_falls_back_to_latest_embedded_report(tmp_path):
    logs = tmp_path / "logs"
    _write_index(logs, embedded=False)
    embedded = logs / "embedded"
    embedded.mkdir()
    (embedded / "embedded_dry_run_20260101T000001Z.json").write_text(
        json.dumps({"valid": True, "exit_code": 0, "hardware_required": False}),
        encoding="utf-8",
    )

    report = generate_audit(tmp_path / "workspace", logs)

    assert report["headless_ready"] is True
    assert report["criteria"]["embedded_dry_run"]["evidence"]["report_path"].endswith(".json")
