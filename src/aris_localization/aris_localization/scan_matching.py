"""ROS-free known-map scan matching for V2A.

This is a deliberately small 2.5D matcher for the ARIS lightweight simulator:
it aligns LiDAR-frame points against a YAML box map using local grid search
around wheel odometry. The API is sensor/source agnostic, so a real LiDAR driver
can feed the same `/scan_cloud` contract later.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import yaml

from .localization_core import Pose2D, normalize_angle


@dataclass(frozen=True)
class BoxMapObject:
    center: tuple[float, float, float]
    size: tuple[float, float, float]
    label: str = "unknown"

    @property
    def xy_bounds(self) -> tuple[float, float, float, float]:
        cx, cy, _ = self.center
        sx, sy, _ = self.size
        return (cx - sx / 2.0, cy - sy / 2.0, cx + sx / 2.0, cy + sy / 2.0)


@dataclass(frozen=True)
class LidarExtrinsic2D:
    x: float = 0.6
    y: float = 0.0
    yaw: float = 0.0


@dataclass(frozen=True)
class ScanMatchConfig:
    xy_window_m: float = 0.20
    xy_step_m: float = 0.05
    yaw_window_rad: float = 0.08
    yaw_step_rad: float = 0.02
    max_points: int = 240
    prior_weight: float = 0.05
    distance_clip_m: float = 1.0
    min_improvement_m: float = 0.03


@dataclass(frozen=True)
class ScanMatchResult:
    pose: Pose2D
    mean_error_m: float
    used_points: int


def load_box_map(path: str | Path) -> list[BoxMapObject]:
    with Path(path).open("r") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"expected YAML mapping in {path}")
    boxes: list[BoxMapObject] = []
    for item in data.get("boxes", []):
        boxes.append(
            BoxMapObject(
                center=_triple(item["center"]),
                size=_triple(item["size"]),
                label=str(item.get("label", "unknown")),
            )
        )
    if not boxes:
        raise ValueError(f"known map must define at least one box: {path}")
    return boxes


def match_scan_to_map(
    points_lidar: Sequence[tuple[float, float, float]],
    odom_pose: Pose2D,
    known_map: Sequence[BoxMapObject],
    lidar_extrinsic: LidarExtrinsic2D = LidarExtrinsic2D(),
    config: ScanMatchConfig = ScanMatchConfig(),
) -> ScanMatchResult:
    sampled = _sample_points(points_lidar, config.max_points)
    if not sampled:
        raise ValueError("scan has no usable points")

    best_pose = odom_pose
    best_score = math.inf
    best_error = math.inf
    odom_error = scan_map_mean_error(
        sampled, odom_pose, known_map, lidar_extrinsic, config.distance_clip_m
    )
    for dx in _symmetric_grid(config.xy_window_m, config.xy_step_m):
        for dy in _symmetric_grid(config.xy_window_m, config.xy_step_m):
            for dyaw in _symmetric_grid(config.yaw_window_rad, config.yaw_step_rad):
                candidate = Pose2D(
                    x=odom_pose.x + dx,
                    y=odom_pose.y + dy,
                    yaw=normalize_angle(odom_pose.yaw + dyaw),
                )
                error = scan_map_mean_error(
                    sampled, candidate, known_map, lidar_extrinsic, config.distance_clip_m
                )
                prior = config.prior_weight * (dx * dx + dy * dy + dyaw * dyaw)
                score = error + prior
                if score < best_score:
                    best_score = score
                    best_error = error
                    best_pose = candidate

    if odom_error - best_error < config.min_improvement_m:
        return ScanMatchResult(pose=odom_pose, mean_error_m=odom_error, used_points=len(sampled))
    return ScanMatchResult(pose=best_pose, mean_error_m=best_error, used_points=len(sampled))


def scan_map_mean_error(
    points_lidar: Sequence[tuple[float, float, float]],
    candidate_pose: Pose2D,
    known_map: Sequence[BoxMapObject],
    lidar_extrinsic: LidarExtrinsic2D,
    distance_clip_m: float,
) -> float:
    total = 0.0
    lidar_x, lidar_y, lidar_yaw = _lidar_pose(candidate_pose, lidar_extrinsic)
    cos_yaw = math.cos(lidar_yaw)
    sin_yaw = math.sin(lidar_yaw)
    for px, py, _ in points_lidar:
        mx = lidar_x + cos_yaw * px - sin_yaw * py
        my = lidar_y + sin_yaw * px + cos_yaw * py
        total += min(_distance_to_map_xy(mx, my, known_map), distance_clip_m)
    return total / max(len(points_lidar), 1)


def _lidar_pose(base_pose: Pose2D, extrinsic: LidarExtrinsic2D) -> tuple[float, float, float]:
    cos_yaw = math.cos(base_pose.yaw)
    sin_yaw = math.sin(base_pose.yaw)
    return (
        base_pose.x + cos_yaw * extrinsic.x - sin_yaw * extrinsic.y,
        base_pose.y + sin_yaw * extrinsic.x + cos_yaw * extrinsic.y,
        normalize_angle(base_pose.yaw + extrinsic.yaw),
    )


def _distance_to_map_xy(x: float, y: float, known_map: Sequence[BoxMapObject]) -> float:
    return min(_distance_to_box_xy(x, y, box) for box in known_map)


def _distance_to_box_xy(x: float, y: float, box: BoxMapObject) -> float:
    min_x, min_y, max_x, max_y = box.xy_bounds
    if min_x <= x <= max_x and min_y <= y <= max_y:
        return min(x - min_x, max_x - x, y - min_y, max_y - y)
    clamped_x = max(min_x, min(max_x, x))
    clamped_y = max(min_y, min(max_y, y))
    return math.hypot(x - clamped_x, y - clamped_y)


def _sample_points(
    points: Sequence[tuple[float, float, float]], max_points: int
) -> list[tuple[float, float, float]]:
    usable = [point for point in points if math.isfinite(point[0]) and math.isfinite(point[1])]
    if len(usable) <= max_points:
        return usable
    step = len(usable) / float(max_points)
    return [usable[int(i * step)] for i in range(max_points)]


def _symmetric_grid(window: float, step: float) -> list[float]:
    if window <= 0.0:
        return [0.0]
    count = int(round(window / step))
    values = [0.0]
    for index in range(1, count + 1):
        delta = index * step
        values.extend((-delta, delta))
    return values


def _triple(values: Iterable[Any]) -> tuple[float, float, float]:
    items = tuple(float(value) for value in values)
    if len(items) != 3:
        raise ValueError(f"expected three numeric values, got {items}")
    return items
