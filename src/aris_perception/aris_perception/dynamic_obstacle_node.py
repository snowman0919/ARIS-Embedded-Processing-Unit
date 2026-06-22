"""Publish V5 dynamic-obstacle advisories from /scan_cloud."""

from __future__ import annotations

import json
import struct
from typing import Callable, Iterable

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2, PointField
from std_msgs.msg import String

from .dynamic_obstacles import (
    DynamicObstacleConfig,
    DynamicObstacleTracker,
    PointXYZ,
    evaluate_dynamic_obstacle,
    obstacle_observation,
    with_track,
)


Reader = Callable[[bytes, int], float]


def _reader_for(field: PointField) -> Reader:
    if field.datatype == PointField.FLOAT32:
        return lambda data, offset: float(struct.unpack_from("<f", data, offset)[0])
    if field.datatype == PointField.FLOAT64:
        return lambda data, offset: float(struct.unpack_from("<d", data, offset)[0])
    if field.datatype == PointField.UINT16:
        return lambda data, offset: float(struct.unpack_from("<H", data, offset)[0])
    if field.datatype == PointField.UINT32:
        return lambda data, offset: float(struct.unpack_from("<I", data, offset)[0])
    if field.datatype == PointField.INT32:
        return lambda data, offset: float(struct.unpack_from("<i", data, offset)[0])
    if field.datatype == PointField.UINT8:
        return lambda data, offset: float(struct.unpack_from("<B", data, offset)[0])
    raise ValueError(f"unsupported PointField datatype for {field.name}: {field.datatype}")


def cloud_points(msg: PointCloud2, *, sample_stride: int = 1) -> Iterable[PointXYZ]:
    if msg.is_bigendian:
        raise ValueError("big-endian PointCloud2 is not supported")
    fields = {field.name: field for field in msg.fields}
    missing = [name for name in ("x", "y", "z") if name not in fields]
    if missing:
        raise ValueError(f"missing required point fields: {', '.join(missing)}")
    readers = {name: _reader_for(fields[name]) for name in ("x", "y", "z")}
    data = bytes(msg.data)
    width = int(msg.width)
    height = int(msg.height)
    stride = max(int(sample_stride), 1)
    for row in range(height):
        row_offset = row * int(msg.row_step)
        for col in range(0, width, stride):
            point_offset = row_offset + col * int(msg.point_step)
            yield PointXYZ(
                x=readers["x"](data, point_offset + fields["x"].offset),
                y=readers["y"](data, point_offset + fields["y"].offset),
                z=readers["z"](data, point_offset + fields["z"].offset),
            )


class DynamicObstacleNode(Node):
    def __init__(self) -> None:
        super().__init__("aris_dynamic_obstacle_detector")
        self.declare_parameter("input_topic", "/scan_cloud")
        self.declare_parameter("output_topic", "/aris/perception/dynamic_obstacle")
        self.declare_parameter("corridor_half_width_m", 0.8)
        self.declare_parameter("slow_distance_m", 4.0)
        self.declare_parameter("stop_distance_m", 1.4)
        self.declare_parameter("min_points", 3)
        self.declare_parameter("closing_stop_mps", 1.2)
        self.declare_parameter("detour_lateral_m", 1.0)
        self.declare_parameter("detour_forward_m", 2.0)
        self.declare_parameter("sample_stride", 2)

        self.config = DynamicObstacleConfig(
            corridor_half_width_m=float(self.get_parameter("corridor_half_width_m").value),
            slow_distance_m=float(self.get_parameter("slow_distance_m").value),
            stop_distance_m=float(self.get_parameter("stop_distance_m").value),
            min_points=int(self.get_parameter("min_points").value),
            closing_stop_mps=float(self.get_parameter("closing_stop_mps").value),
            detour_lateral_m=float(self.get_parameter("detour_lateral_m").value),
            detour_forward_m=float(self.get_parameter("detour_forward_m").value),
        )
        self.sample_stride = int(self.get_parameter("sample_stride").value)
        self.previous_closest_m: float | None = None
        self.previous_stamp_s: float | None = None
        self.tracker = DynamicObstacleTracker(self.config)

        input_topic = str(self.get_parameter("input_topic").value)
        output_topic = str(self.get_parameter("output_topic").value)
        self.pub = self.create_publisher(String, output_topic, 10)
        self.create_subscription(PointCloud2, input_topic, self._on_cloud, 10)
        self.get_logger().info(
            f"V5 dynamic obstacle detector up: {input_topic} -> {output_topic}"
        )

    def _on_cloud(self, msg: PointCloud2) -> None:
        stamp_s = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        dt_s = (
            stamp_s - self.previous_stamp_s
            if self.previous_stamp_s is not None and stamp_s > 0.0
            else None
        )
        try:
            points = list(cloud_points(msg, sample_stride=self.sample_stride))
            decision = evaluate_dynamic_obstacle(
                points,
                config=self.config,
                previous_closest_m=self.previous_closest_m,
                dt_s=dt_s,
            )
            track = self.tracker.update(
                obstacle_observation(points, config=self.config),
                timestamp_s=stamp_s if stamp_s > 0.0 else self.get_clock().now().nanoseconds / 1e9,
            )
            decision = with_track(decision, track)
        except ValueError as exc:
            self.get_logger().warn(f"discarding cloud for dynamic obstacle detection: {exc}")
            return

        if decision.closest_distance_m is not None:
            self.previous_closest_m = decision.closest_distance_m
            self.previous_stamp_s = stamp_s if stamp_s > 0.0 else self.get_clock().now().nanoseconds / 1e9

        out = String()
        out.data = json.dumps(decision.as_dict(), sort_keys=True)
        self.pub.publish(out)


def main() -> None:
    rclpy.init()
    node = DynamicObstacleNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
