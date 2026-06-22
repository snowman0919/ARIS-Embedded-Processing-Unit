"""Pure mapping between the local planner command and the /cmd_drive contract.

Kept ROS-free so it is unit-testable and reused identically in sim and on the
real vehicle. The planner emits steering + speed; brake is folded into the
commanded speed and also surfaced as a normalized deceleration intent so a real
MCU can engage friction brakes (the kinematic sim simply ignores acceleration).
"""

from __future__ import annotations

from dataclasses import dataclass

from .pure_pursuit import LocalPlanCommand


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class AckermannFields:
    steering_angle_rad: float
    speed_mps: float
    acceleration_mps2: float  # <= 0; magnitude is the normalized brake fraction


def local_plan_to_ackermann(command: LocalPlanCommand) -> AckermannFields:
    brake = _clamp(command.brake, 0.0, 1.0)
    effective_speed = max(0.0, command.target_velocity_mps) * (1.0 - brake)
    return AckermannFields(
        steering_angle_rad=command.target_steering_rad,
        speed_mps=effective_speed,
        acceleration_mps2=-brake,
    )


def ackermann_to_brake(acceleration_mps2: float) -> float:
    """Recover the normalized brake fraction the HAL applies (inverse mapping)."""
    return _clamp(-acceleration_mps2, 0.0, 1.0)
