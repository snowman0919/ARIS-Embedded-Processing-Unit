"""Normalize Gazebo GPU LiDAR point clouds to the ARIS /scan_cloud contract."""

from __future__ import annotations

import math
import struct
from typing import Callable

from rclpy.node import Node
import rclpy
from sensor_msgs.msg import PointCloud2, PointField


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


def normalize_cloud(
    source: PointCloud2,
    *,
    target_frame: str,
    scan_period_s: float,
) -> PointCloud2:
    if source.is_bigendian:
        raise ValueError("big-endian PointCloud2 is not supported")

    fields = {field.name: field for field in source.fields}
    missing = [name for name in ("x", "y", "z") if name not in fields]
    if missing:
        raise ValueError(f"missing required point fields: {', '.join(missing)}")

    readers = {name: _reader_for(field) for name, field in fields.items()}
    point_count = int(source.width) * int(source.height)
    if point_count <= 0:
        raise ValueError("empty PointCloud2")

    output = PointCloud2()
    output.header = source.header
    output.header.frame_id = target_frame
    output.height = 1
    output.width = point_count
    output.is_bigendian = False
    output.is_dense = source.is_dense
    output.fields = [
        PointField(name="x", offset=0, datatype=PointField.FLOAT32, count=1),
        PointField(name="y", offset=4, datatype=PointField.FLOAT32, count=1),
        PointField(name="z", offset=8, datatype=PointField.FLOAT32, count=1),
        PointField(name="intensity", offset=12, datatype=PointField.FLOAT32, count=1),
        PointField(name="ring", offset=16, datatype=PointField.UINT16, count=1),
        PointField(name="time", offset=20, datatype=PointField.FLOAT32, count=1),
    ]
    output.point_step = 24
    output.row_step = output.width * output.point_step

    data = bytearray(output.row_step)
    source_bytes = bytes(source.data)
    columns = max(int(source.width), 1)
    rows = max(int(source.height), 1)
    max_col = max(columns - 1, 1)

    for row in range(rows):
        for col in range(columns):
            index = row * columns + col
            src_offset = row * int(source.row_step) + col * int(source.point_step)
            dst_offset = index * output.point_step

            x = readers["x"](source_bytes, src_offset + fields["x"].offset)
            y = readers["y"](source_bytes, src_offset + fields["y"].offset)
            z = readers["z"](source_bytes, src_offset + fields["z"].offset)
            intensity = (
                readers["intensity"](source_bytes, src_offset + fields["intensity"].offset)
                if "intensity" in fields
                else 0.0
            )
            ring = (
                int(readers["ring"](source_bytes, src_offset + fields["ring"].offset))
                if "ring" in fields
                else row
            )
            rel_time = (
                readers["time"](source_bytes, src_offset + fields["time"].offset)
                if "time" in fields
                else float(col) / float(max_col) * scan_period_s
            )

            if not math.isfinite(intensity):
                intensity = 0.0
            if not math.isfinite(rel_time) or rel_time < 0.0:
                rel_time = 0.0
            ring = max(0, min(ring, 65535))
            struct.pack_into(
                "<ffffH2xf",
                data,
                dst_offset,
                float(x),
                float(y),
                float(z),
                float(intensity),
                ring,
                float(rel_time),
            )

    output.data = bytes(data)
    return output


class GazeboCloudAdapterNode(Node):
    def __init__(self) -> None:
        super().__init__("aris_gazebo_cloud_adapter")
        self.declare_parameter("input_topic", "/gazebo/scan_cloud")
        self.declare_parameter("output_topic", "/scan_cloud")
        self.declare_parameter("target_frame", "lidar_link")
        self.declare_parameter("scan_period_s", 0.1)
        self.declare_parameter("stamp_with_receive_time", False)

        input_topic = str(self.get_parameter("input_topic").value)
        output_topic = str(self.get_parameter("output_topic").value)
        self.target_frame = str(self.get_parameter("target_frame").value)
        self.scan_period_s = float(self.get_parameter("scan_period_s").value)
        self.stamp_with_receive_time = bool(
            self.get_parameter("stamp_with_receive_time").value
        )

        self.pub = self.create_publisher(PointCloud2, output_topic, 10)
        self.create_subscription(PointCloud2, input_topic, self._on_cloud, 10)
        self.get_logger().info(
            f"Gazebo cloud adapter up: {input_topic} -> {output_topic} frame={self.target_frame}"
        )

    def _on_cloud(self, msg: PointCloud2) -> None:
        try:
            cloud = normalize_cloud(
                msg,
                target_frame=self.target_frame,
                scan_period_s=self.scan_period_s,
            )
            if self.stamp_with_receive_time:
                cloud.header.stamp = self.get_clock().now().to_msg()
            self.pub.publish(cloud)
        except ValueError as exc:
            self.get_logger().warn(f"discarding Gazebo cloud: {exc}", throttle_duration_sec=5.0)


def main() -> None:
    rclpy.init()
    node = GazeboCloudAdapterNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
