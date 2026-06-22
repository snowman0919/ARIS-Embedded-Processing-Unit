from __future__ import annotations

import math
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Pose2D:
    x: float
    y: float
    yaw: float


@dataclass(frozen=True)
class LocalPlanCommand:
    target_steering_rad: float
    target_velocity_mps: float
    brake: float
    dry_run: bool


class PurePursuit:
    def __init__(self, wheelbase_m: float = 1.2, lookahead_m: float = 2.0, max_speed_mps: float = 2.0) -> None:
        self.wheelbase_m = wheelbase_m
        self.lookahead_m = lookahead_m
        self.max_speed_mps = max_speed_mps

    def command(self, pose: Pose2D, path: list[tuple[float, float]], estop: bool = False) -> LocalPlanCommand:
        dry_run = os.environ.get("ARIS_ENABLE_REAL_ACTUATION", "0") != "1"
        if estop or not path:
            return LocalPlanCommand(0.0, 0.0, 1.0, dry_run=dry_run)

        target = self._lookahead_point(pose, path)
        dx = target[0] - pose.x
        dy = target[1] - pose.y
        local_x = math.cos(-pose.yaw) * dx - math.sin(-pose.yaw) * dy
        local_y = math.sin(-pose.yaw) * dx + math.cos(-pose.yaw) * dy
        if local_x <= 0.0:
            return LocalPlanCommand(0.0, 0.0, 0.5, dry_run=dry_run)

        curvature = 2.0 * local_y / max(self.lookahead_m * self.lookahead_m, 1e-6)
        steering = math.atan(self.wheelbase_m * curvature)
        speed = max(0.3, self.max_speed_mps * (1.0 - min(abs(steering), 0.8) / 0.8))
        return LocalPlanCommand(steering, speed, 0.0, dry_run=dry_run)

    def _lookahead_point(self, pose: Pose2D, path: list[tuple[float, float]]) -> tuple[float, float]:
        for point in path:
            dx = point[0] - pose.x
            dy = point[1] - pose.y
            local_x = math.cos(-pose.yaw) * dx - math.sin(-pose.yaw) * dy
            if local_x > 0.0 and math.hypot(dx, dy) >= self.lookahead_m:
                return point

        forward_points = [
            point
            for point in path
            if math.cos(-pose.yaw) * (point[0] - pose.x) - math.sin(-pose.yaw) * (point[1] - pose.y) > 0.0
        ]
        if forward_points:
            return forward_points[-1]
        return path[-1]
