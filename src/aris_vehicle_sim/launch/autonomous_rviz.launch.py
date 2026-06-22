from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():
    share = Path(get_package_share_directory("aris_vehicle_sim"))
    autonomous_launch = str(share / "launch" / "autonomous_sim.launch.py")
    rviz_config = str(share / "rviz" / "autonomous_sim.rviz")
    return LaunchDescription(
        [
            IncludeLaunchDescription(PythonLaunchDescriptionSource(autonomous_launch)),
            Node(
                package="rviz2",
                executable="rviz2",
                arguments=["-d", rviz_config],
                output="screen",
            ),
        ]
    )
