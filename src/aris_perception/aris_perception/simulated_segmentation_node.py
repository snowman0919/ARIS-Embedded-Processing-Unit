"""Simulation-only V3 semantic observation source.

This node does not use a real model. It emits deterministic semantic
observations so the V3 map update path can be verified without camera assets.
"""

from __future__ import annotations

import json
import math

from nav_msgs.msg import Odometry
import rclpy
from rclpy.node import Node
from std_msgs.msg import String


def yaw_from_odom(msg: Odometry) -> float:
    q = msg.pose.pose.orientation
    siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
    cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
    return math.atan2(siny_cosp, cosy_cosp)


class SimulatedSegmentationNode(Node):
    def __init__(self) -> None:
        super().__init__("aris_simulated_segmentation")
        self.declare_parameter("target_x_m", 6.0)
        self.declare_parameter("target_y_m", 0.0)
        self.declare_parameter("change_after_x_m", 3.0)
        self.declare_parameter("publish_hz", 5.0)
        self.target_x = float(self.get_parameter("target_x_m").value)
        self.target_y = float(self.get_parameter("target_y_m").value)
        self.change_after_x = float(self.get_parameter("change_after_x_m").value)
        publish_hz = float(self.get_parameter("publish_hz").value)
        self.pose: tuple[float, float, float] | None = None
        self.pub = self.create_publisher(String, "/aris/perception/semantic_observation", 10)
        self.create_subscription(Odometry, "/odometry/filtered", self._on_odom, 20)
        self.create_timer(1.0 / max(publish_hz, 1e-6), self._publish_observation)
        self.get_logger().info("V3 simulated segmentation node up (no real camera/model)")

    def _on_odom(self, msg: Odometry) -> None:
        self.pose = (
            float(msg.pose.pose.position.x),
            float(msg.pose.pose.position.y),
            yaw_from_odom(msg),
        )

    def _publish_observation(self) -> None:
        if self.pose is None:
            return
        x, _, _ = self.pose
        label = "debris" if x >= self.change_after_x else "road"
        confidence = 0.88 if label == "debris" else 0.92
        msg = String()
        msg.data = json.dumps(
            {
                "x": self.target_x,
                "y": self.target_y,
                "label": label,
                "confidence": confidence,
                "source": "simulated_segmentation",
            },
            sort_keys=True,
        )
        self.pub.publish(msg)


def main() -> None:
    rclpy.init()
    node = SimulatedSegmentationNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
