import math

import pytest

from aris_perception.semantic_projection import (
    CameraExtrinsic2D,
    CameraIntrinsics,
    SegmentationDetection,
    VehiclePose2D,
    detection_to_semantic_observation,
)


def test_center_detection_projects_forward_from_vehicle_pose():
    observation = detection_to_semantic_observation(
        SegmentationDetection("debris", 0.8, (300.0, 200.0, 40.0, 40.0)),
        VehiclePose2D(x=1.0, y=2.0, yaw=0.0),
        CameraIntrinsics(width_px=640, height_px=480, horizontal_fov_rad=math.radians(90.0)),
        CameraExtrinsic2D(x=0.5, y=0.0, yaw=0.0),
        assumed_range_m=4.0,
        source="front_camera_sim",
    )

    assert observation.label == "debris"
    assert observation.confidence == pytest.approx(0.8)
    assert observation.x == pytest.approx(5.5)
    assert observation.y == pytest.approx(2.0)


def test_right_side_detection_projects_with_positive_lateral_offset():
    observation = detection_to_semantic_observation(
        SegmentationDetection("mud", 0.7, (480.0, 100.0, 40.0, 40.0)),
        VehiclePose2D(x=0.0, y=0.0, yaw=0.0),
        CameraIntrinsics(width_px=640, height_px=480, horizontal_fov_rad=math.radians(90.0)),
        CameraExtrinsic2D(x=0.0, y=0.0, yaw=0.0),
        assumed_range_m=4.0,
        source="front_camera_sim",
    )

    assert observation.x > 0.0
    assert observation.y > 0.0


def test_projection_rejects_invalid_inputs():
    with pytest.raises(ValueError, match="confidence"):
        detection_to_semantic_observation(
            SegmentationDetection("road", 1.4, (0.0, 0.0, 10.0, 10.0)),
            VehiclePose2D(0.0, 0.0, 0.0),
            CameraIntrinsics(640, 480, math.radians(90.0)),
            CameraExtrinsic2D(0.0, 0.0, 0.0),
            assumed_range_m=1.0,
            source="test",
        )
