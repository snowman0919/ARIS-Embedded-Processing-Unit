from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():
    description_launch = str(
        Path(get_package_share_directory("aris_description")) / "launch" / "description.launch.py"
    )
    return LaunchDescription(
        [
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(description_launch),
                launch_arguments={"use_sim": "true"}.items(),
            ),
            Node(
                package="aris_vehicle_sim",
                executable="vehicle_sim_node",
                output="screen",
                parameters=[
                    {
                        "publish_filtered_odom": False,
                        "publish_ground_truth": True,
                        "wheel_odom_lateral_drift_per_m": 0.02,
                    }
                ],
            ),
            Node(
                package="aris_vehicle_sim",
                executable="lidar_sim_node",
                output="screen",
                parameters=[{"pose_topic": "/aris/sim/ground_truth"}],
            ),
            Node(
                package="aris_localization",
                executable="lidar_localization_node",
                output="screen",
                parameters=[
                    {
                        "xy_window_m": 0.25,
                        "xy_step_m": 0.05,
                        "yaw_window_rad": 0.0,
                        "prior_weight": 0.2,
                        "min_improvement_m": 0.0,
                    }
                ],
            ),
        ]
    )
