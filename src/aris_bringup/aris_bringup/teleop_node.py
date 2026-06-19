"""Teleop bridge: standard Twist on /cmd_vel -> the /cmd_drive contract.

Run the stock `teleop_twist_keyboard` (or a joystick teleop) to publish
geometry_msgs/Twist on /cmd_vel; this node converts it to
ackermann_msgs/AckermannDriveStamped on /cmd_drive. The conversion math lives in
the ROS-free teleop_core. The HAL downstream (sim or STM32) is identical to the
autonomous path -- V0 validates exactly that.
"""

from __future__ import annotations

import rclpy
from ackermann_msgs.msg import AckermannDriveStamped
from geometry_msgs.msg import Twist
from rclpy.node import Node

from .teleop_core import twist_to_ackermann


class TeleopNode(Node):
    def __init__(self) -> None:
        super().__init__("aris_teleop")
        self.declare_parameter("max_steer_rad", 0.6)
        self.declare_parameter("max_speed_mps", 3.0)
        self.declare_parameter("steer_scale", 0.6)
        self.max_steer = float(self.get_parameter("max_steer_rad").value)
        self.max_speed = float(self.get_parameter("max_speed_mps").value)
        self.steer_scale = float(self.get_parameter("steer_scale").value)

        self.cmd_pub = self.create_publisher(AckermannDriveStamped, "/cmd_drive", 10)
        self.create_subscription(Twist, "/cmd_vel", self._on_twist, 10)
        self.get_logger().info(
            "Teleop bridge up: run `ros2 run teleop_twist_keyboard teleop_twist_keyboard` "
            "to drive /cmd_vel -> /cmd_drive."
        )

    def _on_twist(self, msg: Twist) -> None:
        cmd = twist_to_ackermann(
            linear_x=float(msg.linear.x),
            angular_z=float(msg.angular.z),
            max_steer_rad=self.max_steer,
            max_speed_mps=self.max_speed,
            steer_scale=self.steer_scale,
        )
        out = AckermannDriveStamped()
        out.header.stamp = self.get_clock().now().to_msg()
        out.header.frame_id = "base_link"
        out.drive.steering_angle = cmd.steering_angle_rad
        out.drive.speed = cmd.speed_mps
        self.cmd_pub.publish(out)


def main() -> None:
    rclpy.init()
    node = TeleopNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
