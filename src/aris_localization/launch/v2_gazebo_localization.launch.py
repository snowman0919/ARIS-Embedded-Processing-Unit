"""Static Gazebo LiDAR -> localization smoke scaffold.

This launch proves that the Gazebo gpu_lidar cloud can flow through the ARIS
cloud contract and into the V2A localization wrapper. It does not yet sync a
moving Gazebo entity pose with the vehicle simulator.
"""

from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():
    localization_share = Path(get_package_share_directory("aris_localization"))
    lidar_launch = str(localization_share / "launch" / "v2_gazebo_lidar.launch.py")
    smoke_map = str(localization_share / "maps" / "aris_lidar_smoke.yaml")

    return LaunchDescription(
        [
            IncludeLaunchDescription(PythonLaunchDescriptionSource(lidar_launch)),
            Node(
                package="aris_vehicle_sim",
                executable="vehicle_sim_node",
                output="screen",
                parameters=[
                    {
                        "publish_filtered_odom": False,
                        "command_timeout_s": 0.2,
                    }
                ],
            ),
            Node(
                package="aris_localization",
                executable="lidar_localization_node",
                output="screen",
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
