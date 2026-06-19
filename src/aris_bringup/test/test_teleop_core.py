from aris_bringup.teleop_core import twist_to_ackermann


def test_forward_straight():
    cmd = twist_to_ackermann(2.0, 0.0, max_steer_rad=0.6, max_speed_mps=3.0)
    assert cmd.speed_mps == 2.0
    assert cmd.steering_angle_rad == 0.0


def test_steering_clamped_to_max():
    cmd = twist_to_ackermann(1.0, 5.0, max_steer_rad=0.6, max_speed_mps=3.0, steer_scale=1.0)
    assert cmd.steering_angle_rad == 0.6


def test_speed_clamped_to_max():
    cmd = twist_to_ackermann(10.0, 0.0, max_steer_rad=0.6, max_speed_mps=3.0)
    assert cmd.speed_mps == 3.0


def test_reverse_and_left_steer():
    cmd = twist_to_ackermann(-1.0, -0.2, max_steer_rad=0.6, max_speed_mps=3.0, steer_scale=1.0)
    assert cmd.speed_mps == -1.0
    assert cmd.steering_angle_rad == -0.2
