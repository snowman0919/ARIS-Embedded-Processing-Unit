"""ROS-free V5 dynamic-obstacle corridor detector."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable


@dataclass(frozen=True)
class PointXYZ:
    x: float
    y: float
    z: float


@dataclass(frozen=True)
class DynamicObstacleDecision:
    action: str
    closest_distance_m: float | None
    closing_speed_mps: float
    point_count: int
    reason: str
    detour_lateral_m: float | None = None
    detour_forward_m: float | None = None

    def as_dict(self) -> dict[str, float | int | str | None]:
        return {
            "action": self.action,
            "closest_distance_m": self.closest_distance_m,
            "closing_speed_mps": self.closing_speed_mps,
            "point_count": self.point_count,
            "reason": self.reason,
            "detour_lateral_m": self.detour_lateral_m,
            "detour_forward_m": self.detour_forward_m,
        }


@dataclass(frozen=True)
class DynamicObstacleConfig:
    corridor_half_width_m: float = 0.8
    min_x_m: float = 0.25
    slow_distance_m: float = 4.0
    stop_distance_m: float = 1.4
    z_min_m: float = -0.6
    z_max_m: float = 1.8
    min_points: int = 3
    closing_stop_mps: float = 1.2
    detour_lateral_m: float = 1.0
    detour_forward_m: float = 2.0


def evaluate_dynamic_obstacle(
    points: Iterable[PointXYZ],
    *,
    config: DynamicObstacleConfig = DynamicObstacleConfig(),
    previous_closest_m: float | None = None,
    dt_s: float | None = None,
) -> DynamicObstacleDecision:
    candidates = [
        point
        for point in points
        if _in_corridor(point, config)
    ]
    if len(candidates) < config.min_points:
        return DynamicObstacleDecision(
            action="clear",
            closest_distance_m=None,
            closing_speed_mps=0.0,
            point_count=len(candidates),
            reason="insufficient_points",
        )

    closest = min(point.x for point in candidates)
    closing_speed = 0.0
    if previous_closest_m is not None and dt_s is not None and dt_s > 1e-3:
        closing_speed = max(0.0, (previous_closest_m - closest) / dt_s)

    if closest <= config.stop_distance_m:
        return DynamicObstacleDecision(
            action="stop",
            closest_distance_m=closest,
            closing_speed_mps=closing_speed,
            point_count=len(candidates),
            reason="inside_stop_distance",
        )
    if closest <= config.slow_distance_m and closing_speed >= config.closing_stop_mps:
        return DynamicObstacleDecision(
            action="stop",
            closest_distance_m=closest,
            closing_speed_mps=closing_speed,
            point_count=len(candidates),
            reason="closing_fast",
        )
    if closest <= config.slow_distance_m:
        detour_lateral = _choose_detour_side(candidates, config.detour_lateral_m)
        return DynamicObstacleDecision(
            action="detour",
            closest_distance_m=closest,
            closing_speed_mps=closing_speed,
            point_count=len(candidates),
            reason="inside_detour_distance",
            detour_lateral_m=detour_lateral,
            detour_forward_m=max(config.detour_forward_m, min(closest, config.slow_distance_m)),
        )
    return DynamicObstacleDecision(
        action="clear",
        closest_distance_m=closest,
        closing_speed_mps=closing_speed,
        point_count=len(candidates),
        reason="outside_slow_distance",
    )


def _in_corridor(point: PointXYZ, config: DynamicObstacleConfig) -> bool:
    return (
        math.isfinite(point.x)
        and math.isfinite(point.y)
        and math.isfinite(point.z)
        and config.min_x_m <= point.x
        and abs(point.y) <= config.corridor_half_width_m
        and config.z_min_m <= point.z <= config.z_max_m
    )


def _choose_detour_side(points: list[PointXYZ], lateral_m: float) -> float:
    mean_y = sum(point.y for point in points) / max(len(points), 1)
    if mean_y >= 0.0:
        return -abs(lateral_m)
    return abs(lateral_m)
