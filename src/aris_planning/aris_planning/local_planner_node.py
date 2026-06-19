"""Local planner ROS wrapper.

Consumes the fused pose on /odometry/filtered and emits the single control
contract topic /cmd_drive (ackermann_msgs/AckermannDriveStamped). The node knows
nothing about whether a simulator or the real vehicle is downstream -- that is
the HAL's job. All steering geometry lives in the ROS-free PurePursuit core.
"""

from __future__ import annotations

import math

import rclpy
from ackermann_msgs.msg import AckermannDriveStamped
from geometry_msgs.msg import Pose, PoseArray
from nav_msgs.msg import Odometry
from rclpy.node import Node
from std_msgs.msg import Bool

from .cmd_drive import local_plan_to_ackermann
from .pure_pursuit import Pose2D, PurePursuit


def yaw_from_odom(msg: Odometry) -> float:
    q = msg.pose.pose.orientation
    siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
    cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
    return math.atan2(siny_cosp, cosy_cosp)


class LocalPlannerNode(Node):
    def __init__(self) -> None:
        super().__init__("aris_local_planner")
        self.declare_parameter("wheelbase_m", 1.25)
        self.declare_parameter("lookahead_m", 2.0)
        self.declare_parameter("max_speed_mps", 1.8)
        self.declare_parameter("goal_tolerance_m", 0.8)
        self.planner = PurePursuit(
            wheelbase_m=float(self.get_parameter("wheelbase_m").value),
            lookahead_m=float(self.get_parameter("lookahead_m").value),
            max_speed_mps=float(self.get_parameter("max_speed_mps").value),
        )
        self.goal_tolerance_m = float(self.get_parameter("goal_tolerance_m").value)
        self.estop = False
        # Placeholder demo path until V4 feeds /global_path from the global planner.
        self.path = [(float(x), 1.2 * math.sin(float(x) / 4.0)) for x in range(2, 31)]

        self.cmd_pub = self.create_publisher(AckermannDriveStamped, "/cmd_drive", 10)
        self.path_pub = self.create_publisher(PoseArray, "/aris/planned_path", 10)
        self.create_subscription(Odometry, "/odometry/filtered", self._on_odom, 10)
        self.create_subscription(Bool, "/estop", self._on_estop, 10)
        self.create_timer(1.0, self._publish_path)

    def _on_estop(self, msg: Bool) -> None:
        self.estop = bool(msg.data)

    def _on_odom(self, msg: Odometry) -> None:
        pose = Pose2D(
            x=float(msg.pose.pose.position.x),
            y=float(msg.pose.pose.position.y),
            yaw=yaw_from_odom(msg),
        )
        command = self.planner.command(
            pose, self.path, estop=self.estop or self._near_goal(pose)
        )
        fields = local_plan_to_ackermann(command)

        out = AckermannDriveStamped()
        out.header.stamp = self.get_clock().now().to_msg()
        out.header.frame_id = "base_link"
        out.drive.steering_angle = float(fields.steering_angle_rad)
        out.drive.speed = float(fields.speed_mps)
        out.drive.acceleration = float(fields.acceleration_mps2)
        self.cmd_pub.publish(out)

    def _near_goal(self, pose: Pose2D) -> bool:
        goal_x, goal_y = self.path[-1]
        return math.hypot(goal_x - pose.x, goal_y - pose.y) < self.goal_tolerance_m

    def _publish_path(self) -> None:
        path = PoseArray()
        path.header.frame_id = "map"
        path.header.stamp = self.get_clock().now().to_msg()
        for x, y in self.path:
            pose = Pose()
            pose.position.x = x
            pose.position.y = y
            path.poses.append(pose)
        self.path_pub.publish(path)


def main() -> None:
    rclpy.init()
    node = LocalPlannerNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
