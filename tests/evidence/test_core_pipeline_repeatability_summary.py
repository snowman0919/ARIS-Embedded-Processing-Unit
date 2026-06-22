import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from summarize_core_pipeline_repeatability import route_signature_stable, summarize_reports


def _flow_report(path: Path, node_path: list[str], *, goal_error: float = 0.7) -> Path:
    report = {
        "valid": True,
        "stages": {
            "mapping": {"passed": True},
            "semantic_hd_map": {"passed": True},
            "route_graph": {"passed": True, "node_path": node_path},
            "localization": {"passed": True, "scan_cloud_samples": 180},
            "goal_based_planning": {"passed": True, "global_path_points": 30},
            "autonomous_driving": {
                "passed": True,
                "cmd_samples": 180,
                "goal_error_m": goal_error,
                "max_x_m": 9.0,
            },
        },
    }
    path.write_text(json.dumps(report), encoding="utf-8")
    return path


def test_route_signature_accepts_stable_suffix_after_vehicle_progress():
    signatures = [
        ("detour_a", "detour_b", "detour_c", "goal"),
        ("detour_b", "detour_c", "goal"),
    ]

    assert route_signature_stable(signatures, expected_runs=2) is True


def test_route_signature_rejects_different_final_detour():
    signatures = [
        ("detour_a", "detour_b", "detour_c", "goal"),
        ("detour_x", "detour_c", "goal"),
    ]

    assert route_signature_stable(signatures, expected_runs=2) is False


def test_repeatability_summary_accepts_suffix_compatible_routes(tmp_path):
    paths = [
        _flow_report(tmp_path / "run1.json", ["approach", "detour_a", "detour_b", "detour_c", "goal"], goal_error=0.72),
        _flow_report(tmp_path / "run2.json", ["detour_b", "detour_c", "goal"], goal_error=0.71),
    ]

    report = summarize_reports(paths, expected_runs=2, workspace="/ws", logs_dir="/logs")

    assert report["valid"] is True
    assert report["failures"] == []
    assert report["summary"]["node_path_stable"] is True
    assert report["summary"]["route_signature"] == ["detour_b", "detour_c", "goal"]
