"""V2 scaffold: headless Gazebo + ARIS URDF spawn + gpu_lidar bridge.

This launch is intentionally a verification scaffold, not a completed V2
localization stack. It preserves the single URDF as the vehicle source of truth
and normalizes the Gazebo gpu_lidar point cloud to the contract topic
/scan_cloud.
"""

from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    world = str(
        Path(get_package_share_directory("aris_localization"))
        / "worlds"
        / "aris_lidar_smoke.sdf"
    )
    description_launch = str(
        Path(get_package_share_directory("aris_description")) / "launch" / "description.launch.py"
    )
    xacro_path = str(
        Path(get_package_share_directory("aris_description")) / "urdf" / "aris.urdf.xacro"
    )
    robot_description = ParameterValue(
        Command(["xacro ", xacro_path, " use_sim:=true"]),
        value_type=str,
    )
    gz_sim_launch = str(
        Path(get_package_share_directory("ros_gz_sim")) / "launch" / "gz_sim.launch.py"
    )

    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(gz_sim_launch),
        launch_arguments={"gz_args": f"-s -r {world}"}.items(),
    )

    spawn_aris = TimerAction(
        period=2.0,
        actions=[
            Node(
                package="ros_gz_sim",
                executable="create",
                output="screen",
                parameters=[
                    {
                        "world": "aris_lidar_smoke",
                        "name": "aris",
                        "string": robot_description,
                        "allow_renaming": True,
                    }
                ],
            )
        ],
    )

    scan_bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        arguments=[
            "/scan_cloud/points@sensor_msgs/msg/PointCloud2@gz.msgs.PointCloudPacked",
        ],
        remappings=[
            ("/scan_cloud/points", "/gazebo/scan_cloud"),
        ],
        output="screen",
    )

    cloud_adapter = Node(
        package="aris_perception",
        executable="gazebo_cloud_adapter_node",
        parameters=[
            {
                "input_topic": "/gazebo/scan_cloud",
                "output_topic": "/scan_cloud",
                "target_frame": "lidar_link",
                "scan_period_s": 0.1,
            }
        ],
        output="screen",
    )

    return LaunchDescription(
        [
            gazebo,
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(description_launch),
                launch_arguments={"use_sim": "true"}.items(),
            ),
            spawn_aris,
            scan_bridge,
            cloud_adapter,
        ]
    )
