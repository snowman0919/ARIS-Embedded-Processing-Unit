#!/usr/bin/env python3
"""Export an ARIS route CSV into the Flutter GUI map snapshot format.

The GUI consumes a compact JSON snapshot so it can render route, local plan,
semantic cells, and LiDAR returns without depending on ROS at startup. This
script bridges the existing V1/V3 route CSV contract into that display format.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--route", required=True, help="Route CSV with x,y,yaw,v_target columns.")
    parser.add_argument(
        "--out",
        default="src/aris_gui/assets/snapshots/aris_map_snapshot.json",
        help="Snapshot JSON path to write.",
    )
    parser.add_argument("--map-id", default="", help="Map id stored in the snapshot.")
    parser.add_argument("--max-points", type=int, default=90, help="Maximum path points to emit.")
    parser.add_argument(
        "--semantic-cell",
        action="append",
        default=[],
        metavar="X,Y,LABEL,CONFIDENCE,TRAVERSABILITY",
        help="Add a semantic cell in map coordinates. Can be repeated.",
    )
    return parser.parse_args()


def load_route(path: Path) -> list[dict[str, float]]:
    with path.open("r", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [column for column in ("x", "y", "yaw", "v_target") if column not in (reader.fieldnames or [])]
        if missing:
            raise SystemExit(f"route file missing required columns: {', '.join(missing)}")

        route: list[dict[str, float]] = []
        for line_number, row in enumerate(reader, start=2):
            try:
                route.append(
                    {
                        "x": float(row["x"]),
                        "y": float(row["y"]),
                        "yaw": float(row["yaw"]),
                        "v_target": float(row["v_target"]),
                    }
                )
            except (TypeError, ValueError) as exc:
                raise SystemExit(f"invalid route row at line {line_number}: {row}") from exc

    if len(route) < 2:
        raise SystemExit(f"route file needs at least two waypoints: {path}")
    return route


def downsample(points: list[dict[str, float]], max_points: int) -> list[dict[str, float]]:
    if len(points) <= max_points:
        return points
    stride = max(1, math.ceil(len(points) / max_points))
    sampled = points[::stride]
    if sampled[-1] != points[-1]:
        sampled.append(points[-1])
    return sampled


def route_point(route: list[dict[str, float]], fraction: float) -> dict[str, float]:
    index = round((len(route) - 1) * fraction)
    return route[max(0, min(index, len(route) - 1))]


def parse_semantic_cell(raw: str) -> dict[str, float | str]:
    parts = [part.strip() for part in raw.split(",")]
    if len(parts) != 5:
        raise SystemExit(f"invalid --semantic-cell value: {raw}")
    try:
        return {
            "x": round(float(parts[0]), 3),
            "y": round(float(parts[1]), 3),
            "label": parts[2],
            "confidence": float(parts[3]),
            "traversability": float(parts[4]),
        }
    except ValueError as exc:
        raise SystemExit(f"invalid --semantic-cell number: {raw}") from exc


def default_semantic_cells(route: list[dict[str, float]]) -> list[dict[str, float | str]]:
    one_third = route_point(route, 0.30)
    middle = route_point(route, 0.52)
    late = route_point(route, 0.74)
    return [
        {
            "x": round(middle["x"], 3),
            "y": round(middle["y"], 3),
            "label": "debris",
            "confidence": 0.93,
            "traversability": 0.94,
        },
        {
            "x": round(one_third["x"], 3),
            "y": round(one_third["y"] - 1.15, 3),
            "label": "grass",
            "confidence": 0.74,
            "traversability": 0.34,
        },
        {
            "x": round(late["x"], 3),
            "y": round(late["y"] + 1.18, 3),
            "label": "obstacle",
            "confidence": 0.87,
            "traversability": 0.98,
        },
    ]


def local_path(route: list[dict[str, float]], cells: list[dict[str, float | str]]) -> list[dict[str, float]]:
    plan: list[dict[str, float]] = []
    blockers = [cell for cell in cells if float(cell["traversability"]) >= 0.8]
    for point in route:
        y_offset = 0.0
        for cell in blockers:
            dx = point["x"] - float(cell["x"])
            distance = abs(dx)
            if distance > 1.8:
                continue
            direction = -1.0 if float(cell["y"]) > point["y"] else 1.0
            if abs(float(cell["y"]) - point["y"]) < 0.15:
                direction = 1.0
            y_offset += direction * 0.88 * (1.0 + math.cos(distance / 1.8 * math.pi)) / 2.0
        plan.append({"x": round(point["x"], 3), "y": round(point["y"] + y_offset, 3)})
    return plan


def lidar_returns(route: list[dict[str, float]], cells: list[dict[str, float | str]]) -> list[dict[str, float]]:
    hits = [
        {
            "x": round(float(cell["x"]), 3),
            "y": round(float(cell["y"]), 3),
            "intensity": round(80.0 + float(cell["confidence"]) * 70.0, 1),
        }
        for cell in cells
    ]
    for fraction, side in ((0.65, -1.6), (0.82, 1.9), (0.92, -1.2)):
        point = route_point(route, fraction)
        hits.append(
            {
                "x": round(point["x"], 3),
                "y": round(point["y"] + side, 3),
                "intensity": 68.0,
            }
        )
    return hits


def point_only(point: dict[str, float]) -> dict[str, float]:
    return {"x": round(point["x"], 3), "y": round(point["y"], 3)}


def bounds_for(
    route: list[dict[str, float]],
    local: list[dict[str, float]],
    cells: list[dict[str, float | str]],
) -> dict[str, float]:
    xs = [point["x"] for point in route] + [point["x"] for point in local]
    ys = [point["y"] for point in route] + [point["y"] for point in local]
    xs.extend(float(cell["x"]) for cell in cells)
    ys.extend(float(cell["y"]) for cell in cells)
    return {
        "min_x": round(min(xs) - 0.8, 3),
        "max_x": round(max(xs) + 0.8, 3),
        "min_y": round(min(ys) - 1.0, 3),
        "max_y": round(max(ys) + 1.0, 3),
    }


def main() -> None:
    args = parse_args()
    route_path = Path(args.route).expanduser()
    out_path = Path(args.out).expanduser()
    route = load_route(route_path)
    display_route = downsample(route, args.max_points)
    cells = (
        [parse_semantic_cell(raw) for raw in args.semantic_cell]
        if args.semantic_cell
        else default_semantic_cells(route)
    )
    local = local_path(display_route, cells)
    snapshot = {
        "schema_version": 1,
        "map_id": args.map_id or route_path.stem,
        "frame": "map",
        "bounds": bounds_for(display_route, local, cells),
        "vehicle_pose": point_only(route_point(route, 0.36)),
        "goal": point_only(route[-1]),
        "global_path": [point_only(point) for point in display_route],
        "local_path": local,
        "semantic_cells": cells,
        "lidar_returns": lidar_returns(display_route, cells),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(snapshot, indent=2) + "\n")
    print(f"wrote {out_path} from {route_path} ({len(display_route)} path points)")


if __name__ == "__main__":
    main()
