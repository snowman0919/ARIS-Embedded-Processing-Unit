import math

import pytest

from aris_localization.gazebo_pose_sync import (
    GazeboPose2D,
    gz_boolean_response_is_true,
    pose_request_text,
    should_send_pose,
)


def test_should_send_first_pose_and_thresholded_updates():
    current = GazeboPose2D(1.0, 2.0, 0.1)

    assert should_send_pose(
        current,
        None,
        min_translation_delta_m=0.5,
        min_yaw_delta_rad=0.2,
    )
    assert not should_send_pose(
        current,
        GazeboPose2D(1.1, 2.1, 0.15),
        min_translation_delta_m=0.5,
        min_yaw_delta_rad=0.2,
    )
    assert should_send_pose(
        current,
        GazeboPose2D(0.4, 2.0, 0.1),
        min_translation_delta_m=0.5,
        min_yaw_delta_rad=0.2,
    )
    assert should_send_pose(
        current,
        GazeboPose2D(1.0, 2.0, -0.2),
        min_translation_delta_m=0.5,
        min_yaw_delta_rad=0.2,
    )


def test_should_send_pose_handles_yaw_wraparound():
    assert not should_send_pose(
        GazeboPose2D(0.0, 0.0, -math.pi + 0.01),
        GazeboPose2D(0.0, 0.0, math.pi - 0.01),
        min_translation_delta_m=0.5,
        min_yaw_delta_rad=0.05,
    )


def test_pose_request_text_formats_gazebo_pose_message():
    request = pose_request_text("aris", GazeboPose2D(1.25, -0.5, math.pi / 2.0), 0.1)

    assert 'name: "aris"' in request
    assert "position { x: 1.250000 y: -0.500000 z: 0.100000 }" in request
    assert "orientation" in request
    assert "z: 0.707106781" in request
    assert "w: 0.707106781" in request


@pytest.mark.parametrize(
    ("stdout", "expected"),
    [
        ("data: true\n", True),
        ("header {}\ndata: true\n", True),
        ("data: false\n", False),
        ("", False),
    ],
)
def test_gz_boolean_response_is_true(stdout, expected):
    assert gz_boolean_response_is_true(stdout) is expected
