"""ROS-free V5 dynamic-obstacle corridor detector."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable


@dataclass(frozen=True)
class PointXYZ:
    x: float
    y: float
    z: float


@dataclass(frozen=True)
class DynamicObstacleDecision:
    action: str
    closest_distance_m: float | None
    closing_speed_mps: float
    point_count: int
    reason: str
    detour_lateral_m: float | None = None
    detour_forward_m: float | None = None
    track_id: int | None = None
    track_age: int = 0
    track_persistence_s: float = 0.0

    def as_dict(self) -> dict[str, float | int | str | None]:
        return {
            "action": self.action,
            "closest_distance_m": self.closest_distance_m,
            "closing_speed_mps": self.closing_speed_mps,
            "point_count": self.point_count,
            "reason": self.reason,
            "detour_lateral_m": self.detour_lateral_m,
            "detour_forward_m": self.detour_forward_m,
            "track_id": self.track_id,
            "track_age": self.track_age,
            "track_persistence_s": self.track_persistence_s,
        }


@dataclass(frozen=True)
class DynamicObstacleConfig:
    corridor_half_width_m: float = 0.8
    min_x_m: float = 0.25
    slow_distance_m: float = 4.0
    stop_distance_m: float = 1.4
    z_min_m: float = -0.6
    z_max_m: float = 1.8
    min_points: int = 3
    closing_stop_mps: float = 1.2
    detour_lateral_m: float = 1.0
    detour_forward_m: float = 2.0
    track_match_distance_m: float = 1.0
    track_forget_after_s: float = 1.0


@dataclass(frozen=True)
class ObstacleObservation:
    center_x: float
    center_y: float
    closest_distance_m: float
    point_count: int


@dataclass
class TrackedObstacle:
    track_id: int
    center_x: float
    center_y: float
    closest_distance_m: float
    first_seen_s: float
    last_seen_s: float
    age: int = 1
    velocity_x_mps: float = 0.0
    velocity_y_mps: float = 0.0

    @property
    def persistence_s(self) -> float:
        return max(0.0, self.last_seen_s - self.first_seen_s)

    @property
    def speed_mps(self) -> float:
        return math.hypot(self.velocity_x_mps, self.velocity_y_mps)


class DynamicObstacleTracker:
    def __init__(self, config: DynamicObstacleConfig = DynamicObstacleConfig()) -> None:
        self.config = config
        self.tracks: dict[int, TrackedObstacle] = {}
        self._next_track_id = 1

    def update(
        self, observation: ObstacleObservation | None, *, timestamp_s: float
    ) -> TrackedObstacle | None:
        self._drop_stale(timestamp_s)
        if observation is None:
            return None

        track = self._nearest_track(observation)
        if track is None:
            track = TrackedObstacle(
                track_id=self._next_track_id,
                center_x=observation.center_x,
                center_y=observation.center_y,
                closest_distance_m=observation.closest_distance_m,
                first_seen_s=timestamp_s,
                last_seen_s=timestamp_s,
            )
            self._next_track_id += 1
            self.tracks[track.track_id] = track
            return track

        dt_s = max(timestamp_s - track.last_seen_s, 1e-3)
        track.velocity_x_mps = (observation.center_x - track.center_x) / dt_s
        track.velocity_y_mps = (observation.center_y - track.center_y) / dt_s
        track.center_x = observation.center_x
        track.center_y = observation.center_y
        track.closest_distance_m = observation.closest_distance_m
        track.last_seen_s = timestamp_s
        track.age += 1
        return track

    def _nearest_track(self, observation: ObstacleObservation) -> TrackedObstacle | None:
        if not self.tracks:
            return None
        nearest = min(
            self.tracks.values(),
            key=lambda track: math.hypot(
                track.center_x - observation.center_x,
                track.center_y - observation.center_y,
            ),
        )
        distance = math.hypot(
            nearest.center_x - observation.center_x,
            nearest.center_y - observation.center_y,
        )
        if distance > self.config.track_match_distance_m:
            return None
        return nearest

    def _drop_stale(self, timestamp_s: float) -> None:
        stale = [
            track_id
            for track_id, track in self.tracks.items()
            if timestamp_s - track.last_seen_s > self.config.track_forget_after_s
        ]
        for track_id in stale:
            del self.tracks[track_id]


def evaluate_dynamic_obstacle(
    points: Iterable[PointXYZ],
    *,
    config: DynamicObstacleConfig = DynamicObstacleConfig(),
    previous_closest_m: float | None = None,
    dt_s: float | None = None,
) -> DynamicObstacleDecision:
    candidates = [point for point in points if _in_corridor(point, config)]
    if len(candidates) < config.min_points:
        return DynamicObstacleDecision(
            action="clear",
            closest_distance_m=None,
            closing_speed_mps=0.0,
            point_count=len(candidates),
            reason="insufficient_points",
        )

    closest = min(point.x for point in candidates)
    closing_speed = 0.0
    if previous_closest_m is not None and dt_s is not None and dt_s > 1e-3:
        closing_speed = max(0.0, (previous_closest_m - closest) / dt_s)

    if closest <= config.stop_distance_m:
        return DynamicObstacleDecision(
            action="stop",
            closest_distance_m=closest,
            closing_speed_mps=closing_speed,
            point_count=len(candidates),
            reason="inside_stop_distance",
        )
    if closest <= config.slow_distance_m and closing_speed >= config.closing_stop_mps:
        return DynamicObstacleDecision(
            action="stop",
            closest_distance_m=closest,
            closing_speed_mps=closing_speed,
            point_count=len(candidates),
            reason="closing_fast",
        )
    if closest <= config.slow_distance_m:
        detour_lateral = _choose_detour_side(candidates, config.detour_lateral_m)
        return DynamicObstacleDecision(
            action="detour",
            closest_distance_m=closest,
            closing_speed_mps=closing_speed,
            point_count=len(candidates),
            reason="inside_detour_distance",
            detour_lateral_m=detour_lateral,
            detour_forward_m=max(config.detour_forward_m, min(closest, config.slow_distance_m)),
        )
    return DynamicObstacleDecision(
        action="clear",
        closest_distance_m=closest,
        closing_speed_mps=closing_speed,
        point_count=len(candidates),
        reason="outside_slow_distance",
    )


def obstacle_observation(
    points: Iterable[PointXYZ],
    *,
    config: DynamicObstacleConfig = DynamicObstacleConfig(),
) -> ObstacleObservation | None:
    candidates = [point for point in points if _in_corridor(point, config)]
    if len(candidates) < config.min_points:
        return None
    return ObstacleObservation(
        center_x=sum(point.x for point in candidates) / len(candidates),
        center_y=sum(point.y for point in candidates) / len(candidates),
        closest_distance_m=min(point.x for point in candidates),
        point_count=len(candidates),
    )


def with_track(
    decision: DynamicObstacleDecision,
    track: TrackedObstacle | None,
) -> DynamicObstacleDecision:
    if track is None:
        return decision
    return DynamicObstacleDecision(
        action=decision.action,
        closest_distance_m=decision.closest_distance_m,
        closing_speed_mps=max(decision.closing_speed_mps, max(0.0, -track.velocity_x_mps)),
        point_count=decision.point_count,
        reason=decision.reason,
        detour_lateral_m=decision.detour_lateral_m,
        detour_forward_m=decision.detour_forward_m,
        track_id=track.track_id,
        track_age=track.age,
        track_persistence_s=track.persistence_s,
    )


def _in_corridor(point: PointXYZ, config: DynamicObstacleConfig) -> bool:
    return (
        math.isfinite(point.x)
        and math.isfinite(point.y)
        and math.isfinite(point.z)
        and config.min_x_m <= point.x
        and abs(point.y) <= config.corridor_half_width_m
        and config.z_min_m <= point.z <= config.z_max_m
    )


def _choose_detour_side(points: list[PointXYZ], lateral_m: float) -> float:
    mean_y = sum(point.y for point in points) / max(len(points), 1)
    if mean_y >= 0.0:
        return -abs(lateral_m)
    return abs(lateral_m)
