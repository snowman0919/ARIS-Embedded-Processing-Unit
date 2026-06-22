"""ROS-free helpers for the V2 localization contract.

The real V2 stack must own `/odometry/filtered` and `map->odom`. These helpers
make that contract testable without ROS: given an odom-frame base pose and a
map-frame matched base pose, compute the map->odom transform that aligns them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class Pose2D:
    x: float
    y: float
    yaw: float


@dataclass(frozen=True)
class Transform2D:
    x: float
    y: float
    yaw: float


def normalize_angle(angle: float) -> float:
    return math.atan2(math.sin(angle), math.cos(angle))


def transform_pose(transform: Transform2D, pose: Pose2D) -> Pose2D:
    cos_yaw = math.cos(transform.yaw)
    sin_yaw = math.sin(transform.yaw)
    return Pose2D(
        x=transform.x + cos_yaw * pose.x - sin_yaw * pose.y,
        y=transform.y + sin_yaw * pose.x + cos_yaw * pose.y,
        yaw=normalize_angle(transform.yaw + pose.yaw),
    )


def inverse_pose_transform(pose: Pose2D) -> Transform2D:
    cos_yaw = math.cos(-pose.yaw)
    sin_yaw = math.sin(-pose.yaw)
    return Transform2D(
        x=-(cos_yaw * pose.x - sin_yaw * pose.y),
        y=-(sin_yaw * pose.x + cos_yaw * pose.y),
        yaw=normalize_angle(-pose.yaw),
    )


def compose(a: Transform2D, b: Transform2D) -> Transform2D:
    posed = transform_pose(a, Pose2D(b.x, b.y, b.yaw))
    return Transform2D(posed.x, posed.y, posed.yaw)


def map_to_odom_from_base_poses(map_base: Pose2D, odom_base: Pose2D) -> Transform2D:
    """Compute map->odom so `map_base == map_to_odom * odom_base`."""
    return compose(
        Transform2D(map_base.x, map_base.y, map_base.yaw),
        inverse_pose_transform(odom_base),
    )


def point_to_polyline_distance(point: tuple[float, float], polyline: Sequence[tuple[float, float]]) -> float:
    if len(polyline) < 2:
        raise ValueError("polyline needs at least two points")
    return min(
        _point_to_segment_distance(point, a, b)
        for a, b in zip(polyline, polyline[1:])
    )


def _point_to_segment_distance(
    point: tuple[float, float], a: tuple[float, float], b: tuple[float, float]
) -> float:
    px, py = point
    ax, ay = a
    bx, by = b
    dx = bx - ax
    dy = by - ay
    denom = dx * dx + dy * dy
    if denom <= 1e-12:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / denom))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))
