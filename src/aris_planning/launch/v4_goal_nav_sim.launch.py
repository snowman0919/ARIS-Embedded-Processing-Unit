from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    route_file = LaunchConfiguration("route_file")
    use_demo_graph = LaunchConfiguration("use_demo_graph")
    enable_dynamic_obstacles = LaunchConfiguration("enable_dynamic_obstacles")
    description_launch = str(
        Path(get_package_share_directory("aris_description")) / "launch" / "description.launch.py"
    )
    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "route_file",
                default_value="__demo__",
                description="Optional recorded V1 route CSV to convert into the V4 route graph.",
            ),
            DeclareLaunchArgument(
                "use_demo_graph",
                default_value="true",
                description="true = built-in semantic demo graph; false = route_file CSV graph.",
            ),
            DeclareLaunchArgument(
                "enable_dynamic_obstacles",
                default_value="false",
                description="Enable V5 /scan_cloud dynamic-obstacle advisory publishing.",
            ),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(description_launch),
                launch_arguments={"use_sim": "true"}.items(),
            ),
            Node(
                package="aris_vehicle_sim",
                executable="vehicle_sim_node",
                output="screen",
                parameters=[
                    {
                        "publish_filtered_odom": False,
                        "publish_ground_truth": True,
                        "wheel_odom_lateral_drift_per_m": 0.02,
                    }
                ],
            ),
            Node(
                package="aris_vehicle_sim",
                executable="lidar_sim_node",
                output="screen",
                parameters=[{"pose_topic": "/aris/sim/ground_truth"}],
            ),
            Node(
                package="aris_localization",
                executable="lidar_localization_node",
                output="screen",
                parameters=[
                    {
                        "xy_window_m": 0.25,
                        "xy_step_m": 0.05,
                        "yaw_window_rad": 0.0,
                        "prior_weight": 0.2,
                        "min_improvement_m": 0.0,
                    }
                ],
            ),
            Node(
                package="aris_perception",
                executable="dynamic_obstacle_node",
                output="screen",
                condition=IfCondition(enable_dynamic_obstacles),
                parameters=[
                    {
                        "corridor_half_width_m": 0.7,
                        "slow_distance_m": 3.0,
                        "stop_distance_m": 1.0,
                        "min_points": 4,
                        "sample_stride": 2,
                    }
                ],
            ),
            Node(
                package="aris_bringup",
                executable="operator_api_node",
                output="screen",
            ),
            Node(
                package="aris_planning",
                executable="global_planner_node",
                output="screen",
                parameters=[
                    {
                        "goal_x_m": 9.0,
                        "goal_y_m": 0.0,
                        "semantic_weight": 10.0,
                        "route_file": route_file,
                        "use_demo_graph": ParameterValue(use_demo_graph, value_type=bool),
                    }
                ],
            ),
            Node(
                package="aris_planning",
                executable="local_planner_node",
                output="screen",
                parameters=[
                    {
                        "goal_tolerance_m": 0.8,
                        "lookahead_m": 1.5,
                        "max_speed_mps": 1.4,
                    }
                ],
            ),
        ]
    )
