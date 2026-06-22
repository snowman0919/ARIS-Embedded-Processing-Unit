#!/usr/bin/env python3
"""Export ARIS dev-env map/route artifacts into the Flutter tablet GUI snapshot.

Inputs:
- V1/V3 route CSV with x,y,yaw,v_target columns.
- V3 SemanticHDMap snapshot JSON from aris_mapping.semantic_map.SemanticHDMap.

Output schema is intentionally compact for Flutter assets and future HTTP bridge responses:
map_id, frame, bounds, vehicle_pose, goal, global_path, local_path,
semantic_cells, lidar_returns.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

Point = dict[str, float]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--route", help="Route CSV with x,y,yaw,v_target columns.")
    source.add_argument("--semantic-map-snapshot", help="SemanticHDMap snapshot JSON.")
    parser.add_argument("--out", required=True, help="Flutter GUI snapshot JSON path to write.")
    parser.add_argument("--map-id", default="", help="Override map id in the output snapshot.")
    parser.add_argument("--max-points", type=int, default=120, help="Maximum path points to emit.")
    return parser.parse_args()


def load_route_csv(path: Path) -> list[Point]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = [column for column in ("x", "y", "yaw", "v_target") if column not in (reader.fieldnames or [])]
        if missing:
            raise SystemExit(f"route file missing required columns: {', '.join(missing)}")
        route: list[Point] = []
        for line_number, row in enumerate(reader, start=2):
            try:
                route.append({"x": float(row["x"]), "y": float(row["y"])})
            except (TypeError, ValueError) as exc:
                raise SystemExit(f"invalid route row at line {line_number}: {row}") from exc
    if len(route) < 2:
        raise SystemExit(f"route file needs at least two waypoints: {path}")
    return route


def load_semantic_snapshot(path: Path) -> tuple[str, list[Point], list[dict[str, Any]]]:
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(snapshot, dict) or snapshot.get("schema_version") != 1:
        raise SystemExit(f"unsupported semantic map snapshot: {path}")

    nodes: dict[str, Point] = {}
    for item in snapshot.get("route_nodes", []):
        node_id = str(item["node_id"])
        nodes[node_id] = {"x": float(item["x"]), "y": float(item["y"])}

    def node_key(node_id: str) -> tuple[int, str]:
        suffix = node_id.rsplit("_", 1)[-1]
        return (int(suffix), node_id) if suffix.isdigit() else (10**9, node_id)

    route = [nodes[node_id] for node_id in sorted(nodes, key=node_key)]
    if len(route) < 2:
        raise SystemExit(f"semantic map snapshot has too few route nodes: {path}")

    resolution = float(snapshot.get("resolution_m", 0.2))
    cells: list[dict[str, Any]] = []
    for item in snapshot.get("cells", []):
        labels = item.get("labels") or {}
        if not labels:
            continue
        cell = item.get("cell") or [0, 0]
        label, confidence = max(labels.items(), key=lambda kv: float(kv[1]))
        cells.append(
            {
                "x": round(float(cell[0]) * resolution, 3),
                "y": round(float(cell[1]) * resolution, 3),
                "label": str(label),
                "confidence": round(float(confidence), 3),
                "traversability": round(float(item.get("traversability", 0.0)), 3),
            }
        )
    if not cells:
        cells = default_semantic_cells(route)

    return str(snapshot.get("map_id") or path.stem), route, cells


def downsample(points: list[Point], max_points: int) -> list[Point]:
    if len(points) <= max_points:
        return points
    stride = max(1, math.ceil(len(points) / max_points))
    sampled = points[::stride]
    if sampled[-1] != points[-1]:
        sampled.append(points[-1])
    return sampled


def route_point(route: list[Point], fraction: float) -> Point:
    index = round((len(route) - 1) * fraction)
    return route[max(0, min(index, len(route) - 1))]


def default_semantic_cells(route: list[Point]) -> list[dict[str, Any]]:
    one_third = route_point(route, 0.30)
    middle = route_point(route, 0.52)
    late = route_point(route, 0.74)
    return [
        {"x": round(middle["x"], 3), "y": round(middle["y"], 3), "label": "debris", "confidence": 0.93, "traversability": 0.94},
        {"x": round(one_third["x"], 3), "y": round(one_third["y"] - 1.15, 3), "label": "grass", "confidence": 0.74, "traversability": 0.34},
        {"x": round(late["x"], 3), "y": round(late["y"] + 1.18, 3), "label": "obstacle", "confidence": 0.87, "traversability": 0.98},
    ]


def local_path(route: list[Point], cells: list[dict[str, Any]]) -> list[Point]:
    blockers = [cell for cell in cells if float(cell.get("traversability", 0.0)) >= 0.8]
    plan: list[Point] = []
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


def lidar_returns(route: list[Point], cells: list[dict[str, Any]]) -> list[Point]:
    hits: list[Point] = [
        {"x": round(float(cell["x"]), 3), "y": round(float(cell["y"]), 3), "intensity": round(80.0 + float(cell.get("confidence", 0.5)) * 70.0, 1)}
        for cell in cells[:8]
    ]
    for fraction, side in ((0.65, -1.6), (0.82, 1.9), (0.92, -1.2)):
        point = route_point(route, fraction)
        hits.append({"x": round(point["x"], 3), "y": round(point["y"] + side, 3), "intensity": 68.0})
    return hits


def point_only(point: Point) -> Point:
    return {"x": round(point["x"], 3), "y": round(point["y"], 3)}


def bounds_for(route: list[Point], local: list[Point], cells: list[dict[str, Any]]) -> dict[str, float]:
    xs = [point["x"] for point in route] + [point["x"] for point in local] + [float(cell["x"]) for cell in cells]
    ys = [point["y"] for point in route] + [point["y"] for point in local] + [float(cell["y"]) for cell in cells]
    return {"min_x": round(min(xs) - 0.8, 3), "max_x": round(max(xs) + 0.8, 3), "min_y": round(min(ys) - 1.0, 3), "max_y": round(max(ys) + 1.0, 3)}


def main() -> None:
    args = parse_args()
    if args.route:
        source_path = Path(args.route).expanduser()
        source_map_id = source_path.stem
        route = load_route_csv(source_path)
        cells = default_semantic_cells(route)
    else:
        source_path = Path(args.semantic_map_snapshot).expanduser()
        source_map_id, route, cells = load_semantic_snapshot(source_path)

    display_route = downsample(route, args.max_points)
    local = local_path(display_route, cells)
    snapshot = {
        "schema_version": 1,
        "map_id": args.map_id or source_map_id,
        "frame": "map",
        "bounds": bounds_for(display_route, local, cells),
        "vehicle_pose": point_only(route_point(route, 0.36)),
        "goal": point_only(route[-1]),
        "global_path": [point_only(point) for point in display_route],
        "local_path": local,
        "semantic_cells": cells,
        "lidar_returns": lidar_returns(display_route, cells),
    }
    out_path = Path(args.out).expanduser()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out_path} from {source_path} ({len(display_route)} path points)")


if __name__ == "__main__":
    main()
