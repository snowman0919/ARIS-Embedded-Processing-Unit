"""Spec-driven 3D LiDAR simulator core.

This module is deliberately ROS-free. It turns a LiDAR profile, a simple 3D box
world, and the current sensor pose into point returns shaped like a real LiDAR
driver would publish. The ROS wrapper only converts the returns to PointCloud2.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import yaml


@dataclass(frozen=True)
class Pose3D:
    x: float
    y: float
    z: float
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0


@dataclass(frozen=True)
class BoxObstacle:
    center: tuple[float, float, float]
    size: tuple[float, float, float]
    label: str
    intensity: float = 80.0

    @property
    def bounds(self) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        cx, cy, cz = self.center
        sx, sy, sz = self.size
        return (
            (cx - sx / 2.0, cy - sy / 2.0, cz - sz / 2.0),
            (cx + sx / 2.0, cy + sy / 2.0, cz + sz / 2.0),
        )


@dataclass(frozen=True)
class LidarProfile:
    model: str
    horizontal_fov_deg: float
    horizontal_samples: int
    vertical_angles_deg: tuple[float, ...]
    scan_rate_hz: float
    range_min_m: float
    range_max_m: float
    range_noise_std_m: float = 0.0
    angular_noise_std_deg: float = 0.0
    dropout_rate: float = 0.0

    @property
    def points_per_frame(self) -> int:
        return self.horizontal_samples * len(self.vertical_angles_deg)


@dataclass(frozen=True)
class LidarReturn:
    x: float
    y: float
    z: float
    intensity: float
    ring: int
    time_s: float
    label: str


def load_profile(path: str | Path) -> LidarProfile:
    data = _load_yaml(path)
    lidar = data["lidar"]
    vertical = tuple(float(angle) for angle in lidar["vertical_angles_deg"])
    if not vertical:
        raise ValueError("lidar.vertical_angles_deg must contain at least one channel")
    return LidarProfile(
        model=str(lidar["model"]),
        horizontal_fov_deg=float(lidar["horizontal_fov_deg"]),
        horizontal_samples=int(lidar["horizontal_samples"]),
        vertical_angles_deg=vertical,
        scan_rate_hz=float(lidar["scan_rate_hz"]),
        range_min_m=float(lidar["range_min_m"]),
        range_max_m=float(lidar["range_max_m"]),
        range_noise_std_m=float(lidar.get("range_noise_std_m", 0.0)),
        angular_noise_std_deg=float(lidar.get("angular_noise_std_deg", 0.0)),
        dropout_rate=float(lidar.get("dropout_rate", 0.0)),
    )


def load_world(path: str | Path) -> list[BoxObstacle]:
    data = _load_yaml(path)
    obstacles: list[BoxObstacle] = []
    for item in data.get("boxes", []):
        obstacles.append(
            BoxObstacle(
                center=_triple(item["center"]),
                size=_triple(item["size"]),
                label=str(item.get("label", "unknown")),
                intensity=float(item.get("intensity", 80.0)),
            )
        )
    if not obstacles:
        raise ValueError("sim world must define at least one box")
    return obstacles


def simulate_lidar_frame(
    lidar_pose_map: Pose3D,
    profile: LidarProfile,
    world: Sequence[BoxObstacle],
    *,
    rng: random.Random | None = None,
) -> list[LidarReturn]:
    rng = rng or random.Random()
    returns: list[LidarReturn] = []
    min_yaw = -math.radians(profile.horizontal_fov_deg) / 2.0
    yaw_step = math.radians(profile.horizontal_fov_deg) / max(profile.horizontal_samples - 1, 1)
    angular_noise_std = math.radians(profile.angular_noise_std_deg)
    frame_period_s = 1.0 / max(profile.scan_rate_hz, 1e-6)
    total_points = max(profile.points_per_frame, 1)

    point_index = 0
    for ring, vertical_deg in enumerate(profile.vertical_angles_deg):
        base_pitch = math.radians(vertical_deg)
        for horizontal_index in range(profile.horizontal_samples):
            if profile.dropout_rate > 0.0 and rng.random() < profile.dropout_rate:
                point_index += 1
                continue

            rel_yaw = min_yaw + yaw_step * horizontal_index
            rel_pitch = base_pitch
            if angular_noise_std > 0.0:
                rel_yaw += rng.gauss(0.0, angular_noise_std)
                rel_pitch += rng.gauss(0.0, angular_noise_std)

            direction_lidar = _direction_from_angles(rel_yaw, rel_pitch)
            direction_map = _rotate_lidar_to_map(direction_lidar, lidar_pose_map.yaw)
            hit = _nearest_box_hit(lidar_pose_map, direction_map, world, profile)
            if hit is None:
                point_index += 1
                continue

            distance, obstacle = hit
            measured_distance = distance
            if profile.range_noise_std_m > 0.0:
                measured_distance += rng.gauss(0.0, profile.range_noise_std_m)
            measured_distance = min(max(measured_distance, profile.range_min_m), profile.range_max_m)

            x = direction_lidar[0] * measured_distance
            y = direction_lidar[1] * measured_distance
            z = direction_lidar[2] * measured_distance
            returns.append(
                LidarReturn(
                    x=x,
                    y=y,
                    z=z,
                    intensity=obstacle.intensity,
                    ring=ring,
                    time_s=frame_period_s * point_index / total_points,
                    label=obstacle.label,
                )
            )
            point_index += 1

    return returns


def pose_lidar_from_base(base_pose: Pose3D, lidar_extrinsic: Pose3D) -> Pose3D:
    cos_yaw = math.cos(base_pose.yaw)
    sin_yaw = math.sin(base_pose.yaw)
    return Pose3D(
        x=base_pose.x + cos_yaw * lidar_extrinsic.x - sin_yaw * lidar_extrinsic.y,
        y=base_pose.y + sin_yaw * lidar_extrinsic.x + cos_yaw * lidar_extrinsic.y,
        z=base_pose.z + lidar_extrinsic.z,
        roll=base_pose.roll + lidar_extrinsic.roll,
        pitch=base_pose.pitch + lidar_extrinsic.pitch,
        yaw=base_pose.yaw + lidar_extrinsic.yaw,
    )


def _nearest_box_hit(
    origin: Pose3D,
    direction: tuple[float, float, float],
    world: Sequence[BoxObstacle],
    profile: LidarProfile,
) -> tuple[float, BoxObstacle] | None:
    best: tuple[float, BoxObstacle] | None = None
    for obstacle in world:
        distance = _ray_aabb_distance((origin.x, origin.y, origin.z), direction, obstacle)
        if distance is None or distance < profile.range_min_m or distance > profile.range_max_m:
            continue
        if best is None or distance < best[0]:
            best = (distance, obstacle)
    return best


def _ray_aabb_distance(
    origin: tuple[float, float, float],
    direction: tuple[float, float, float],
    box: BoxObstacle,
) -> float | None:
    bounds_min, bounds_max = box.bounds
    t_min = -math.inf
    t_max = math.inf
    for axis in range(3):
        if abs(direction[axis]) < 1e-12:
            if origin[axis] < bounds_min[axis] or origin[axis] > bounds_max[axis]:
                return None
            continue
        inv_d = 1.0 / direction[axis]
        t0 = (bounds_min[axis] - origin[axis]) * inv_d
        t1 = (bounds_max[axis] - origin[axis]) * inv_d
        if t0 > t1:
            t0, t1 = t1, t0
        t_min = max(t_min, t0)
        t_max = min(t_max, t1)
        if t_max < t_min:
            return None
    if t_max < 0.0:
        return None
    return t_min if t_min >= 0.0 else t_max


def _direction_from_angles(yaw: float, pitch: float) -> tuple[float, float, float]:
    cos_pitch = math.cos(pitch)
    return (
        cos_pitch * math.cos(yaw),
        cos_pitch * math.sin(yaw),
        math.sin(pitch),
    )


def _rotate_lidar_to_map(
    direction_lidar: tuple[float, float, float], yaw: float
) -> tuple[float, float, float]:
    cos_yaw = math.cos(yaw)
    sin_yaw = math.sin(yaw)
    x, y, z = direction_lidar
    return (
        cos_yaw * x - sin_yaw * y,
        sin_yaw * x + cos_yaw * y,
        z,
    )


def _load_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"expected YAML mapping in {path}")
    return data


def _triple(values: Iterable[Any]) -> tuple[float, float, float]:
    items = tuple(float(value) for value in values)
    if len(items) != 3:
        raise ValueError(f"expected three numeric values, got {items}")
    return items
