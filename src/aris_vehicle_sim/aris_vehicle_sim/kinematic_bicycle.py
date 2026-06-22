from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class VehicleState:
    x: float = 0.0
    y: float = 0.0
    yaw: float = 0.0
    velocity_mps: float = 0.0
    steering_rad: float = 0.0


class KinematicBicycleModel:
    def __init__(self, wheelbase_m: float = 1.2) -> None:
        self.wheelbase_m = wheelbase_m

    def step(self, state: VehicleState, target_velocity_mps: float, target_steering_rad: float, dt_s: float) -> VehicleState:
        state.velocity_mps += (target_velocity_mps - state.velocity_mps) * min(dt_s * 3.0, 1.0)
        state.steering_rad += (target_steering_rad - state.steering_rad) * min(dt_s * 5.0, 1.0)
        state.x += state.velocity_mps * math.cos(state.yaw) * dt_s
        state.y += state.velocity_mps * math.sin(state.yaw) * dt_s
        state.yaw += state.velocity_mps / self.wheelbase_m * math.tan(state.steering_rad) * dt_s
        state.yaw = math.atan2(math.sin(state.yaw), math.cos(state.yaw))
        return state
