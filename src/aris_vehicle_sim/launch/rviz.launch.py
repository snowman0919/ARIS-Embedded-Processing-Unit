from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
from pathlib import Path


def generate_launch_description():
    config = Path(get_package_share_directory("aris_vehicle_sim")) / "rviz" / "autonomous_sim.rviz"
    return LaunchDescription([
        Node(package="rviz2", executable="rviz2", arguments=["-d", str(config)], output="screen"),
    ])
