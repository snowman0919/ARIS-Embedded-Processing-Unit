"""Single ARIS bringup switch (Sim2Real Strategy 6).

  ros2 launch aris_bringup bringup.launch.py use_sim:=true|false mode:=teleop|auto

Algorithm/HAL-reporting nodes run identically either way; only the actuation/
sensor source changes with use_sim, and the command source changes with mode.
Everything emits or consumes the same /cmd_drive contract.
"""

from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    GroupAction,
    IncludeLaunchDescription,
    LogInfo,
)
from launch.conditions import IfCondition, UnlessCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node


def generate_launch_description():
    use_sim = LaunchConfiguration("use_sim")
    mode = LaunchConfiguration("mode")
    description_launch = str(
        Path(get_package_share_directory("aris_description")) / "launch" / "description.launch.py"
    )

    is_teleop = IfCondition(PythonExpression(["'", mode, "' == 'teleop'"]))
    is_auto = IfCondition(PythonExpression(["'", mode, "' == 'auto'"]))

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "use_sim",
                default_value="true",
                description="true = simulation HAL; false = real STM32 + sensor drivers",
            ),
            DeclareLaunchArgument(
                "mode",
                default_value="teleop",
                description="teleop = manual /cmd_vel->/cmd_drive; auto = autonomous planner",
            ),
            # Shared vehicle model + base_link->sensor TFs (sim and real identical).
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(description_launch),
                launch_arguments={"use_sim": use_sim}.items(),
            ),
            # STM32 HAL: consumes /cmd_drive, reports /vehicle/state. Dry-run in sim.
            Node(package="aris_mcu_bridge", executable="mcu_bridge_node", output="screen"),
            # ---- Simulation HAL branch ----
            GroupAction(
                condition=IfCondition(use_sim),
                actions=[
                    Node(
                        package="aris_vehicle_sim",
                        executable="vehicle_sim_node",
                        output="screen",
                    ),
                    Node(
                        package="tf2_ros",
                        executable="static_transform_publisher",
                        name="map_to_odom_static",
                        arguments=["--frame-id", "map", "--child-frame-id", "odom"],
                        output="screen",
                    ),
                ],
            ),
            # ---- Real HAL branch (stubs until drivers exist) ----
            GroupAction(
                condition=UnlessCondition(use_sim),
                actions=[
                    LogInfo(
                        msg="[aris_bringup] use_sim:=false -> real HAL. TODO: launch the "
                        "LiDAR/camera drivers and STM32 serial bridge. No hardware drivers yet."
                    ),
                ],
            ),
            # ---- Command source: teleop or autonomous planner ----
            Node(
                package="aris_bringup",
                executable="teleop_node",
                output="screen",
                condition=is_teleop,
            ),
            Node(
                package="aris_planning",
                executable="local_planner_node",
                output="screen",
                condition=is_auto,
            ),
        ]
    )
