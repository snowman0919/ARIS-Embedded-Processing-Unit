import pytest

from aris_bringup.operator_api import goal_event, parse_goal_request
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


def test_parse_operator_goal_request():
    goal = parse_goal_request('{"x": 9.0, "y": 1.2, "source": "test"}')

    assert goal.x == 9.0
    assert goal.y == 1.2
    assert goal.frame_id == "map"
    assert '"goal_accepted"' in goal_event(goal)


def test_parse_operator_goal_rejects_non_map_frame():
    with pytest.raises(ValueError, match="map-frame"):
        parse_goal_request('{"x": 1.0, "y": 2.0, "frame_id": "odom"}')
