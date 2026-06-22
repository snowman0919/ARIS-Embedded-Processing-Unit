"""Pose-sync-free Gazebo physics smoke scaffold.

This launch keeps the ARIS `/cmd_drive` contract and lets Gazebo's Ackermann
system move the spawned URDF through its wheel joints. It is intentionally kept
separate from the pose-sync localization smokes until the physics path is stable
enough to become the default V2 moving simulation authority.
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

    cmd_vel_bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        arguments=[
            "/cmd_vel@geometry_msgs/msg/Twist@gz.msgs.Twist",
            "/gazebo/odom@nav_msgs/msg/Odometry@gz.msgs.Odometry",
        ],
        remappings=[
            ("/cmd_vel", "/aris/gazebo/cmd_vel"),
        ],
        output="screen",
    )

    return LaunchDescription(
        [
            IncludeLaunchDescription(PythonLaunchDescriptionSource(lidar_launch)),
            Node(
                package="aris_vehicle_sim",
                executable="gazebo_cmd_drive_bridge_node",
                output="screen",
                parameters=[
                    {
                        "wheelbase_m": 1.25,
                        "max_speed_mps": 1.0,
                        "max_steer_rad": 0.6,
                        "command_timeout_s": 0.4,
                    }
                ],
            ),
            cmd_vel_bridge,
        ]
    )
