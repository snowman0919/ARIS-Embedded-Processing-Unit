import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from compare_semantic_map_snapshots import compare_snapshots


def _snapshot(metric_count=4, label="road", review_count=1):
    cells = [
        {
            "cell": [idx, 0],
            "occupancy": 0.75,
            "labels": {label: 0.9},
            "traversability": 0.1 if label == "road" else 0.925,
            "observations": 1,
        }
        for idx in range(metric_count)
    ]
    return {
        "schema_version": 1,
        "map_id": "repeat-pass-test",
        "resolution_m": 0.5,
        "change_threshold": 0.65,
        "confirmation_threshold": 0.75,
        "metric_cells": [[idx, 0] for idx in range(metric_count)],
        "cells": cells,
        "route_nodes": [{"node_id": f"n{idx}", "x": float(idx), "y": 0.0} for idx in range(3)],
        "route_edges": [
            {"from_node": "n0", "to_node": "n1", "cost": 1.0, "blocked": False},
            {"from_node": "n1", "to_node": "n2", "cost": 1.0, "blocked": False},
        ],
        "review_queue": [
            {
                "cell": [0, 0],
                "label": label,
                "applied": True,
                "change_detected": label != "road",
                "review_required": True,
                "reason": "change_detected",
            }
            for _ in range(review_count)
        ],
    }


def _write(tmp_path, name, snapshot):
    path = tmp_path / name
    path.write_text(json.dumps(snapshot), encoding="utf-8")
    return path


def test_repeat_pass_compare_accepts_stable_snapshots(tmp_path):
    baseline = _write(tmp_path, "baseline.json", _snapshot())
    candidate = _write(tmp_path, "candidate.json", _snapshot())

    report = compare_snapshots(
        baseline,
        candidate,
        min_metric_overlap=1.0,
        min_route_overlap=1.0,
        max_label_changes=0,
        max_high_risk_delta=0,
        max_review_queue_delta=0,
        high_risk_threshold=0.8,
    )

    assert report["valid"]
    assert report["metric_overlap_ratio"] == 1.0
    assert report["route_overlap_ratio"] == 1.0


def test_repeat_pass_compare_rejects_low_metric_overlap(tmp_path):
    baseline = _write(tmp_path, "baseline.json", _snapshot(metric_count=4))
    candidate = _write(tmp_path, "candidate.json", _snapshot(metric_count=1))

    with pytest.raises(ValueError, match="metric_overlap_ratio"):
        compare_snapshots(
            baseline,
            candidate,
            min_metric_overlap=0.75,
            min_route_overlap=1.0,
            max_label_changes=0,
            max_high_risk_delta=0,
            max_review_queue_delta=0,
            high_risk_threshold=0.8,
        )
