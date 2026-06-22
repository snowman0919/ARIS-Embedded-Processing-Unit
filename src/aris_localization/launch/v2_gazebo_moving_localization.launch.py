"""Moving Gazebo LiDAR -> localization smoke scaffold.

The lightweight vehicle simulator remains the motion authority. This launch
synchronizes its `/wheel_odom` pose into the Gazebo ARIS entity so the Gazebo
gpu_lidar returns change as the vehicle moves through the smoke world.
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
                        "command_timeout_s": 0.4,
                    }
                ],
            ),
            Node(
                package="aris_localization",
                executable="gazebo_pose_sync_node",
                output="screen",
                parameters=[
                    {
                        "odom_topic": "/wheel_odom",
                        "world_name": "aris_lidar_smoke",
                        "entity_name": "aris",
                        "entity_z_m": 0.0,
                        "sync_hz": 8.0,
                        "min_translation_delta_m": 0.01,
                        "min_yaw_delta_rad": 0.005,
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
