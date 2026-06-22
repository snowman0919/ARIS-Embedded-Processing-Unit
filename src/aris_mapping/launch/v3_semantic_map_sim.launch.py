from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    route_file = LaunchConfiguration("route_file")
    snapshot_file = LaunchConfiguration("snapshot_file")
    v2a_route_launch = str(
        Path(get_package_share_directory("aris_localization"))
        / "launch"
        / "v2a_route_repeat.launch.py"
    )
    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "route_file",
                default_value="/aris/data/routes/route.csv",
                description="V1 route CSV used by the V3 simulation smoke.",
            ),
            DeclareLaunchArgument(
                "snapshot_file",
                default_value="",
                description="Optional semantic HD map snapshot JSON output path.",
            ),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(v2a_route_launch),
                launch_arguments={"route_file": route_file}.items(),
            ),
            Node(
                package="aris_perception",
                executable="simulated_segmentation_node",
                output="screen",
            ),
            Node(
                package="aris_mapping",
                executable="semantic_map_node",
                output="screen",
                parameters=[
                    {
                        "route_file": route_file,
                        "snapshot_file": snapshot_file,
                    }
                ],
            ),
        ]
    )
