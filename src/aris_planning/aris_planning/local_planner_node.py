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
from std_msgs.msg import Bool, String

from .cmd_drive import local_plan_to_ackermann
from .dynamic_obstacle_advisory import (
    DynamicObstacleAdvisory,
    apply_dynamic_obstacle_advisory,
    parse_dynamic_obstacle_advisory,
)
from .pure_pursuit import Pose2D, PurePursuit
from .route import load_route_csv, path_xy, resolve_route_file


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
        self.declare_parameter("dynamic_obstacle_timeout_s", 0.6)
        self.declare_parameter("dynamic_obstacle_slow_speed_mps", 0.4)
        self.declare_parameter("route_file", "")
        self.planner = PurePursuit(
            wheelbase_m=float(self.get_parameter("wheelbase_m").value),
            lookahead_m=float(self.get_parameter("lookahead_m").value),
            max_speed_mps=float(self.get_parameter("max_speed_mps").value),
        )
        self.goal_tolerance_m = float(self.get_parameter("goal_tolerance_m").value)
        self.dynamic_obstacle_timeout_s = float(
            self.get_parameter("dynamic_obstacle_timeout_s").value
        )
        self.dynamic_obstacle_slow_speed_mps = float(
            self.get_parameter("dynamic_obstacle_slow_speed_mps").value
        )
        self.estop = False
        self.dynamic_obstacle: DynamicObstacleAdvisory | None = None
        self.dynamic_obstacle_time_s: float | None = None
        route_file = str(self.get_parameter("route_file").value)
        if route_file.strip():
            route_path = resolve_route_file(route_file)
            route = load_route_csv(route_path)
            self.path = path_xy(route)
            self.get_logger().info(
                f"Loaded V1 route with {len(self.path)} waypoints from {route_path}"
            )
        else:
            # Placeholder demo path until V1/V4 feeds a route/global path.
            self.path = [(float(x), 1.2 * math.sin(float(x) / 4.0)) for x in range(2, 31)]
            self.get_logger().info("No route_file set; using placeholder sine demo path.")

        self.cmd_pub = self.create_publisher(AckermannDriveStamped, "/cmd_drive", 10)
        self.path_pub = self.create_publisher(PoseArray, "/aris/planned_path", 10)
        self.create_subscription(Odometry, "/odometry/filtered", self._on_odom, 10)
        self.create_subscription(Bool, "/estop", self._on_estop, 10)
        self.create_subscription(PoseArray, "/global_path", self._on_global_path, 10)
        self.create_subscription(
            String, "/aris/perception/dynamic_obstacle", self._on_dynamic_obstacle, 10
        )
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
        command = apply_dynamic_obstacle_advisory(
            command,
            self._current_dynamic_obstacle_advisory(),
            slow_speed_mps=self.dynamic_obstacle_slow_speed_mps,
        )
        fields = local_plan_to_ackermann(command)

        out = AckermannDriveStamped()
        out.header.stamp = self.get_clock().now().to_msg()
        out.header.frame_id = "base_link"
        out.drive.steering_angle = float(fields.steering_angle_rad)
        out.drive.speed = float(fields.speed_mps)
        out.drive.acceleration = float(fields.acceleration_mps2)
        self.cmd_pub.publish(out)

    def _on_global_path(self, msg: PoseArray) -> None:
        if len(msg.poses) < 2:
            return
        self.path = [(float(pose.position.x), float(pose.position.y)) for pose in msg.poses]

    def _on_dynamic_obstacle(self, msg: String) -> None:
        try:
            self.dynamic_obstacle = parse_dynamic_obstacle_advisory(msg.data)
            self.dynamic_obstacle_time_s = self.get_clock().now().nanoseconds / 1e9
        except (ValueError, TypeError) as exc:
            self.get_logger().warn(f"Ignoring malformed dynamic-obstacle advisory: {exc}")

    def _near_goal(self, pose: Pose2D) -> bool:
        goal_x, goal_y = self.path[-1]
        return math.hypot(goal_x - pose.x, goal_y - pose.y) < self.goal_tolerance_m

    def _current_dynamic_obstacle_advisory(self) -> DynamicObstacleAdvisory | None:
        if self.dynamic_obstacle is None or self.dynamic_obstacle_time_s is None:
            return None
        age_s = self.get_clock().now().nanoseconds / 1e9 - self.dynamic_obstacle_time_s
        if age_s > self.dynamic_obstacle_timeout_s:
            return None
        return self.dynamic_obstacle

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
