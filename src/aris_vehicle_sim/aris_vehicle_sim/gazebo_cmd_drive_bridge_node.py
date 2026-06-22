"""Bridge the ARIS drive contract to Gazebo Ackermann steering.

The rest of the stack must keep publishing `/cmd_drive`. Gazebo's built-in
Ackermann system consumes `geometry_msgs/Twist` through `ros_gz_bridge`, so this
node is a simulation-only adapter at the HAL boundary.
"""

from __future__ import annotations

import rclpy
from ackermann_msgs.msg import AckermannDriveStamped
from geometry_msgs.msg import Twist
from rclpy.duration import Duration
from rclpy.node import Node

from .gazebo_cmd_drive_bridge import cmd_drive_to_twist_values


def cmd_drive_to_twist(
    speed_mps: float,
    steering_rad: float,
    wheelbase_m: float,
    max_speed_mps: float,
    max_steer_rad: float,
) -> Twist:
    speed, yaw_rate = cmd_drive_to_twist_values(
        speed_mps,
        steering_rad,
        wheelbase_m,
        max_speed_mps,
        max_steer_rad,
    )
    msg = Twist()
    msg.linear.x = speed
    msg.angular.z = yaw_rate
    return msg


class GazeboCmdDriveBridgeNode(Node):
    def __init__(self) -> None:
        super().__init__("aris_gazebo_cmd_drive_bridge")
        self.declare_parameter("wheelbase_m", 1.25)
        self.declare_parameter("max_speed_mps", 2.0)
        self.declare_parameter("max_steer_rad", 0.6)
        self.declare_parameter("command_timeout_s", 0.5)
        self.declare_parameter("input_topic", "/cmd_drive")
        self.declare_parameter("output_topic", "/aris/gazebo/cmd_vel")

        self.wheelbase_m = float(self.get_parameter("wheelbase_m").value)
        self.max_speed_mps = float(self.get_parameter("max_speed_mps").value)
        self.max_steer_rad = float(self.get_parameter("max_steer_rad").value)
        self.command_timeout = Duration(
            seconds=float(self.get_parameter("command_timeout_s").value)
        )
        input_topic = str(self.get_parameter("input_topic").value)
        output_topic = str(self.get_parameter("output_topic").value)

        self.latest_twist = Twist()
        self.last_command_time = None
        self.pub = self.create_publisher(Twist, output_topic, 10)
        self.create_subscription(AckermannDriveStamped, input_topic, self._on_cmd_drive, 10)
        self.create_timer(0.02, self._tick)

    def _on_cmd_drive(self, msg: AckermannDriveStamped) -> None:
        self.latest_twist = cmd_drive_to_twist(
            msg.drive.speed,
            msg.drive.steering_angle,
            self.wheelbase_m,
            self.max_speed_mps,
            self.max_steer_rad,
        )
        self.last_command_time = self.get_clock().now()

    def _tick(self) -> None:
        if self.last_command_time is None:
            self.pub.publish(Twist())
            return

        if self.get_clock().now() - self.last_command_time > self.command_timeout:
            self.pub.publish(Twist())
            return

        self.pub.publish(self.latest_twist)


def main() -> None:
    rclpy.init()
    node = GazeboCmdDriveBridgeNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
