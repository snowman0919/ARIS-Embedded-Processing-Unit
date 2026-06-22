from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    route_file = LaunchConfiguration("route_file")
    description_launch = str(
        Path(get_package_share_directory("aris_description")) / "launch" / "description.launch.py"
    )
    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "route_file",
                default_value="",
                description="V1 route CSV. Empty keeps the demo path.",
            ),
            # One shared URDF -> base_link -> sensor TFs (sim and real identical).
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(description_launch),
                launch_arguments={"use_sim": "true"}.items(),
            ),
            # Placeholder global correction until aris_localization (V2) owns map->odom.
            Node(
                package="tf2_ros",
                executable="static_transform_publisher",
                name="map_to_odom_static",
                arguments=["--frame-id", "map", "--child-frame-id", "odom"],
                output="screen",
            ),
            # Simulation HAL: consumes /cmd_drive, emits odom + odom->base_link TF.
            Node(package="aris_vehicle_sim", executable="vehicle_sim_node", output="screen"),
            # Algorithm layer: /odometry/filtered -> /cmd_drive (sim-agnostic).
            Node(
                package="aris_planning",
                executable="local_planner_node",
                output="screen",
                parameters=[{"route_file": route_file}],
            ),
            # STM32 HAL (dry-run): /cmd_drive -> binary frames + /vehicle/state.
            Node(package="aris_mcu_bridge", executable="mcu_bridge_node", output="screen"),
        ]
    )
