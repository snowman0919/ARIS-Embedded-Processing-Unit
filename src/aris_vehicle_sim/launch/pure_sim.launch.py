from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():
    # Brings up the simulation HAL + description + MCU bridge without a planner,
    # so the stack and TF tree come up but the vehicle stays stationary.
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
                package="tf2_ros",
                executable="static_transform_publisher",
                name="map_to_odom_static",
                arguments=["--frame-id", "map", "--child-frame-id", "odom"],
                output="screen",
            ),
            Node(package="aris_vehicle_sim", executable="vehicle_sim_node", output="screen"),
            Node(package="aris_mcu_bridge", executable="mcu_bridge_node", output="screen"),
        ]
    )
