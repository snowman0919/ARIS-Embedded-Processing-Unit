from __future__ import annotations

import math


def cmd_drive_to_twist_values(
    speed_mps: float,
    steering_rad: float,
    wheelbase_m: float,
    max_speed_mps: float,
    max_steer_rad: float,
) -> tuple[float, float]:
    speed = max(-max_speed_mps, min(max_speed_mps, float(speed_mps)))
    steer = max(-max_steer_rad, min(max_steer_rad, float(steering_rad)))
    wheelbase = max(float(wheelbase_m), 1e-6)
    return speed, speed / wheelbase * math.tan(steer)
