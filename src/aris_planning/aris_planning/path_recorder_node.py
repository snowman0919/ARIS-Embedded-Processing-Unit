"""V1 teach-mode route recorder.

Subscribes to /odometry/filtered and appends a waypoint every configured
distance to a CSV route under ARIS_DATA/routes by default. This is a thin ROS
wrapper; route CSV semantics live in aris_planning.route.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import rclpy
from geometry_msgs.msg import Pose, PoseArray
from nav_msgs.msg import Odometry
from rclpy.node import Node

from .route import ROUTE_COLUMNS, resolve_route_file


def yaw_from_odom(msg: Odometry) -> float:
    q = msg.pose.pose.orientation
    siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
    cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
    return math.atan2(siny_cosp, cosy_cosp)


class PathRecorderNode(Node):
    def __init__(self) -> None:
        super().__init__("aris_path_recorder")
        self.declare_parameter("route_file", "")
        self.declare_parameter("waypoint_spacing_m", 0.2)
        self.declare_parameter("v_target_mps", 1.0)

        self.route_file = resolve_route_file(str(self.get_parameter("route_file").value))
        self.spacing_m = float(self.get_parameter("waypoint_spacing_m").value)
        self.v_target_mps = float(self.get_parameter("v_target_mps").value)
        self.last_xy: tuple[float, float] | None = None
        self.count = 0
        self.recorded_points: list[tuple[float, float]] = []

        self._prepare_route_file(self.route_file)
        self.path_pub = self.create_publisher(PoseArray, "/aris/recorded_path", 10)
        self.create_subscription(Odometry, "/odometry/filtered", self._on_odom, 20)
        self.create_timer(0.5, self._publish_recorded_path)
        self.get_logger().info(
            f"Recording /odometry/filtered to {self.route_file} every {self.spacing_m:.2f} m"
        )

    def _prepare_route_file(self, route_file: Path) -> None:
        route_file.parent.mkdir(parents=True, exist_ok=True)
        if route_file.exists() and route_file.stat().st_size > 0:
            return
        with route_file.open("a", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=ROUTE_COLUMNS)
            writer.writeheader()

    def _on_odom(self, msg: Odometry) -> None:
        x = float(msg.pose.pose.position.x)
        y = float(msg.pose.pose.position.y)
        if (
            self.last_xy is not None
            and math.hypot(x - self.last_xy[0], y - self.last_xy[1]) < self.spacing_m
        ):
            return

        yaw = yaw_from_odom(msg)
        with self.route_file.open("a", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=ROUTE_COLUMNS)
            writer.writerow(
                {
                    "x": f"{x:.6f}",
                    "y": f"{y:.6f}",
                    "yaw": f"{yaw:.6f}",
                    "v_target": f"{self.v_target_mps:.6f}",
                }
            )

        self.last_xy = (x, y)
        self.recorded_points.append((x, y))
        self.count += 1
        if self.count == 1 or self.count % 25 == 0:
            self.get_logger().info(f"Recorded {self.count} waypoints to {self.route_file}")

    def _publish_recorded_path(self) -> None:
        path = PoseArray()
        path.header.frame_id = "map"
        path.header.stamp = self.get_clock().now().to_msg()
        for x, y in self.recorded_points:
            pose = Pose()
            pose.position.x = x
            pose.position.y = y
            path.poses.append(pose)
        self.path_pub.publish(path)


def main() -> None:
    rclpy.init()
    node = PathRecorderNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
