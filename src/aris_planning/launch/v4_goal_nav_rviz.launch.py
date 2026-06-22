from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    route_file = LaunchConfiguration("route_file")
    use_demo_graph = LaunchConfiguration("use_demo_graph")
    planning_share = Path(get_package_share_directory("aris_planning"))
    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "route_file",
                default_value="__demo__",
                description="Optional recorded route CSV for the V4 route graph.",
            ),
            DeclareLaunchArgument(
                "use_demo_graph",
                default_value="true",
                description="true = built-in semantic demo graph; false = route_file CSV graph.",
            ),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    str(planning_share / "launch" / "v4_goal_nav_sim.launch.py")
                ),
                launch_arguments={
                    "route_file": route_file,
                    "use_demo_graph": use_demo_graph,
                }.items(),
            ),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    str(planning_share / "launch" / "v4_rviz.launch.py")
                )
            ),
        ]
    )
