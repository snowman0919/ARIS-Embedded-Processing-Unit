from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription(
        [
            Node(package="aris_mcu_bridge", executable="mcu_bridge_node", output="screen"),
        ]
    )
