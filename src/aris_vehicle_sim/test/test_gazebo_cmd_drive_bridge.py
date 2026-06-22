import math

import pytest

from aris_vehicle_sim.gazebo_cmd_drive_bridge import cmd_drive_to_twist_values


def test_cmd_drive_to_twist_preserves_ackermann_yaw_rate():
    speed, yaw_rate = cmd_drive_to_twist_values(
        speed_mps=1.2,
        steering_rad=0.3,
        wheelbase_m=1.25,
        max_speed_mps=2.0,
        max_steer_rad=0.6,
    )

    assert speed == pytest.approx(1.2)
    assert yaw_rate == pytest.approx(1.2 / 1.25 * math.tan(0.3))


def test_cmd_drive_to_twist_clamps_speed_and_steering():
    speed, yaw_rate = cmd_drive_to_twist_values(
        speed_mps=5.0,
        steering_rad=2.0,
        wheelbase_m=1.25,
        max_speed_mps=0.8,
        max_steer_rad=0.4,
    )

    assert speed == pytest.approx(0.8)
    assert yaw_rate == pytest.approx(0.8 / 1.25 * math.tan(0.4))


def test_cmd_drive_to_twist_supports_reverse_for_gazebo_recovery():
    speed, yaw_rate = cmd_drive_to_twist_values(
        speed_mps=-0.5,
        steering_rad=-0.2,
        wheelbase_m=1.25,
        max_speed_mps=1.0,
        max_steer_rad=0.6,
    )

    assert speed == pytest.approx(-0.5)
    assert yaw_rate == pytest.approx(-0.5 / 1.25 * math.tan(-0.2))
