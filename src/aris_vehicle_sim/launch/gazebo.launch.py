from launch import LaunchDescription
from launch.actions import ExecuteProcess


def generate_launch_description():
    return LaunchDescription([
        ExecuteProcess(cmd=["gz", "sim", "-r", "sim/worlds/aris_empty.sdf"], output="screen"),
    ])
