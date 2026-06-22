"""Generate advisory-only V6 review reports from semantic-map artifacts."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .annotator import MapUpdateEvent, annotate_event


@dataclass(frozen=True)
class ReviewInputs:
    manifest: dict[str, Any]
    compare: dict[str, Any] | None = None


def load_review_inputs(manifest_path: Path, compare_path: Path | None = None) -> ReviewInputs:
    manifest = _read_json_object(manifest_path)
    compare = _read_json_object(compare_path) if compare_path else None
    return ReviewInputs(manifest=manifest, compare=compare)


def generate_review_report(inputs: ReviewInputs) -> dict[str, Any]:
    manifest = inputs.manifest
    compare = inputs.compare or {}
    events = _events_from_manifest(manifest) + _events_from_compare(compare)
    annotations = [annotate_event(event).model_dump() for event in events]
    review_items = [
        {
            "event": event.model_dump(),
            "annotation": annotation,
        }
        for event, annotation in zip(events, annotations)
        if annotation["review_required"]
    ]
    return {
        "artifact_type": "aris_v6_semantic_review_report",
        "schema_version": 1,
        "advisory_only": True,
        "control_authority": "none",
        "source": {
            "map_id": manifest.get("map_id"),
            "snapshot_path": manifest.get("snapshot_path"),
            "snapshot_sha256": manifest.get("snapshot_sha256"),
        },
        "summary": {
            "event_count": len(events),
            "review_item_count": len(review_items),
            "high_risk_cells": int(manifest.get("high_risk_cells", 0)),
            "review_queue": int(manifest.get("review_queue", 0)),
            "label_changes": int(compare.get("label_changes", 0)),
            "route_overlap_ratio": float(compare.get("route_overlap_ratio", 1.0)),
            "metric_overlap_ratio": float(compare.get("metric_overlap_ratio", 1.0)),
        },
        "review_items": review_items,
    }


def write_review_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate_review_report(report: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if report.get("artifact_type") != "aris_v6_semantic_review_report":
        failures.append("artifact_type must be aris_v6_semantic_review_report")
    if report.get("advisory_only") is not True:
        failures.append("review report must be advisory_only")
    if report.get("control_authority") != "none":
        failures.append("review report must have no control authority")
    summary = report.get("summary", {})
    if int(summary.get("review_item_count", 0)) < 1:
        failures.append("review report must contain at least one operator review item")
    for index, item in enumerate(report.get("review_items", [])):
        annotation = item.get("annotation", {})
        if annotation.get("control_authority") != "none":
            failures.append(f"review item {index} grants control authority")
        if annotation.get("advisory_only") is not True:
            failures.append(f"review item {index} is not advisory_only")
    return failures


def _events_from_manifest(manifest: dict[str, Any]) -> list[MapUpdateEvent]:
    events: list[MapUpdateEvent] = []
    if int(manifest.get("high_risk_cells", 0)) > 0:
        events.append(
            MapUpdateEvent(
                event_id=f"{manifest.get('map_id', 'map')}:high-risk",
                layer="traversability",
                location=(0.0, 0.0),
                description=(
                    f"{manifest.get('high_risk_cells')} high-risk traversability cells "
                    f"and labels {json.dumps(manifest.get('labels', {}), sort_keys=True)}"
                ),
                confidence=0.82,
            )
        )
    if int(manifest.get("review_queue", 0)) > 0:
        events.append(
            MapUpdateEvent(
                event_id=f"{manifest.get('map_id', 'map')}:review-queue",
                layer="semantic",
                location=(0.0, 0.0),
                description=f"{manifest.get('review_queue')} map changes require operator review",
                confidence=0.86,
            )
        )
    return events


def _events_from_compare(compare: dict[str, Any]) -> list[MapUpdateEvent]:
    if not compare:
        return []
    events: list[MapUpdateEvent] = []
    if int(compare.get("label_changes", 0)) > 0:
        events.append(
            MapUpdateEvent(
                event_id=f"{compare.get('candidate_map_id', 'map')}:label-change",
                layer="semantic",
                location=(0.0, 0.0),
                description=f"{compare.get('label_changes')} semantic label changes detected",
                confidence=0.78,
            )
        )
    if float(compare.get("metric_overlap_ratio", 1.0)) < 0.95:
        events.append(
            MapUpdateEvent(
                event_id=f"{compare.get('candidate_map_id', 'map')}:metric-overlap",
                layer="metric",
                location=(0.0, 0.0),
                description=(
                    "metric map repeat-pass overlap dropped to "
                    f"{float(compare.get('metric_overlap_ratio', 0.0)):.3f}"
                ),
                confidence=0.88,
            )
        )
    return events


def _read_json_object(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON artifact must be an object: {path}")
    return data
