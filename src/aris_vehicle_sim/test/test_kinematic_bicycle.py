from aris_vehicle_sim.kinematic_bicycle import KinematicBicycleModel, VehicleState
from aris_vehicle_sim.lidar_sim_core import (
    BoxObstacle,
    LidarProfile,
    Pose3D,
    load_profile,
    load_world,
    pose_lidar_from_base,
    simulate_lidar_frame,
)


def test_bicycle_model_moves_forward():
    state = VehicleState()
    model = KinematicBicycleModel()
    model.step(state, target_velocity_mps=1.0, target_steering_rad=0.0, dt_s=1.0)
    assert state.x > 0.0
    assert abs(state.y) < 1e-9


def test_bicycle_model_turns():
    state = VehicleState(velocity_mps=1.0)
    model = KinematicBicycleModel()
    model.step(state, target_velocity_mps=1.0, target_steering_rad=0.2, dt_s=1.0)
    assert state.yaw > 0.0


def test_lidar_sim_hits_front_box_without_noise():
    profile = LidarProfile(
        model="test",
        horizontal_fov_deg=0.0,
        horizontal_samples=1,
        vertical_angles_deg=(0.0,),
        scan_rate_hz=10.0,
        range_min_m=0.1,
        range_max_m=20.0,
    )
    world = [
        BoxObstacle(
            center=(5.0, 0.0, 0.0),
            size=(1.0, 1.0, 1.0),
            label="box",
            intensity=123.0,
        )
    ]

    returns = simulate_lidar_frame(Pose3D(0.0, 0.0, 0.0), profile, world)

    assert len(returns) == 1
    assert returns[0].x == 4.5
    assert abs(returns[0].y) < 1e-9
    assert abs(returns[0].z) < 1e-9
    assert returns[0].intensity == 123.0
    assert returns[0].ring == 0
    assert returns[0].time_s == 0.0


def test_lidar_sim_populates_rings_and_relative_times():
    profile = LidarProfile(
        model="test",
        horizontal_fov_deg=10.0,
        horizontal_samples=3,
        vertical_angles_deg=(-2.0, 0.0),
        scan_rate_hz=20.0,
        range_min_m=0.1,
        range_max_m=20.0,
    )
    world = [
        BoxObstacle(center=(5.0, 0.0, 0.0), size=(1.0, 6.0, 6.0), label="wall")
    ]

    returns = simulate_lidar_frame(Pose3D(0.0, 0.0, 0.0), profile, world)

    assert len(returns) == profile.points_per_frame
    assert {point.ring for point in returns} == {0, 1}
    assert returns[0].time_s == 0.0
    assert returns[-1].time_s > returns[0].time_s
    assert returns[-1].time_s < 1.0 / profile.scan_rate_hz


def test_lidar_pose_uses_base_to_lidar_extrinsic():
    pose = pose_lidar_from_base(
        Pose3D(x=1.0, y=2.0, z=0.0, yaw=1.5707963267948966),
        Pose3D(x=0.5, y=0.0, z=0.9),
    )

    assert pose.x == 1.0
    assert pose.y == 2.5
    assert pose.z == 0.9


def test_lidar_profile_and_world_load_from_yaml(tmp_path):
    profile_file = tmp_path / "profile.yaml"
    profile_file.write_text(
        """
lidar:
  model: test_profile
  horizontal_fov_deg: 90
  horizontal_samples: 5
  vertical_angles_deg: [-1, 1]
  scan_rate_hz: 10
  range_min_m: 0.1
  range_max_m: 30
"""
    )
    world_file = tmp_path / "world.yaml"
    world_file.write_text(
        """
boxes:
  - center: [3, 0, 1]
    size: [1, 1, 2]
    label: obstacle
    intensity: 99
"""
    )

    profile = load_profile(profile_file)
    world = load_world(world_file)

    assert profile.model == "test_profile"
    assert profile.points_per_frame == 10
    assert world[0].label == "obstacle"
    assert world[0].intensity == 99.0
