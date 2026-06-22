from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field


class MapUpdateEvent(BaseModel):
    event_id: str
    layer: str
    location: tuple[float, float]
    description: str
    confidence: float = Field(ge=0.0, le=1.0)


class SemanticAnnotation(BaseModel):
    event_id: str
    advisory_only: bool = True
    labels: list[str]
    risk_hint: str
    review_required: bool
    control_authority: str = "none"


def annotate_event(event: MapUpdateEvent) -> SemanticAnnotation:
    text = event.description.lower()
    labels: list[str] = []
    risk = "low"
    if "blocked" in text or "debris" in text or "fallen" in text:
        labels.append("possible_obstruction")
        risk = "high"
    if "mud" in text or "water" in text or "soft" in text:
        labels.append("traversability_change")
        risk = "medium" if risk == "low" else risk
    if "person" in text or "vehicle" in text:
        labels.append("dynamic_agent_review")
        risk = "high"
    if not labels:
        labels.append("map_change")

    return SemanticAnnotation(
        event_id=event.event_id,
        labels=labels,
        risk_hint=risk,
        review_required=event.confidence < 0.9 or risk != "low",
    )


def annotate_json(payload: dict[str, Any]) -> dict[str, Any]:
    event = MapUpdateEvent.model_validate(payload)
    return annotate_event(event).model_dump()


def main() -> None:
    event = MapUpdateEvent(
        event_id="mock-001",
        layer="traversability",
        location=(37.0, 127.0),
        description="mud and debris detected near route edge",
        confidence=0.82,
    )
    print(json.dumps(annotate_event(event).model_dump(), indent=2, sort_keys=True))
