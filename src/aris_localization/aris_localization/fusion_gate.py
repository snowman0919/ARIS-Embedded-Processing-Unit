"""ROS-free acceptance gate for LiDAR localization corrections."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .localization_core import Pose2D, normalize_angle
from .scan_matching import ScanMatchResult


@dataclass(frozen=True)
class CorrectionGateConfig:
    max_translation_m: float = 0.50
    max_yaw_rad: float = 0.25
    max_mean_error_m: float = 0.35
    min_used_points: int = 10


@dataclass(frozen=True)
class CorrectionDecision:
    accepted: bool
    pose: Pose2D
    reason: str
    translation_delta_m: float
    yaw_delta_rad: float


def evaluate_lidar_correction(
    odom_pose: Pose2D,
    scan_match: ScanMatchResult,
    config: CorrectionGateConfig = CorrectionGateConfig(),
) -> CorrectionDecision:
    dx = scan_match.pose.x - odom_pose.x
    dy = scan_match.pose.y - odom_pose.y
    translation_delta = math.hypot(dx, dy)
    yaw_delta = abs(normalize_angle(scan_match.pose.yaw - odom_pose.yaw))

    if scan_match.used_points < config.min_used_points:
        return _reject("too_few_points", odom_pose, translation_delta, yaw_delta)
    if scan_match.mean_error_m > config.max_mean_error_m:
        return _reject("scan_error_too_high", odom_pose, translation_delta, yaw_delta)
    if translation_delta > config.max_translation_m:
        return _reject("translation_jump_too_large", odom_pose, translation_delta, yaw_delta)
    if yaw_delta > config.max_yaw_rad:
        return _reject("yaw_jump_too_large", odom_pose, translation_delta, yaw_delta)

    return CorrectionDecision(
        accepted=True,
        pose=scan_match.pose,
        reason="accepted",
        translation_delta_m=translation_delta,
        yaw_delta_rad=yaw_delta,
    )


def _reject(
    reason: str,
    odom_pose: Pose2D,
    translation_delta: float,
    yaw_delta: float,
) -> CorrectionDecision:
    return CorrectionDecision(
        accepted=False,
        pose=odom_pose,
        reason=reason,
        translation_delta_m=translation_delta,
        yaw_delta_rad=yaw_delta,
    )
