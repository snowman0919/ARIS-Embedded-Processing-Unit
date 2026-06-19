"""Simulation HAL.

Stands in for the real vehicle behind the interface contract: it consumes
/cmd_drive (the same topic the STM32 bridge consumes) and produces odometry plus
the odom->base_link transform exactly as wheel odometry would on the car. The
vehicle dynamics live in the ROS-free KinematicBicycleModel core.

/odometry/filtered is published here only as a V1 stand-in for the fused pose;
aris_localization (V2, EKF + NDT) takes ownership of it and the map->odom TF
later, at which point this node keeps publishing just /wheel_odom and sensors.
"""

from __future__ import annotations

import math

import rclpy
from ackermann_msgs.msg import AckermannDriveStamped
from geometry_msgs.msg import Quaternion, TransformStamped
from nav_msgs.msg import Odometry
from rclpy.duration import Duration
from rclpy.node import Node
from std_msgs.msg import Bool
from tf2_ros import TransformBroadcaster

from .kinematic_bicycle import KinematicBicycleModel, VehicleState


def yaw_to_quaternion(yaw: float) -> Quaternion:
    q = Quaternion()
    q.z = math.sin(yaw / 2.0)
    q.w = math.cos(yaw / 2.0)
    return q


class VehicleSimNode(Node):
    def __init__(self) -> None:
        super().__init__("aris_vehicle_sim")
        self.declare_parameter("wheelbase_m", 1.25)
        self.declare_parameter("max_steer_rad", 0.6)
        self.declare_parameter("command_timeout_s", 0.5)
        self.wheelbase_m = float(self.get_parameter("wheelbase_m").value)
        self.max_steer = float(self.get_parameter("max_steer_rad").value)
        self.command_timeout = Duration(
            seconds=float(self.get_parameter("command_timeout_s").value)
        )

        self.model = KinematicBicycleModel(wheelbase_m=self.wheelbase_m)
        self.state = VehicleState()
        self.estop = False
        self.target_velocity = 0.0
        self.target_steering = 0.0
        self.last_command_time = None
        self.last_time = self.get_clock().now()

        self.wheel_odom_pub = self.create_publisher(Odometry, "/wheel_odom", 10)
        self.filtered_pub = self.create_publisher(Odometry, "/odometry/filtered", 10)
        self.tf_broadcaster = TransformBroadcaster(self)
        self.create_subscription(AckermannDriveStamped, "/cmd_drive", self._on_cmd_drive, 10)
        self.create_subscription(Bool, "/estop", self._on_estop, 10)
        self.create_timer(0.02, self._tick)

    def _on_estop(self, msg: Bool) -> None:
        self.estop = bool(msg.data)

    def _on_cmd_drive(self, msg: AckermannDriveStamped) -> None:
        self.target_velocity = max(0.0, float(msg.drive.speed))
        self.target_steering = max(
            -self.max_steer, min(self.max_steer, float(msg.drive.steering_angle))
        )
        self.last_command_time = self.get_clock().now()

    def _tick(self) -> None:
        now = self.get_clock().now()
        dt = max((now - self.last_time).nanoseconds / 1e9, 1e-3)
        self.last_time = now
        velocity, steering = self._active_command(now)
        self.model.step(self.state, velocity, steering, dt)
        self._publish(now)

    def _active_command(self, now) -> tuple[float, float]:
        if self.estop:
            return 0.0, 0.0
        fresh = (
            self.last_command_time is not None
            and now - self.last_command_time < self.command_timeout
        )
        if not fresh:
            # No fresh command: coast to a stop while holding the wheel.
            return 0.0, self.state.steering_rad
        return self.target_velocity, self.target_steering

    def _publish(self, now) -> None:
        stamp = now.to_msg()
        orientation = yaw_to_quaternion(self.state.yaw)
        yaw_rate = (
            self.state.velocity_mps / self.wheelbase_m * math.tan(self.state.steering_rad)
        )

        odom = Odometry()
        odom.header.stamp = stamp
        odom.header.frame_id = "odom"
        odom.child_frame_id = "base_link"
        odom.pose.pose.position.x = self.state.x
        odom.pose.pose.position.y = self.state.y
        odom.pose.pose.orientation = orientation
        odom.twist.twist.linear.x = self.state.velocity_mps
        odom.twist.twist.angular.z = yaw_rate
        self.wheel_odom_pub.publish(odom)

        tf = TransformStamped()
        tf.header.stamp = stamp
        tf.header.frame_id = "odom"
        tf.child_frame_id = "base_link"
        tf.transform.translation.x = self.state.x
        tf.transform.translation.y = self.state.y
        tf.transform.rotation = orientation
        self.tf_broadcaster.sendTransform(tf)

        # V1 placeholder for the EKF output (see module docstring).
        filtered = Odometry()
        filtered.header.stamp = stamp
        filtered.header.frame_id = "map"
        filtered.child_frame_id = "base_link"
        filtered.pose.pose = odom.pose.pose
        filtered.twist.twist = odom.twist.twist
        self.filtered_pub.publish(filtered)


def main() -> None:
    rclpy.init()
    node = VehicleSimNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
