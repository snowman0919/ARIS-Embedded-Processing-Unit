"""ROS-free operator command parsing for ARIS HMI/API adapters."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OperatorGoal:
    x: float
    y: float
    frame_id: str = "map"
    source: str = "operator"


def parse_goal_request(payload: str) -> OperatorGoal:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid goal JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ValueError("goal request must be a JSON object")
    return goal_from_mapping(data)


def goal_from_mapping(data: dict[str, Any]) -> OperatorGoal:
    try:
        x = float(data["x"])
        y = float(data["y"])
    except KeyError as exc:
        raise ValueError(f"missing goal field: {exc.args[0]}") from exc
    except (TypeError, ValueError) as exc:
        raise ValueError("goal x/y must be numeric") from exc

    frame_id = str(data.get("frame_id", "map")).strip() or "map"
    source = str(data.get("source", "operator")).strip() or "operator"
    if frame_id != "map":
        raise ValueError("only map-frame goals are accepted")
    return OperatorGoal(x=x, y=y, frame_id=frame_id, source=source)


def goal_event(goal: OperatorGoal) -> str:
    return json.dumps(
        {
            "event": "goal_accepted",
            "x": goal.x,
            "y": goal.y,
            "frame_id": goal.frame_id,
            "source": goal.source,
        },
        sort_keys=True,
    )
