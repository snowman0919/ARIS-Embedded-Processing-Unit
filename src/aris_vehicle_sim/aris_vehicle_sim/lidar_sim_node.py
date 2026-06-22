"""Thin ROS wrapper for the spec-driven ARIS LiDAR simulator."""

from __future__ import annotations

import random
import struct
from pathlib import Path
import math

from ament_index_python.packages import get_package_share_directory
from nav_msgs.msg import Odometry
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2, PointField

from .lidar_sim_core import (
    LidarReturn,
    Pose3D,
    load_profile,
    load_world,
    pose_lidar_from_base,
    simulate_lidar_frame,
)


def yaw_from_odom(msg: Odometry) -> float:
    q = msg.pose.pose.orientation
    siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
    cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
    return math.atan2(siny_cosp, cosy_cosp)


class LidarSimNode(Node):
    def __init__(self) -> None:
        super().__init__("aris_lidar_sim")
        share = Path(get_package_share_directory("aris_vehicle_sim"))
        self.declare_parameter("profile_file", str(share / "config" / "aris_lidar_3d_default.yaml"))
        self.declare_parameter("map_file", str(share / "maps" / "simple_3d_track.yaml"))
        self.declare_parameter("lidar_x_m", 0.6)
        self.declare_parameter("lidar_y_m", 0.0)
        self.declare_parameter("lidar_z_m", 0.9)
        self.declare_parameter("lidar_yaw_rad", 0.0)
        self.declare_parameter("pose_topic", "/wheel_odom")
        self.declare_parameter("random_seed", 7)

        profile_file = str(self.get_parameter("profile_file").value).strip()
        map_file = str(self.get_parameter("map_file").value).strip()
        if not profile_file:
            profile_file = str(share / "config" / "aris_lidar_3d_default.yaml")
        if not map_file:
            map_file = str(share / "maps" / "simple_3d_track.yaml")

        self.profile = load_profile(profile_file)
        self.world = load_world(map_file)
        self.lidar_extrinsic = Pose3D(
            x=float(self.get_parameter("lidar_x_m").value),
            y=float(self.get_parameter("lidar_y_m").value),
            z=float(self.get_parameter("lidar_z_m").value),
            yaw=float(self.get_parameter("lidar_yaw_rad").value),
        )
        self.rng = random.Random(int(self.get_parameter("random_seed").value))
        self.base_pose: Pose3D | None = None
        self.base_stamp = None

        self.cloud_pub = self.create_publisher(PointCloud2, "/scan_cloud", 10)
        pose_topic = str(self.get_parameter("pose_topic").value)
        self.create_subscription(Odometry, pose_topic, self._on_odom, 20)
        self.create_timer(1.0 / max(self.profile.scan_rate_hz, 1e-6), self._publish_scan)
        self.get_logger().info(
            f"LiDAR sim up: {self.profile.model}, {len(self.profile.vertical_angles_deg)} rings, "
            f"{self.profile.horizontal_samples} horizontal samples, pose={pose_topic} -> /scan_cloud"
        )

    def _on_odom(self, msg: Odometry) -> None:
        self.base_pose = Pose3D(
            x=float(msg.pose.pose.position.x),
            y=float(msg.pose.pose.position.y),
            z=float(msg.pose.pose.position.z),
            yaw=yaw_from_odom(msg),
        )
        self.base_stamp = msg.header.stamp

    def _publish_scan(self) -> None:
        if self.base_pose is None or self.base_stamp is None:
            return
        lidar_pose = pose_lidar_from_base(self.base_pose, self.lidar_extrinsic)
        returns = simulate_lidar_frame(lidar_pose, self.profile, self.world, rng=self.rng)
        self.cloud_pub.publish(self._to_pointcloud2(returns, self.base_stamp))

    def _to_pointcloud2(self, returns: list[LidarReturn], stamp) -> PointCloud2:
        msg = PointCloud2()
        msg.header.stamp = stamp
        msg.header.frame_id = "lidar_link"
        msg.height = 1
        msg.width = len(returns)
        msg.fields = [
            PointField(name="x", offset=0, datatype=PointField.FLOAT32, count=1),
            PointField(name="y", offset=4, datatype=PointField.FLOAT32, count=1),
            PointField(name="z", offset=8, datatype=PointField.FLOAT32, count=1),
            PointField(name="intensity", offset=12, datatype=PointField.FLOAT32, count=1),
            PointField(name="ring", offset=16, datatype=PointField.UINT16, count=1),
            PointField(name="time", offset=20, datatype=PointField.FLOAT32, count=1),
        ]
        msg.is_bigendian = False
        msg.point_step = 24
        msg.row_step = msg.point_step * msg.width
        msg.is_dense = True
        msg.data = b"".join(
            struct.pack("<ffffH2xf", point.x, point.y, point.z, point.intensity, point.ring, point.time_s)
            for point in returns
        )
        return msg


def main() -> None:
    rclpy.init()
    node = LidarSimNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
