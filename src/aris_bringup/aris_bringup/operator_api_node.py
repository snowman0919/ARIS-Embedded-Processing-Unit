"""Minimal operator-facing API bridge."""

from __future__ import annotations

import json

from geometry_msgs.msg import PoseStamped
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from .operator_api import goal_event, parse_goal_request


class OperatorApiNode(Node):
    def __init__(self) -> None:
        super().__init__("aris_operator_api")
        self.goal_pub = self.create_publisher(PoseStamped, "/goal_pose", 10)
        self.event_pub = self.create_publisher(String, "/aris/operator/events", 10)
        self.create_subscription(String, "/aris/operator/goal_request", self._on_goal, 10)
        self.get_logger().info("ARIS operator API up: /aris/operator/goal_request -> /goal_pose")

    def _on_goal(self, msg: String) -> None:
        try:
            goal = parse_goal_request(msg.data)
        except ValueError as exc:
            self._publish_event({"event": "goal_rejected", "reason": str(exc)})
            self.get_logger().warn(f"Rejected operator goal: {exc}")
            return

        out = PoseStamped()
        out.header.stamp = self.get_clock().now().to_msg()
        out.header.frame_id = goal.frame_id
        out.pose.position.x = goal.x
        out.pose.position.y = goal.y
        out.pose.orientation.w = 1.0
        self.goal_pub.publish(out)
        self._publish_event(json.loads(goal_event(goal)))

    def _publish_event(self, payload: dict[str, object]) -> None:
        event = String()
        event.data = json.dumps(payload, sort_keys=True)
        self.event_pub.publish(event)


def main() -> None:
    rclpy.init()
    node = OperatorApiNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
