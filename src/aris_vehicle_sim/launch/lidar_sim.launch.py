from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    profile_file = LaunchConfiguration("profile_file")
    map_file = LaunchConfiguration("map_file")

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "profile_file",
                default_value="",
                description="Optional LiDAR profile YAML. Empty uses the package default.",
            ),
            DeclareLaunchArgument(
                "map_file",
                default_value="",
                description="Optional 3D box map YAML. Empty uses the package default.",
            ),
            Node(
                package="aris_vehicle_sim",
                executable="lidar_sim_node",
                output="screen",
                parameters=[
                    {
                        "profile_file": profile_file,
                        "map_file": map_file,
                    }
                ],
            ),
        ]
    )
