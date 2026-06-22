"""ROS-free conversion from segmentation detections to map observations."""

from __future__ import annotations

import math
from dataclasses import dataclass

from aris_mapping.semantic_map import SemanticObservation


@dataclass(frozen=True)
class CameraIntrinsics:
    width_px: int
    height_px: int
    horizontal_fov_rad: float

    def __post_init__(self) -> None:
        if self.width_px <= 0 or self.height_px <= 0:
            raise ValueError("camera dimensions must be positive")
        if not 0.0 < self.horizontal_fov_rad < math.pi:
            raise ValueError("horizontal_fov_rad must be in (0, pi)")


@dataclass(frozen=True)
class SegmentationDetection:
    label: str
    confidence: float
    bbox_xywh: tuple[float, float, float, float]


@dataclass(frozen=True)
class VehiclePose2D:
    x: float
    y: float
    yaw: float


@dataclass(frozen=True)
class CameraExtrinsic2D:
    x: float
    y: float
    yaw: float


def detection_to_semantic_observation(
    detection: SegmentationDetection,
    vehicle_pose: VehiclePose2D,
    intrinsics: CameraIntrinsics,
    extrinsic: CameraExtrinsic2D,
    assumed_range_m: float,
    source: str,
) -> SemanticObservation:
    if not 0.0 <= detection.confidence <= 1.0:
        raise ValueError("detection confidence must be in [0, 1]")
    if assumed_range_m <= 0.0:
        raise ValueError("assumed_range_m must be positive")

    cx = detection.bbox_xywh[0] + detection.bbox_xywh[2] / 2.0
    normalized_x = (cx - intrinsics.width_px / 2.0) / (intrinsics.width_px / 2.0)
    bearing = normalized_x * intrinsics.horizontal_fov_rad / 2.0
    camera_yaw = vehicle_pose.yaw + extrinsic.yaw
    local_x = extrinsic.x + math.cos(bearing) * assumed_range_m
    local_y = extrinsic.y + math.sin(bearing) * assumed_range_m
    world_x = vehicle_pose.x + math.cos(camera_yaw) * local_x - math.sin(camera_yaw) * local_y
    world_y = vehicle_pose.y + math.sin(camera_yaw) * local_x + math.cos(camera_yaw) * local_y

    return SemanticObservation(
        x=world_x,
        y=world_y,
        label=detection.label,
        confidence=detection.confidence,
        source=source,
    )
