"""Pure teleop mapping: a Twist command -> Ackermann steering + speed.

ROS-free and unit-testable. For manual driving we map angular.z directly to a
steering angle (intuitive left/right) rather than treating it as a yaw rate,
which also avoids the v->0 singularity of the geometric inversion. Both axes are
clamped to the vehicle limits. The result is published verbatim on /cmd_drive,
so teleop obeys the same control contract as the autonomous planner.
"""

from __future__ import annotations

from dataclasses import dataclass


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class TeleopCommand:
    steering_angle_rad: float
    speed_mps: float


def twist_to_ackermann(
    linear_x: float,
    angular_z: float,
    max_steer_rad: float,
    max_speed_mps: float,
    steer_scale: float = 1.0,
) -> TeleopCommand:
    speed = _clamp(linear_x, -max_speed_mps, max_speed_mps)
    steering = _clamp(angular_z * steer_scale, -max_steer_rad, max_steer_rad)
    return TeleopCommand(steering_angle_rad=steering, speed_mps=speed)
