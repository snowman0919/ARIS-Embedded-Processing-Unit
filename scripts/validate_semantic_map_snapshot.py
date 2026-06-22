#!/usr/bin/env python3
"""Validate an ARIS semantic map snapshot and emit a promotion manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


def _load_snapshot(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"snapshot does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"snapshot is not valid JSON: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("snapshot root must be a JSON object")
    return data


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _label_counts(cells: list[dict[str, Any]]) -> dict[str, int]:
    labels: dict[str, int] = {}
    for cell in cells:
        for label in cell.get("labels", {}):
            labels[str(label)] = labels.get(str(label), 0) + 1
    return dict(sorted(labels.items()))


def _semantic_cells(cells: list[dict[str, Any]]) -> int:
    return sum(1 for cell in cells if cell.get("labels"))


def _high_risk_cells(cells: list[dict[str, Any]], threshold: float) -> int:
    return sum(1 for cell in cells if float(cell.get("traversability", 0.0)) >= threshold)


def validate_snapshot(
    snapshot_path: Path,
    *,
    min_metric_cells: int,
    min_semantic_cells: int,
    min_route_nodes: int,
    min_route_edges: int,
    min_review_queue: int,
    min_high_risk_cells: int,
    high_risk_threshold: float,
) -> dict[str, Any]:
    snapshot = _load_snapshot(snapshot_path)
    cells = snapshot.get("cells", [])
    metric_cells = snapshot.get("metric_cells", [])
    route_nodes = snapshot.get("route_nodes", [])
    route_edges = snapshot.get("route_edges", [])
    review_queue = snapshot.get("review_queue", [])
    failures: list[str] = []

    if snapshot.get("schema_version") != 1:
        failures.append(f"schema_version={snapshot.get('schema_version')!r}, expected 1")
    if not snapshot.get("map_id"):
        failures.append("map_id is empty")
    for field, value in (
        ("cells", cells),
        ("metric_cells", metric_cells),
        ("route_nodes", route_nodes),
        ("route_edges", route_edges),
        ("review_queue", review_queue),
    ):
        if not isinstance(value, list):
            failures.append(f"{field} must be a list")

    cells = cells if isinstance(cells, list) else []
    metric_cells = metric_cells if isinstance(metric_cells, list) else []
    route_nodes = route_nodes if isinstance(route_nodes, list) else []
    route_edges = route_edges if isinstance(route_edges, list) else []
    review_queue = review_queue if isinstance(review_queue, list) else []
    semantic_cells = _semantic_cells(cells)
    label_counts = _label_counts(cells)
    high_risk_cells = _high_risk_cells(cells, high_risk_threshold)

    if len(metric_cells) < min_metric_cells:
        failures.append(f"metric_cells={len(metric_cells)}, expected >= {min_metric_cells}")
    if semantic_cells < min_semantic_cells:
        failures.append(f"semantic_cells={semantic_cells}, expected >= {min_semantic_cells}")
    if len(route_nodes) < min_route_nodes:
        failures.append(f"route_nodes={len(route_nodes)}, expected >= {min_route_nodes}")
    if len(route_edges) < min_route_edges:
        failures.append(f"route_edges={len(route_edges)}, expected >= {min_route_edges}")
    if len(review_queue) < min_review_queue:
        failures.append(f"review_queue={len(review_queue)}, expected >= {min_review_queue}")
    if high_risk_cells < min_high_risk_cells:
        failures.append(f"high_risk_cells={high_risk_cells}, expected >= {min_high_risk_cells}")
    if not label_counts:
        failures.append("no semantic labels in snapshot")

    manifest = {
        "artifact_type": "aris_semantic_map_snapshot_manifest",
        "snapshot_path": str(snapshot_path),
        "snapshot_sha256": _sha256(snapshot_path),
        "schema_version": snapshot.get("schema_version"),
        "map_id": snapshot.get("map_id"),
        "resolution_m": snapshot.get("resolution_m"),
        "metric_cells": len(metric_cells),
        "cells": len(cells),
        "semantic_cells": semantic_cells,
        "high_risk_cells": high_risk_cells,
        "route_nodes": len(route_nodes),
        "route_edges": len(route_edges),
        "review_queue": len(review_queue),
        "labels": label_counts,
        "valid": not failures,
        "failures": failures,
    }
    if failures:
        raise ValueError("; ".join(failures))
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--manifest-out", type=Path)
    parser.add_argument("--min-metric-cells", type=int, default=20)
    parser.add_argument("--min-semantic-cells", type=int, default=1)
    parser.add_argument("--min-route-nodes", type=int, default=2)
    parser.add_argument("--min-route-edges", type=int, default=1)
    parser.add_argument("--min-review-queue", type=int, default=1)
    parser.add_argument("--min-high-risk-cells", type=int, default=1)
    parser.add_argument("--high-risk-threshold", type=float, default=0.8)
    args = parser.parse_args(argv)

    try:
        manifest = validate_snapshot(
            args.snapshot,
            min_metric_cells=args.min_metric_cells,
            min_semantic_cells=args.min_semantic_cells,
            min_route_nodes=args.min_route_nodes,
            min_route_edges=args.min_route_edges,
            min_review_queue=args.min_review_queue,
            min_high_risk_cells=args.min_high_risk_cells,
            high_risk_threshold=args.high_risk_threshold,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if args.manifest_out:
        args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
        args.manifest_out.write_text(text, encoding="utf-8")
    print(
        "semantic_map_snapshot_valid path={} sha256={} metric_cells={} semantic_cells={} "
        "route_nodes={} route_edges={} review_queue={} high_risk_cells={}".format(
            args.snapshot,
            manifest["snapshot_sha256"],
            manifest["metric_cells"],
            manifest["semantic_cells"],
            manifest["route_nodes"],
            manifest["route_edges"],
            manifest["review_queue"],
            manifest["high_risk_cells"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
