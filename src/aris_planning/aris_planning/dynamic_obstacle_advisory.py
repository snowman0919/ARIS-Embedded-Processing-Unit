"""Apply V5 dynamic-obstacle advisories to local planner commands."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math

from .pure_pursuit import LocalPlanCommand, Pose2D


@dataclass(frozen=True)
class DynamicObstacleAdvisory:
    action: str
    closest_distance_m: float | None = None
    closing_speed_mps: float = 0.0
    point_count: int = 0
    reason: str = ""
    detour_lateral_m: float = 0.0
    detour_forward_m: float = 2.0


def parse_dynamic_obstacle_advisory(payload: str) -> DynamicObstacleAdvisory:
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError("dynamic-obstacle advisory must be a JSON object")
    action = str(data.get("action", "clear"))
    if action not in {"clear", "slow", "stop", "detour"}:
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
        detour_lateral_m=float(data.get("detour_lateral_m", 0.0)),
        detour_forward_m=float(data.get("detour_forward_m", 2.0)),
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
    if advisory.action == "detour":
        return LocalPlanCommand(
            target_steering_rad=command.target_steering_rad,
            target_velocity_mps=min(command.target_velocity_mps, max(0.0, slow_speed_mps)),
            brake=max(command.brake, 0.1),
            dry_run=command.dry_run,
        )
    return LocalPlanCommand(
        target_steering_rad=command.target_steering_rad,
        target_velocity_mps=min(command.target_velocity_mps, max(0.0, slow_speed_mps)),
        brake=max(command.brake, 0.2),
        dry_run=command.dry_run,
    )


def path_with_dynamic_detour(
    pose: Pose2D,
    path: list[tuple[float, float]],
    advisory: DynamicObstacleAdvisory | None,
    *,
    default_lateral_m: float = 1.0,
    merge_forward_m: float = 4.0,
) -> list[tuple[float, float]]:
    if advisory is None or advisory.action != "detour" or not path:
        return path
    lateral_m = advisory.detour_lateral_m
    if abs(lateral_m) < 1e-3:
        lateral_m = default_lateral_m
    forward_m = max(advisory.detour_forward_m, 0.5)
    detour_point = _local_to_map(pose, forward_m, lateral_m)
    merge_point = _first_forward_path_point(pose, path, min_forward_m=merge_forward_m)
    if merge_point is None:
        merge_point = path[-1]
    return [detour_point, merge_point, *path]


def _first_forward_path_point(
    pose: Pose2D, path: list[tuple[float, float]], *, min_forward_m: float
) -> tuple[float, float] | None:
    for point in path:
        dx = point[0] - pose.x
        dy = point[1] - pose.y
        local_x = math.cos(-pose.yaw) * dx - math.sin(-pose.yaw) * dy
        if local_x >= min_forward_m:
            return point
    return None


def _local_to_map(pose: Pose2D, x: float, y: float) -> tuple[float, float]:
    return (
        pose.x + math.cos(pose.yaw) * x - math.sin(pose.yaw) * y,
        pose.y + math.sin(pose.yaw) * x + math.cos(pose.yaw) * y,
    )
