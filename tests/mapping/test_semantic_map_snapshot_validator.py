import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from validate_semantic_map_snapshot import validate_snapshot


def _snapshot(metric_cells=2, semantic=True, route_nodes=2, route_edges=1, review_queue=1):
    cells = [
        {
            "cell": [0, 0],
            "occupancy": 0.75,
            "labels": {"road": 0.9} if semantic else {},
            "traversability": 0.1,
            "observations": 1,
        },
        {
            "cell": [1, 0],
            "occupancy": 0.75,
            "labels": {"debris": 0.85} if semantic else {},
            "traversability": 0.925,
            "observations": 1,
        },
    ]
    return {
        "schema_version": 1,
        "map_id": "unit-test-map",
        "resolution_m": 0.5,
        "change_threshold": 0.65,
        "confirmation_threshold": 0.75,
        "metric_cells": [[idx, 0] for idx in range(metric_cells)],
        "cells": cells,
        "route_nodes": [{"node_id": f"n{idx}", "x": float(idx), "y": 0.0} for idx in range(route_nodes)],
        "route_edges": [
            {"from_node": f"n{idx}", "to_node": f"n{idx + 1}", "cost": 1.0, "blocked": False}
            for idx in range(route_edges)
        ],
        "review_queue": [
            {
                "cell": [1, 0],
                "label": "debris",
                "applied": True,
                "change_detected": True,
                "review_required": True,
                "reason": "change_detected",
            }
            for _ in range(review_queue)
        ],
    }


def test_semantic_map_snapshot_manifest_accepts_complete_snapshot(tmp_path):
    snapshot_path = tmp_path / "map.json"
    snapshot_path.write_text(json.dumps(_snapshot()), encoding="utf-8")

    manifest = validate_snapshot(
        snapshot_path,
        min_metric_cells=2,
        min_semantic_cells=1,
        min_route_nodes=2,
        min_route_edges=1,
        min_review_queue=1,
        min_high_risk_cells=1,
        high_risk_threshold=0.8,
    )

    assert manifest["valid"]
    assert manifest["snapshot_sha256"]
    assert manifest["labels"] == {"debris": 1, "road": 1}


def test_semantic_map_snapshot_manifest_rejects_missing_route_graph(tmp_path):
    snapshot_path = tmp_path / "map.json"
    snapshot_path.write_text(json.dumps(_snapshot(route_nodes=0, route_edges=0)), encoding="utf-8")

    with pytest.raises(ValueError, match="route_nodes=0"):
        validate_snapshot(
            snapshot_path,
            min_metric_cells=2,
            min_semantic_cells=1,
            min_route_nodes=2,
            min_route_edges=1,
            min_review_queue=1,
            min_high_risk_cells=1,
            high_risk_threshold=0.8,
        )
