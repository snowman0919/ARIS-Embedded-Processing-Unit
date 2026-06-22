"""Gazebo gpu_lidar drift-recovery scaffold.

The vehicle simulator publishes intentionally drifted `/wheel_odom` plus
ground truth. Gazebo follows ground truth so its gpu_lidar sees the true scene,
while `lidar_localization_node` must correct the drifted odometry estimate from
the Gazebo `/scan_cloud`.
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
                        "publish_ground_truth": True,
                        "command_timeout_s": 0.4,
                        "wheel_odom_lateral_drift_per_m": 0.04,
                    }
                ],
            ),
            Node(
                package="aris_localization",
                executable="gazebo_pose_sync_node",
                output="screen",
                parameters=[
                    {
                        "odom_topic": "/aris/sim/ground_truth",
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
                        "xy_window_m": 0.30,
                        "xy_step_m": 0.05,
                        "yaw_window_rad": 0.0,
                        "max_points": 400,
                        "prior_weight": 0.1,
                        "min_improvement_m": 0.0,
                        "correction_max_translation_m": 0.50,
                        "correction_max_mean_error_m": 1.0,
                    }
                ],
            ),
        ]
    )
