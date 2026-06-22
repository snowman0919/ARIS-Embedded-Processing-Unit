"""ROS-free route utilities for V1 teach-and-repeat.

Routes are CSV files with the V1 contract columns: x, y, yaw, v_target. The
planner still delegates steering and speed choice to the existing PurePursuit
core; this module only owns route file parsing and waypoint lookup helpers.
"""

from __future__ import annotations

import csv
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from .pure_pursuit import Pose2D

ROUTE_COLUMNS = ("x", "y", "yaw", "v_target")


@dataclass(frozen=True)
class RouteWaypoint:
    x: float
    y: float
    yaw: float
    v_target: float


def default_routes_dir() -> Path:
    configured = Path(os.environ.get("ARIS_DATA", str(Path.home() / "aris" / "data")))
    container_mount = Path("/aris/data")
    if (
        not configured.exists()
        and not configured.parent.exists()
        and container_mount.is_dir()
    ):
        configured = container_mount
    return configured / "routes"


def default_route_file() -> Path:
    return default_routes_dir() / "route.csv"


def resolve_route_file(route_file: str | os.PathLike[str] | None) -> Path:
    if route_file is None or str(route_file).strip() == "":
        return default_route_file()
    path = Path(os.path.expandvars(os.path.expanduser(str(route_file))))
    if not path.is_absolute():
        path = default_routes_dir() / path
    return path


def load_route_csv(route_file: str | os.PathLike[str]) -> list[RouteWaypoint]:
    path = resolve_route_file(route_file)
    if not path.exists():
        raise FileNotFoundError(f"route file does not exist: {path}")

    with path.open("r", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [column for column in ROUTE_COLUMNS if column not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"route file missing required columns: {', '.join(missing)}")

        route: list[RouteWaypoint] = []
        for line_number, row in enumerate(reader, start=2):
            try:
                route.append(
                    RouteWaypoint(
                        x=float(row["x"]),
                        y=float(row["y"]),
                        yaw=float(row["yaw"]),
                        v_target=float(row["v_target"]),
                    )
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid route row at line {line_number}: {row}") from exc

    if not route:
        raise ValueError(f"route file has no waypoints: {path}")
    return route


def write_route_csv(route_file: str | os.PathLike[str], route: Iterable[RouteWaypoint]) -> None:
    path = resolve_route_file(route_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ROUTE_COLUMNS)
        writer.writeheader()
        for waypoint in route:
            writer.writerow(
                {
                    "x": waypoint.x,
                    "y": waypoint.y,
                    "yaw": waypoint.yaw,
                    "v_target": waypoint.v_target,
                }
            )


def path_xy(route: Sequence[RouteWaypoint]) -> list[tuple[float, float]]:
    return [(waypoint.x, waypoint.y) for waypoint in route]


def select_lookahead_waypoint(
    pose: Pose2D, route: Sequence[RouteWaypoint], lookahead_m: float
) -> RouteWaypoint:
    """Return the first forward waypoint at least lookahead_m away.

    This intentionally mirrors PurePursuit's waypoint selection semantics so
    route-level utilities and tests reason about the same target as the planner
    without changing PurePursuit itself.
    """
    if not route:
        raise ValueError("route has no waypoints")

    for waypoint in route:
        dx = waypoint.x - pose.x
        dy = waypoint.y - pose.y
        local_x = math.cos(-pose.yaw) * dx - math.sin(-pose.yaw) * dy
        if local_x > 0.0 and math.hypot(dx, dy) >= lookahead_m:
            return waypoint

    forward_points = [
        waypoint
        for waypoint in route
        if math.cos(-pose.yaw) * (waypoint.x - pose.x)
        - math.sin(-pose.yaw) * (waypoint.y - pose.y)
        > 0.0
    ]
    if forward_points:
        return forward_points[-1]
    return route[-1]
