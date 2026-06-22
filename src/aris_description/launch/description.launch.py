from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    use_sim = LaunchConfiguration("use_sim")
    xacro_path = str(
        Path(get_package_share_directory("aris_description")) / "urdf" / "aris.urdf.xacro"
    )
    robot_description = ParameterValue(
        Command(["xacro ", xacro_path, " use_sim:=", use_sim]),
        value_type=str,
    )
    return LaunchDescription(
        [
            DeclareLaunchArgument("use_sim", default_value="true"),
            Node(
                package="robot_state_publisher",
                executable="robot_state_publisher",
                output="screen",
                parameters=[{"robot_description": robot_description}],
            ),
        ]
    )
