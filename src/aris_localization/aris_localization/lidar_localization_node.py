"""V2A LiDAR localization ROS wrapper.

Subscribes to `/wheel_odom` and `/scan_cloud`, performs known-map scan matching,
publishes localization-owned `/odometry/filtered`, and broadcasts `map->odom`.
"""

from __future__ import annotations

import math
import struct
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import Quaternion, TransformStamped
from nav_msgs.msg import Odometry
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2
from tf2_ros import TransformBroadcaster

from .fusion_gate import CorrectionGateConfig, evaluate_lidar_correction
from .localization_core import Pose2D, map_to_odom_from_base_poses
from .scan_matching import (
    LidarExtrinsic2D,
    ScanMatchConfig,
    load_box_map,
    match_scan_to_map,
)


def yaw_from_odom(msg: Odometry) -> float:
    q = msg.pose.pose.orientation
    siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
    cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
    return math.atan2(siny_cosp, cosy_cosp)


def yaw_to_quaternion(yaw: float) -> Quaternion:
    q = Quaternion()
    q.z = math.sin(yaw / 2.0)
    q.w = math.cos(yaw / 2.0)
    return q


class LidarLocalizationNode(Node):
    def __init__(self) -> None:
        super().__init__("aris_lidar_localization")
        share = Path(get_package_share_directory("aris_vehicle_sim"))
        self.declare_parameter("map_file", str(share / "maps" / "simple_3d_track.yaml"))
        self.declare_parameter("lidar_x_m", 0.6)
        self.declare_parameter("lidar_y_m", 0.0)
        self.declare_parameter("lidar_yaw_rad", 0.0)
        self.declare_parameter("xy_window_m", 0.20)
        self.declare_parameter("xy_step_m", 0.05)
        self.declare_parameter("yaw_window_rad", 0.08)
        self.declare_parameter("yaw_step_rad", 0.02)
        self.declare_parameter("max_points", 240)
        self.declare_parameter("prior_weight", 5.0)
        self.declare_parameter("min_improvement_m", 0.05)
        self.declare_parameter("correction_max_translation_m", 0.50)
        self.declare_parameter("correction_max_yaw_rad", 0.25)
        self.declare_parameter("correction_max_mean_error_m", 0.35)
        self.declare_parameter("correction_min_used_points", 10)

        map_file = str(self.get_parameter("map_file").value)
        self.known_map = load_box_map(map_file)
        self.lidar_extrinsic = LidarExtrinsic2D(
            x=float(self.get_parameter("lidar_x_m").value),
            y=float(self.get_parameter("lidar_y_m").value),
            yaw=float(self.get_parameter("lidar_yaw_rad").value),
        )
        self.match_config = ScanMatchConfig(
            xy_window_m=float(self.get_parameter("xy_window_m").value),
            xy_step_m=float(self.get_parameter("xy_step_m").value),
            yaw_window_rad=float(self.get_parameter("yaw_window_rad").value),
            yaw_step_rad=float(self.get_parameter("yaw_step_rad").value),
            max_points=int(self.get_parameter("max_points").value),
            prior_weight=float(self.get_parameter("prior_weight").value),
            min_improvement_m=float(self.get_parameter("min_improvement_m").value),
        )
        self.gate_config = CorrectionGateConfig(
            max_translation_m=float(self.get_parameter("correction_max_translation_m").value),
            max_yaw_rad=float(self.get_parameter("correction_max_yaw_rad").value),
            max_mean_error_m=float(self.get_parameter("correction_max_mean_error_m").value),
            min_used_points=int(self.get_parameter("correction_min_used_points").value),
        )
        self.odom_history: list[Odometry] = []
        self.last_rejection_reason = ""

        self.filtered_pub = self.create_publisher(Odometry, "/odometry/filtered", 10)
        self.tf_broadcaster = TransformBroadcaster(self)
        self.create_subscription(Odometry, "/wheel_odom", self._on_odom, 20)
        self.create_subscription(PointCloud2, "/scan_cloud", self._on_scan, 10)
        self.get_logger().info(
            f"V2A LiDAR localization up with {len(self.known_map)} map boxes from {map_file}"
        )

    def _on_odom(self, msg: Odometry) -> None:
        self.odom_history.append(msg)
        self.odom_history = self.odom_history[-200:]

    def _on_scan(self, msg: PointCloud2) -> None:
        odom_msg = self._odom_for_stamp(msg.header.stamp)
        if odom_msg is None:
            return
        odom_pose = Pose2D(
            x=float(odom_msg.pose.pose.position.x),
            y=float(odom_msg.pose.pose.position.y),
            yaw=yaw_from_odom(odom_msg),
        )
        points = _read_xyz(msg)
        if not points:
            return
        result = match_scan_to_map(
            points, odom_pose, self.known_map, self.lidar_extrinsic, self.match_config
        )
        decision = evaluate_lidar_correction(odom_pose, result, self.gate_config)
        if not decision.accepted and decision.reason != self.last_rejection_reason:
            self.get_logger().warn(
                "Rejected LiDAR correction: "
                f"{decision.reason}, delta={decision.translation_delta_m:.3f}m, "
                f"dyaw={decision.yaw_delta_rad:.3f}rad, score={result.mean_error_m:.3f}, "
                f"points={result.used_points}"
            )
            self.last_rejection_reason = decision.reason
        stamp = msg.header.stamp
        self._publish_filtered(stamp, decision.pose, odom_msg)
        self._publish_map_to_odom(stamp, decision.pose, odom_pose)

    def _odom_for_stamp(self, stamp) -> Odometry | None:
        if not self.odom_history:
            return None
        target = stamp.sec + stamp.nanosec * 1e-9
        return min(
            self.odom_history,
            key=lambda msg: abs(
                msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9 - target
            ),
        )

    def _publish_filtered(self, stamp, pose: Pose2D, odom_msg: Odometry) -> None:
        out = Odometry()
        out.header.stamp = stamp
        out.header.frame_id = "map"
        out.child_frame_id = "base_link"
        out.pose.pose.position.x = pose.x
        out.pose.pose.position.y = pose.y
        out.pose.pose.orientation = yaw_to_quaternion(pose.yaw)
        out.twist.twist = odom_msg.twist.twist
        self.filtered_pub.publish(out)

    def _publish_map_to_odom(self, stamp, map_base: Pose2D, odom_base: Pose2D) -> None:
        transform = map_to_odom_from_base_poses(map_base, odom_base)
        tf = TransformStamped()
        tf.header.stamp = stamp
        tf.header.frame_id = "map"
        tf.child_frame_id = "odom"
        tf.transform.translation.x = transform.x
        tf.transform.translation.y = transform.y
        tf.transform.rotation = yaw_to_quaternion(transform.yaw)
        self.tf_broadcaster.sendTransform(tf)


def _read_xyz(msg: PointCloud2) -> list[tuple[float, float, float]]:
    offsets = {field.name: field.offset for field in msg.fields}
    if not {"x", "y", "z"}.issubset(offsets):
        return []
    endian = ">" if msg.is_bigendian else "<"
    points: list[tuple[float, float, float]] = []
    for offset in range(0, len(msg.data), msg.point_step):
        x = struct.unpack_from(endian + "f", msg.data, offset + offsets["x"])[0]
        y = struct.unpack_from(endian + "f", msg.data, offset + offsets["y"])[0]
        z = struct.unpack_from(endian + "f", msg.data, offset + offsets["z"])[0]
        points.append((x, y, z))
    return points


def main() -> None:
    rclpy.init()
    node = LidarLocalizationNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
