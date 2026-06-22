"""Synchronize a Gazebo entity pose from ROS odometry.

Gazebo Sim exposes entity pose updates as a gz transport service. The ROS image
used by this repository does not ship Python gz transport bindings, so this node
uses the `gz service` CLI as a narrow adapter until a native binding or plugin is
added.
"""

from __future__ import annotations

import math
import shutil
import subprocess

from nav_msgs.msg import Odometry
import rclpy
from rclpy.node import Node

from .gazebo_pose_sync import (
    GazeboPose2D,
    gz_boolean_response_is_true,
    pose_request_text,
    should_send_pose,
)


def yaw_from_odom(msg: Odometry) -> float:
    q = msg.pose.pose.orientation
    siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
    cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
    return math.atan2(siny_cosp, cosy_cosp)


class GazeboPoseSyncNode(Node):
    def __init__(self) -> None:
        super().__init__("aris_gazebo_pose_sync")
        self.declare_parameter("odom_topic", "/wheel_odom")
        self.declare_parameter("world_name", "aris_lidar_smoke")
        self.declare_parameter("entity_name", "aris")
        self.declare_parameter("entity_z_m", 0.0)
        self.declare_parameter("sync_hz", 5.0)
        self.declare_parameter("service_timeout_ms", 500)
        self.declare_parameter("min_translation_delta_m", 0.02)
        self.declare_parameter("min_yaw_delta_rad", 0.01)

        odom_topic = str(self.get_parameter("odom_topic").value)
        world_name = str(self.get_parameter("world_name").value)
        self.entity_name = str(self.get_parameter("entity_name").value)
        self.entity_z_m = float(self.get_parameter("entity_z_m").value)
        self.service_name = f"/world/{world_name}/set_pose"
        self.service_timeout_ms = int(self.get_parameter("service_timeout_ms").value)
        self.min_translation_delta_m = float(
            self.get_parameter("min_translation_delta_m").value
        )
        self.min_yaw_delta_rad = float(self.get_parameter("min_yaw_delta_rad").value)
        self.gz_executable = shutil.which("gz")
        self.latest_odom: Odometry | None = None
        self.last_sent_pose: GazeboPose2D | None = None
        self.in_flight = False

        if self.gz_executable is None:
            self.get_logger().error("Cannot find `gz` executable; Gazebo pose sync disabled")

        self.create_subscription(Odometry, odom_topic, self._on_odom, 20)
        sync_hz = max(float(self.get_parameter("sync_hz").value), 1e-6)
        self.create_timer(1.0 / sync_hz, self._sync_pose)
        self.get_logger().info(
            f"Gazebo pose sync up: {odom_topic} -> {self.service_name}/{self.entity_name}"
        )

    def _on_odom(self, msg: Odometry) -> None:
        self.latest_odom = msg

    def _sync_pose(self) -> None:
        if self.gz_executable is None or self.latest_odom is None or self.in_flight:
            return
        pose = GazeboPose2D(
            x=float(self.latest_odom.pose.pose.position.x),
            y=float(self.latest_odom.pose.pose.position.y),
            yaw=yaw_from_odom(self.latest_odom),
        )
        if not should_send_pose(
            pose,
            self.last_sent_pose,
            min_translation_delta_m=self.min_translation_delta_m,
            min_yaw_delta_rad=self.min_yaw_delta_rad,
        ):
            return

        self.in_flight = True
        try:
            self._call_set_pose(pose)
            self.last_sent_pose = pose
        except (subprocess.SubprocessError, OSError) as exc:
            self.get_logger().warn(f"Gazebo pose sync failed: {exc}", throttle_duration_sec=2.0)
        finally:
            self.in_flight = False

    def _call_set_pose(self, pose: GazeboPose2D) -> None:
        request = pose_request_text(self.entity_name, pose, self.entity_z_m)
        result = subprocess.run(
            [
                self.gz_executable or "gz",
                "service",
                "-s",
                self.service_name,
                "--reqtype",
                "gz.msgs.Pose",
                "--reptype",
                "gz.msgs.Boolean",
                "--timeout",
                str(self.service_timeout_ms),
                "--req",
                request,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=max(self.service_timeout_ms / 1000.0 + 0.5, 1.0),
        )
        if result.returncode != 0 or not gz_boolean_response_is_true(result.stdout):
            detail = (result.stderr or result.stdout or "").strip()
            raise subprocess.SubprocessError(detail or f"gz service exited {result.returncode}")


def main() -> None:
    rclpy.init()
    node = GazeboPoseSyncNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
