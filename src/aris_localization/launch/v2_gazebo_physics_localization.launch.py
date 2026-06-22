"""Gazebo physics odometry -> LiDAR localization smoke scaffold.

This is the pose-sync-free successor path for V2 moving localization: Gazebo's
Ackermann plugin owns motion, `/gazebo/odom` is treated as wheel odometry, and
`lidar_localization_node` publishes `/odometry/filtered` from Gazebo `gpu_lidar`
observations.
"""

from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():
    localization_share = Path(get_package_share_directory("aris_localization"))
    physics_launch = str(localization_share / "launch" / "v2_gazebo_physics.launch.py")
    smoke_map = str(localization_share / "maps" / "aris_lidar_smoke.yaml")

    return LaunchDescription(
        [
            IncludeLaunchDescription(PythonLaunchDescriptionSource(physics_launch)),
            Node(
                package="aris_localization",
                executable="lidar_localization_node",
                output="screen",
                remappings=[
                    ("/wheel_odom", "/gazebo/odom"),
                ],
                parameters=[
                    {
                        "map_file": smoke_map,
                        "xy_window_m": 0.0,
                        "yaw_window_rad": 0.0,
                        "max_points": 300,
                        "min_improvement_m": 0.0,
                        "correction_max_mean_error_m": 2.0,
                    }
                ],
            ),
        ]
    )
