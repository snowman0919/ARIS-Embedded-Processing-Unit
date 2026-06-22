import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from generate_hil_preflight import generate_preflight


def test_hil_preflight_reports_safe_default_and_evidence(tmp_path, monkeypatch):
    monkeypatch.setenv("ARIS_ENABLE_REAL_ACTUATION", "0")
    logs = tmp_path / "logs"
    readiness = logs / "readiness"
    obstacles = logs / "obstacles"
    maps = logs / "maps"
    readiness.mkdir(parents=True)
    obstacles.mkdir()
    maps.mkdir()

    (readiness / "evidence_index_20260101T000000Z.json").write_text(
        json.dumps(
            {
                "readiness": {
                    "result": "PASS",
                    "skip_gazebo": "0",
                    "skip_v3": "0",
                }
            }
        ),
        encoding="utf-8",
    )
    (obstacles / "v5_dynamic_obstacle_20260101T000000Z.json").write_text(
        json.dumps({"artifact_type": "aris_v5_dynamic_obstacle_report", "valid": True}),
        encoding="utf-8",
    )
    (maps / "v3_semantic_map_20260101.v6_review.json").write_text(
        json.dumps({"artifact_type": "aris_v6_semantic_review_report"}),
        encoding="utf-8",
    )

    report = generate_preflight(tmp_path / "workspace", logs)

    assert report["artifact_type"] == "aris_hil_preflight_report"
    assert report["safe_to_enable_real_actuation"] is False
    assert report["checks"]["real_actuation_disabled"] is True
    assert report["checks"]["latest_readiness_passed"] is True
    assert report["evidence"]["latest_v5_obstacle_report"].endswith(".json")
