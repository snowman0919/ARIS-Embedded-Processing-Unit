"""V3 simulation semantic map ROS wrapper."""

from __future__ import annotations

import json
import math
import struct
from pathlib import Path

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2
from std_msgs.msg import String

from .semantic_map import SemanticHDMap, SemanticObservation, load_route_csv_as_graph


class SemanticMapNode(Node):
    def __init__(self) -> None:
        super().__init__("aris_semantic_map")
        self.declare_parameter("resolution_m", 0.5)
        self.declare_parameter("change_threshold", 0.65)
        self.declare_parameter("confirmation_threshold", 0.75)
        self.declare_parameter("max_cloud_points", 200)
        self.declare_parameter("snapshot_file", "")
        self.declare_parameter("route_file", "")
        self.snapshot_file = str(self.get_parameter("snapshot_file").value).strip()
        self.route_file = str(self.get_parameter("route_file").value).strip()
        if self.snapshot_file and Path(self.snapshot_file).exists():
            self.map = SemanticHDMap.load_snapshot(self.snapshot_file)
            self.get_logger().info(f"Loaded semantic map snapshot from {self.snapshot_file}")
        else:
            self.map = SemanticHDMap(
                resolution_m=float(self.get_parameter("resolution_m").value),
                change_threshold=float(self.get_parameter("change_threshold").value),
                confirmation_threshold=float(self.get_parameter("confirmation_threshold").value),
            )
        if self.route_file:
            loaded_nodes, loaded_edges = load_route_csv_as_graph(self.map, Path(self.route_file))
            self.get_logger().info(
                f"Loaded route graph from {self.route_file}: nodes={loaded_nodes} edges={loaded_edges}"
            )
        self.max_cloud_points = int(self.get_parameter("max_cloud_points").value)
        self.semantic_updates = 0
        self.change_events = 0
        self.review_events = 0

        self.summary_pub = self.create_publisher(String, "/aris/mapping/semantic_map", 10)
        self.create_subscription(PointCloud2, "/scan_cloud", self._on_cloud, 10)
        self.create_subscription(String, "/aris/perception/semantic_observation", self._on_observation, 20)
        self.create_timer(0.5, self._publish_summary)
        self.get_logger().info("V3 simulation semantic map node up")

    def _on_cloud(self, msg: PointCloud2) -> None:
        for x, y, _ in _read_xyz_sampled(msg, self.max_cloud_points):
            if math.isfinite(x) and math.isfinite(y):
                self.map.mark_occupied(float(x), float(y), 0.75)

    def _on_observation(self, msg: String) -> None:
        try:
            data = json.loads(msg.data)
            observation = SemanticObservation(
                x=float(data["x"]),
                y=float(data["y"]),
                label=str(data["label"]),
                confidence=float(data["confidence"]),
                source=str(data.get("source", "unknown")),
            )
            decision = self.map.apply_semantic_observation(observation)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self.get_logger().warn(f"Ignoring invalid semantic observation: {exc}")
            return

        if decision.applied:
            self.semantic_updates += 1
        if decision.change_detected:
            self.change_events += 1
        if decision.review_required:
            self.review_events += 1

    def _publish_summary(self) -> None:
        label_counts: dict[str, int] = {}
        blocked_cells = 0
        for state in self.map.cells.values():
            for label in state.labels:
                label_counts[label] = label_counts.get(label, 0) + 1
            if state.traversability >= 0.8:
                blocked_cells += 1

        msg = String()
        msg.data = json.dumps(
            {
                "metric_cells": len(self.map.metric_cells),
                "semantic_cells": sum(1 for state in self.map.cells.values() if state.labels),
                "semantic_updates": self.semantic_updates,
                "change_events": self.change_events,
                "review_events": self.review_events,
                "review_queue": len(self.map.review_queue),
                "blocked_cells": blocked_cells,
                "route_nodes": len(self.map.route_nodes),
                "route_edges": len(self.map.route_edges),
                "labels": label_counts,
            },
            sort_keys=True,
        )
        self.summary_pub.publish(msg)
        if self.snapshot_file:
            self.map.save_snapshot(self.snapshot_file, map_id="aris-v3-sim")


def _read_xyz_sampled(msg: PointCloud2, max_points: int) -> list[tuple[float, float, float]]:
    offsets = {field.name: field.offset for field in msg.fields}
    if not {"x", "y", "z"}.issubset(offsets) or msg.point_step <= 0:
        return []
    total_points = len(msg.data) // msg.point_step
    if total_points <= 0:
        return []
    step = max(1, total_points // max(max_points, 1))
    endian = ">" if msg.is_bigendian else "<"
    points: list[tuple[float, float, float]] = []
    for index in range(0, total_points, step):
        offset = index * msg.point_step
        x = struct.unpack_from(endian + "f", msg.data, offset + offsets["x"])[0]
        y = struct.unpack_from(endian + "f", msg.data, offset + offsets["y"])[0]
        z = struct.unpack_from(endian + "f", msg.data, offset + offsets["z"])[0]
        points.append((x, y, z))
        if len(points) >= max_points:
            break
    return points


def main() -> None:
    rclpy.init()
    node = SemanticMapNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
