"""V4 semantic route-graph global planner ROS wrapper."""

from __future__ import annotations

import json
import math

from geometry_msgs.msg import Pose, PoseArray
from nav_msgs.msg import Odometry
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from aris_mapping.semantic_map import RouteEdge, RouteNode, SemanticHDMap, SemanticObservation

from .local_planner_node import yaw_from_odom
from .route_graph import build_bidirectional_edges, densify_path, nearest_route_node, plan_route_graph


class GlobalPlannerNode(Node):
    def __init__(self) -> None:
        super().__init__("aris_global_planner")
        self.declare_parameter("goal_x_m", 9.0)
        self.declare_parameter("goal_y_m", 0.0)
        self.declare_parameter("semantic_weight", 10.0)
        self.declare_parameter("path_spacing_m", 0.25)
        self.goal_x = float(self.get_parameter("goal_x_m").value)
        self.goal_y = float(self.get_parameter("goal_y_m").value)
        self.semantic_weight = float(self.get_parameter("semantic_weight").value)
        self.path_spacing_m = float(self.get_parameter("path_spacing_m").value)
        self.pose: tuple[float, float, float] | None = None
        self.hd_map = _demo_semantic_route_graph()
        self.goal_node = nearest_route_node(self.hd_map.route_nodes, self.goal_x, self.goal_y)
        self.last_node_path: list[str] = []

        self.path_pub = self.create_publisher(PoseArray, "/global_path", 10)
        self.summary_pub = self.create_publisher(String, "/aris/planning/global_plan", 10)
        self.create_subscription(Odometry, "/odometry/filtered", self._on_odom, 20)
        self.create_timer(0.5, self._publish_plan)
        self.get_logger().info(f"V4 global planner up: goal={self.goal_node}")

    def _on_odom(self, msg: Odometry) -> None:
        self.pose = (
            float(msg.pose.pose.position.x),
            float(msg.pose.pose.position.y),
            yaw_from_odom(msg),
        )

    def _publish_plan(self) -> None:
        if self.pose is None:
            return
        start_node = nearest_route_node(self.hd_map.route_nodes, self.pose[0], self.pose[1])
        try:
            plan = plan_route_graph(
                self.hd_map,
                start_node,
                self.goal_node,
                semantic_weight=self.semantic_weight,
            )
        except ValueError as exc:
            self.get_logger().warn(f"Global planning failed: {exc}")
            return
        dense = densify_path(plan.points, self.path_spacing_m)
        self._publish_pose_array(dense)
        self._publish_summary(plan.node_ids, plan.cost, len(dense))
        self.last_node_path = plan.node_ids

    def _publish_pose_array(self, points: list[tuple[float, float]]) -> None:
        path = PoseArray()
        path.header.stamp = self.get_clock().now().to_msg()
        path.header.frame_id = "map"
        for x, y in points:
            pose = Pose()
            pose.position.x = x
            pose.position.y = y
            path.poses.append(pose)
        self.path_pub.publish(path)

    def _publish_summary(self, node_ids: list[str], cost: float, point_count: int) -> None:
        msg = String()
        msg.data = json.dumps(
            {
                "node_path": node_ids,
                "cost": cost,
                "point_count": point_count,
                "goal_x": self.goal_x,
                "goal_y": self.goal_y,
                "detour": any("detour" in node_id for node_id in node_ids),
            },
            sort_keys=True,
        )
        self.summary_pub.publish(msg)


def _demo_semantic_route_graph() -> SemanticHDMap:
    hd_map = SemanticHDMap(resolution_m=0.5)
    for node in [
        RouteNode("start", 0.0, 0.0),
        RouteNode("approach", 3.0, 0.0),
        RouteNode("blocked", 6.0, 0.0),
        RouteNode("goal", 9.0, 0.0),
        RouteNode("detour_a", 3.0, 1.2),
        RouteNode("detour_b", 6.0, 1.2),
        RouteNode("detour_c", 9.0, 1.2),
    ]:
        hd_map.add_route_node(node)
    for edge in build_bidirectional_edges(
        [
            RouteEdge("start", "approach", 3.0),
            RouteEdge("approach", "blocked", 3.0),
            RouteEdge("blocked", "goal", 3.0),
            RouteEdge("approach", "detour_a", 1.2),
            RouteEdge("detour_a", "detour_b", 3.0),
            RouteEdge("detour_b", "detour_c", 3.0),
            RouteEdge("detour_c", "goal", 1.2),
        ]
    ):
        hd_map.add_route_edge(edge)
    hd_map.apply_semantic_observation(
        SemanticObservation(x=6.0, y=0.0, label="debris", confidence=0.95)
    )
    return hd_map


def main() -> None:
    rclpy.init()
    node = GlobalPlannerNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
