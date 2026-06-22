"""ROS-free helpers for synchronizing ARIS pose into Gazebo."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class GazeboPose2D:
    x: float
    y: float
    yaw: float


def normalize_angle(angle: float) -> float:
    return math.atan2(math.sin(angle), math.cos(angle))


def should_send_pose(
    current: GazeboPose2D,
    last_sent: GazeboPose2D | None,
    *,
    min_translation_delta_m: float,
    min_yaw_delta_rad: float,
) -> bool:
    if last_sent is None:
        return True
    dx = current.x - last_sent.x
    dy = current.y - last_sent.y
    dyaw = normalize_angle(current.yaw - last_sent.yaw)
    return (
        math.hypot(dx, dy) >= min_translation_delta_m
        or abs(dyaw) >= min_yaw_delta_rad
    )


def pose_request_text(entity_name: str, pose: GazeboPose2D, entity_z_m: float) -> str:
    half_yaw = pose.yaw / 2.0
    return (
        f'name: "{entity_name}" '
        f"position {{ x: {pose.x:.6f} y: {pose.y:.6f} z: {entity_z_m:.6f} }} "
        f"orientation {{ z: {math.sin(half_yaw):.9f} w: {math.cos(half_yaw):.9f} }}"
    )


def gz_boolean_response_is_true(stdout: str) -> bool:
    return "data: true" in stdout
