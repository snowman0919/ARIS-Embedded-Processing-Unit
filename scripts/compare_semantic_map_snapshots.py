#!/usr/bin/env python3
"""Compare two ARIS semantic map snapshots for repeat-pass stability."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


Cell = tuple[int, int]


def _load(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"snapshot does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"snapshot is not valid JSON: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"snapshot root must be an object: {path}")
    if data.get("schema_version") != 1:
        raise ValueError(f"unsupported schema_version in {path}: {data.get('schema_version')!r}")
    return data


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _cell(value: object) -> Cell:
    if not isinstance(value, list | tuple) or len(value) != 2:
        raise ValueError(f"invalid cell: {value!r}")
    return (int(value[0]), int(value[1]))


def _cells(snapshot: dict[str, Any]) -> dict[Cell, dict[str, Any]]:
    cells: dict[Cell, dict[str, Any]] = {}
    for item in snapshot.get("cells", []):
        if isinstance(item, dict) and "cell" in item:
            cells[_cell(item["cell"])] = item
    return cells


def _metric_cells(snapshot: dict[str, Any]) -> set[Cell]:
    return {_cell(cell) for cell in snapshot.get("metric_cells", [])}


def _route_edges(snapshot: dict[str, Any]) -> set[tuple[str, str]]:
    edges: set[tuple[str, str]] = set()
    for edge in snapshot.get("route_edges", []):
        if isinstance(edge, dict):
            edges.add((str(edge.get("from_node")), str(edge.get("to_node"))))
    return edges


def _top_label(cell: dict[str, Any] | None) -> str | None:
    if not cell:
        return None
    labels = cell.get("labels", {})
    if not isinstance(labels, dict) or not labels:
        return None
    return max(labels.items(), key=lambda item: float(item[1]))[0]


def _high_risk_cells(cells: dict[Cell, dict[str, Any]], threshold: float) -> set[Cell]:
    return {
        cell
        for cell, data in cells.items()
        if float(data.get("traversability", 0.0)) >= threshold
    }


def _ratio(numerator: int, denominator: int) -> float:
    return 1.0 if denominator == 0 and numerator == 0 else numerator / max(denominator, 1)


def compare_snapshots(
    baseline_path: Path,
    candidate_path: Path,
    *,
    min_metric_overlap: float,
    min_route_overlap: float,
    max_label_changes: int,
    max_high_risk_delta: int,
    max_review_queue_delta: int,
    high_risk_threshold: float,
) -> dict[str, Any]:
    baseline = _load(baseline_path)
    candidate = _load(candidate_path)
    baseline_metric = _metric_cells(baseline)
    candidate_metric = _metric_cells(candidate)
    baseline_cells = _cells(baseline)
    candidate_cells = _cells(candidate)
    baseline_edges = _route_edges(baseline)
    candidate_edges = _route_edges(candidate)
    baseline_high_risk = _high_risk_cells(baseline_cells, high_risk_threshold)
    candidate_high_risk = _high_risk_cells(candidate_cells, high_risk_threshold)

    shared_metric = baseline_metric & candidate_metric
    shared_edges = baseline_edges & candidate_edges
    common_semantic_cells = set(baseline_cells) & set(candidate_cells)
    label_changes = [
        cell
        for cell in sorted(common_semantic_cells)
        if _top_label(baseline_cells.get(cell)) != _top_label(candidate_cells.get(cell))
    ]
    baseline_review = len(baseline.get("review_queue", []))
    candidate_review = len(candidate.get("review_queue", []))

    result = {
        "artifact_type": "aris_semantic_map_repeat_pass_compare",
        "baseline_path": str(baseline_path),
        "candidate_path": str(candidate_path),
        "baseline_sha256": _sha256(baseline_path),
        "candidate_sha256": _sha256(candidate_path),
        "baseline_map_id": baseline.get("map_id"),
        "candidate_map_id": candidate.get("map_id"),
        "metric_overlap_ratio": _ratio(len(shared_metric), len(baseline_metric)),
        "metric_cells_baseline": len(baseline_metric),
        "metric_cells_candidate": len(candidate_metric),
        "metric_cells_shared": len(shared_metric),
        "route_overlap_ratio": _ratio(len(shared_edges), len(baseline_edges)),
        "route_edges_baseline": len(baseline_edges),
        "route_edges_candidate": len(candidate_edges),
        "route_edges_shared": len(shared_edges),
        "semantic_cells_baseline": sum(1 for cell in baseline_cells.values() if cell.get("labels")),
        "semantic_cells_candidate": sum(1 for cell in candidate_cells.values() if cell.get("labels")),
        "label_changes": len(label_changes),
        "label_change_cells": [list(cell) for cell in label_changes[:20]],
        "high_risk_cells_baseline": len(baseline_high_risk),
        "high_risk_cells_candidate": len(candidate_high_risk),
        "high_risk_delta": abs(len(candidate_high_risk) - len(baseline_high_risk)),
        "review_queue_baseline": baseline_review,
        "review_queue_candidate": candidate_review,
        "review_queue_delta": abs(candidate_review - baseline_review),
        "valid": True,
        "failures": [],
    }

    failures: list[str] = []
    if result["metric_overlap_ratio"] < min_metric_overlap:
        failures.append(
            f"metric_overlap_ratio={result['metric_overlap_ratio']:.3f}, expected >= {min_metric_overlap:.3f}"
        )
    if result["route_overlap_ratio"] < min_route_overlap:
        failures.append(
            f"route_overlap_ratio={result['route_overlap_ratio']:.3f}, expected >= {min_route_overlap:.3f}"
        )
    if result["label_changes"] > max_label_changes:
        failures.append(f"label_changes={result['label_changes']}, expected <= {max_label_changes}")
    if result["high_risk_delta"] > max_high_risk_delta:
        failures.append(
            f"high_risk_delta={result['high_risk_delta']}, expected <= {max_high_risk_delta}"
        )
    if result["review_queue_delta"] > max_review_queue_delta:
        failures.append(
            f"review_queue_delta={result['review_queue_delta']}, expected <= {max_review_queue_delta}"
        )
    result["failures"] = failures
    result["valid"] = not failures
    if failures:
        raise ValueError("; ".join(failures))
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--report-out", type=Path)
    parser.add_argument("--min-metric-overlap", type=float, default=0.70)
    parser.add_argument("--min-route-overlap", type=float, default=0.95)
    parser.add_argument("--max-label-changes", type=int, default=2)
    parser.add_argument("--max-high-risk-delta", type=int, default=2)
    parser.add_argument("--max-review-queue-delta", type=int, default=5)
    parser.add_argument("--high-risk-threshold", type=float, default=0.8)
    args = parser.parse_args(argv)

    try:
        report = compare_snapshots(
            args.baseline,
            args.candidate,
            min_metric_overlap=args.min_metric_overlap,
            min_route_overlap=args.min_route_overlap,
            max_label_changes=args.max_label_changes,
            max_high_risk_delta=args.max_high_risk_delta,
            max_review_queue_delta=args.max_review_queue_delta,
            high_risk_threshold=args.high_risk_threshold,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report_out:
        args.report_out.parent.mkdir(parents=True, exist_ok=True)
        args.report_out.write_text(text, encoding="utf-8")
    print(
        "semantic_map_repeat_pass_valid baseline={} candidate={} metric_overlap={:.3f} "
        "route_overlap={:.3f} label_changes={} high_risk_delta={} review_queue_delta={}".format(
            args.baseline,
            args.candidate,
            report["metric_overlap_ratio"],
            report["route_overlap_ratio"],
            report["label_changes"],
            report["high_risk_delta"],
            report["review_queue_delta"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
