import math

import pytest

from aris_localization.fusion_gate import CorrectionGateConfig, evaluate_lidar_correction
from aris_localization.localization_core import (
    Pose2D,
    Transform2D,
    map_to_odom_from_base_poses,
    normalize_angle,
    point_to_polyline_distance,
    transform_pose,
)
from aris_localization.scan_matching import (
    BoxMapObject,
    LidarExtrinsic2D,
    ScanMatchConfig,
    ScanMatchResult,
    match_scan_to_map,
    scan_map_mean_error,
)
from aris_vehicle_sim.lidar_sim_core import (
    BoxObstacle,
    LidarProfile,
    Pose3D,
    pose_lidar_from_base,
    simulate_lidar_frame,
)


def assert_pose_close(actual: Pose2D, expected: Pose2D) -> None:
    assert actual.x == pytest.approx(expected.x, abs=1e-9)
    assert actual.y == pytest.approx(expected.y, abs=1e-9)
    assert normalize_angle(actual.yaw - expected.yaw) == pytest.approx(0.0, abs=1e-9)


def test_map_to_odom_transform_aligns_base_poses():
    odom_base = Pose2D(x=4.0, y=1.0, yaw=0.3)
    map_base = Pose2D(x=10.0, y=-2.0, yaw=1.0)

    map_to_odom = map_to_odom_from_base_poses(map_base, odom_base)

    assert_pose_close(transform_pose(map_to_odom, odom_base), map_base)


def test_transform_pose_rotates_and_translates():
    transformed = transform_pose(
        Transform2D(x=1.0, y=2.0, yaw=math.pi / 2.0),
        Pose2D(x=2.0, y=0.0, yaw=math.pi / 2.0),
    )

    assert_pose_close(transformed, Pose2D(x=1.0, y=4.0, yaw=math.pi))


def test_point_to_polyline_distance_uses_nearest_segment():
    polyline = [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0)]

    assert point_to_polyline_distance((1.0, 0.3), polyline) == pytest.approx(0.3)
    assert point_to_polyline_distance((2.4, 1.0), polyline) == pytest.approx(0.4)


def test_point_to_polyline_distance_rejects_degenerate_route():
    with pytest.raises(ValueError, match="at least two"):
        point_to_polyline_distance((0.0, 0.0), [(0.0, 0.0)])


def test_known_map_scan_matching_corrects_lateral_and_yaw_error():
    known_map = [
        BoxMapObject(center=(5.0, 0.0, 0.0), size=(1.0, 4.0, 3.0), label="front_wall"),
        BoxMapObject(center=(2.5, 2.0, 0.0), size=(5.0, 0.3, 3.0), label="left_wall"),
        BoxMapObject(center=(2.5, -2.0, 0.0), size=(5.0, 0.3, 3.0), label="right_wall"),
    ]
    sim_world = [
        BoxObstacle(center=box.center, size=box.size, label=box.label)
        for box in known_map
    ]
    profile = LidarProfile(
        model="test",
        horizontal_fov_deg=100.0,
        horizontal_samples=101,
        vertical_angles_deg=(-5.0, 0.0, 5.0),
        scan_rate_hz=10.0,
        range_min_m=0.1,
        range_max_m=20.0,
    )
    extrinsic = LidarExtrinsic2D(x=0.6)
    true_pose = Pose2D(x=0.0, y=0.0, yaw=0.0)
    lidar_pose = pose_lidar_from_base(
        Pose3D(true_pose.x, true_pose.y, 0.0, yaw=true_pose.yaw),
        Pose3D(extrinsic.x, extrinsic.y, 0.0, yaw=extrinsic.yaw),
    )
    returns = simulate_lidar_frame(lidar_pose, profile, sim_world)
    points = [(point.x, point.y, point.z) for point in returns]
    odom_guess = Pose2D(x=0.0, y=0.12, yaw=0.04)

    result = match_scan_to_map(
        points,
        odom_guess,
        known_map,
        extrinsic,
        ScanMatchConfig(
            xy_window_m=0.20,
            xy_step_m=0.04,
            yaw_window_rad=0.08,
            yaw_step_rad=0.02,
            prior_weight=0.0,
            min_improvement_m=0.0,
        ),
    )

    assert result.pose.y == pytest.approx(0.0, abs=0.04)
    assert result.pose.yaw == pytest.approx(0.0, abs=0.03)
    assert result.mean_error_m < scan_map_mean_error(points, odom_guess, known_map, extrinsic, 1.0)


def test_correction_gate_accepts_bounded_lidar_correction():
    odom = Pose2D(x=1.0, y=0.10, yaw=0.02)
    result = ScanMatchResult(
        pose=Pose2D(x=1.0, y=0.0, yaw=0.0),
        mean_error_m=0.03,
        used_points=120,
    )

    decision = evaluate_lidar_correction(odom, result)

    assert decision.accepted
    assert decision.pose == result.pose
    assert decision.translation_delta_m == pytest.approx(0.10)


def test_correction_gate_rejects_large_or_low_quality_corrections():
    odom = Pose2D(x=1.0, y=0.0, yaw=0.0)
    config = CorrectionGateConfig(
        max_translation_m=0.5,
        max_yaw_rad=0.2,
        max_mean_error_m=0.2,
        min_used_points=20,
    )

    large_jump = evaluate_lidar_correction(
        odom,
        ScanMatchResult(Pose2D(x=1.8, y=0.0, yaw=0.0), mean_error_m=0.05, used_points=100),
        config,
    )
    noisy_scan = evaluate_lidar_correction(
        odom,
        ScanMatchResult(Pose2D(x=1.1, y=0.0, yaw=0.0), mean_error_m=0.4, used_points=100),
        config,
    )
    sparse_scan = evaluate_lidar_correction(
        odom,
        ScanMatchResult(Pose2D(x=1.1, y=0.0, yaw=0.0), mean_error_m=0.05, used_points=4),
        config,
    )

    assert not large_jump.accepted
    assert large_jump.reason == "translation_jump_too_large"
    assert large_jump.pose == odom
    assert not noisy_scan.accepted
    assert noisy_scan.reason == "scan_error_too_high"
    assert noisy_scan.pose == odom
    assert not sparse_scan.accepted
    assert sparse_scan.reason == "too_few_points"
    assert sparse_scan.pose == odom
