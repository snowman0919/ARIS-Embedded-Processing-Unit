from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    route_file = LaunchConfiguration("route_file")
    waypoint_spacing_m = LaunchConfiguration("waypoint_spacing_m")
    v_target_mps = LaunchConfiguration("v_target_mps")

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "route_file",
                default_value="",
                description="Route CSV path. Empty means $ARIS_DATA/routes/route.csv.",
            ),
            DeclareLaunchArgument(
                "waypoint_spacing_m",
                default_value="0.2",
                description="Distance between recorded waypoints.",
            ),
            DeclareLaunchArgument(
                "v_target_mps",
                default_value="1.0",
                description="Recorded target speed column value.",
            ),
            Node(
                package="aris_planning",
                executable="path_recorder_node",
                output="screen",
                parameters=[
                    {
                        "route_file": route_file,
                        "waypoint_spacing_m": ParameterValue(
                            waypoint_spacing_m, value_type=float
                        ),
                        "v_target_mps": ParameterValue(v_target_mps, value_type=float),
                    }
                ],
            ),
        ]
    )
