"""Apply V5 dynamic-obstacle advisories to local planner commands."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math

from .pure_pursuit import LocalPlanCommand


@dataclass(frozen=True)
class DynamicObstacleAdvisory:
    action: str
    closest_distance_m: float | None = None
    closing_speed_mps: float = 0.0
    point_count: int = 0
    reason: str = ""


def parse_dynamic_obstacle_advisory(payload: str) -> DynamicObstacleAdvisory:
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError("dynamic-obstacle advisory must be a JSON object")
    action = str(data.get("action", "clear"))
    if action not in {"clear", "slow", "stop"}:
        raise ValueError(f"unknown dynamic-obstacle action: {action}")
    closest = data.get("closest_distance_m")
    closest_distance_m = float(closest) if closest is not None else None
    if closest_distance_m is not None and not math.isfinite(closest_distance_m):
        closest_distance_m = None
    return DynamicObstacleAdvisory(
        action=action,
        closest_distance_m=closest_distance_m,
        closing_speed_mps=float(data.get("closing_speed_mps", 0.0)),
        point_count=int(data.get("point_count", 0)),
        reason=str(data.get("reason", "")),
    )


def apply_dynamic_obstacle_advisory(
    command: LocalPlanCommand,
    advisory: DynamicObstacleAdvisory | None,
    *,
    slow_speed_mps: float = 0.4,
) -> LocalPlanCommand:
    if advisory is None or advisory.action == "clear":
        return command
    if advisory.action == "stop":
        return LocalPlanCommand(
            target_steering_rad=command.target_steering_rad,
            target_velocity_mps=0.0,
            brake=1.0,
            dry_run=command.dry_run,
        )
    return LocalPlanCommand(
        target_steering_rad=command.target_steering_rad,
        target_velocity_mps=min(command.target_velocity_mps, max(0.0, slow_speed_mps)),
        brake=max(command.brake, 0.2),
        dry_run=command.dry_run,
    )
