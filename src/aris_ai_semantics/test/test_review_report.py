from aris_ai_semantics.review_report import (
    ReviewInputs,
    generate_review_report,
    validate_review_report,
)


def test_v6_review_report_is_advisory_only():
    report = generate_review_report(
        ReviewInputs(
            manifest={
                "map_id": "aris-v3-sim",
                "snapshot_path": "/aris/logs/maps/map.json",
                "snapshot_sha256": "abc",
                "high_risk_cells": 1,
                "review_queue": 4,
                "labels": {"debris": 1},
            },
            compare={
                "candidate_map_id": "aris-v3-sim",
                "label_changes": 1,
                "metric_overlap_ratio": 0.94,
                "route_overlap_ratio": 1.0,
            },
        )
    )

    assert report["artifact_type"] == "aris_v6_semantic_review_report"
    assert report["advisory_only"] is True
    assert report["control_authority"] == "none"
    assert report["summary"]["review_item_count"] >= 1
    assert validate_review_report(report) == []
    assert all(
        item["annotation"]["control_authority"] == "none"
        for item in report["review_items"]
    )


def test_v6_review_report_requires_review_items():
    report = generate_review_report(
        ReviewInputs(
            manifest={
                "map_id": "aris-v3-sim",
                "high_risk_cells": 0,
                "review_queue": 0,
            }
        )
    )

    failures = validate_review_report(report)

    assert "review report must contain at least one operator review item" in failures
