"""V0 convenience: bring up the simulation stack in manual teleop mode.

Equivalent to `bringup.launch.py use_sim:=true mode:=teleop`. After launching,
drive with the stock keyboard teleop in another terminal:

    ros2 run teleop_twist_keyboard teleop_twist_keyboard

and record with `record.launch.py` if desired.
"""

from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, LogInfo
from launch.launch_description_sources import PythonLaunchDescriptionSource


def generate_launch_description():
    bringup = str(
        Path(get_package_share_directory("aris_bringup")) / "launch" / "bringup.launch.py"
    )
    return LaunchDescription(
        [
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(bringup),
                launch_arguments={"use_sim": "true", "mode": "teleop"}.items(),
            ),
            LogInfo(
                msg="V0 teleop ready. In another terminal: "
                "ros2 run teleop_twist_keyboard teleop_twist_keyboard"
            ),
        ]
    )
