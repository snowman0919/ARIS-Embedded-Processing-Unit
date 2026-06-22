"""Record the ARIS contract topics to a rosbag under $ARIS_LOGS/bags/.

V0 deliverable: capture every driving run for replay and later-stage testing.
Sensor streams (/scan_cloud, cameras, /imu/data, /gps/fix) are added to the list
once the Gazebo sensor suite lands (V2+); they are harmless no-ops until then.
"""

import os
import time

from launch import LaunchDescription
from launch.actions import ExecuteProcess

CONTRACT_TOPICS = [
    "/cmd_drive",
    "/cmd_vel",
    "/wheel_odom",
    "/odometry/filtered",
    "/vehicle/state",
    "/estop",
    "/tf",
    "/tf_static",
    # V2+: "/scan_cloud", "/imu/data", "/gps/fix", "/camera/front/image", ...
]


def _bag_out_dir():
    stamp = time.strftime("%Y%m%d_%H%M%S")
    # In the dev container the ARIS logs are mounted at /aris/logs, while
    # ARIS_LOGS may carry the host path; prefer the mount when it exists so the
    # bag persists to the host's ~/aris/logs.
    base = (
        "/aris/logs"
        if os.path.isdir("/aris/logs")
        else os.environ.get("ARIS_LOGS", os.path.expanduser("~/aris/logs"))
    )
    return os.path.join(base, "bags", f"aris_{stamp}")


def generate_launch_description():
    out_dir = _bag_out_dir()
    return LaunchDescription(
        [
            ExecuteProcess(
                cmd=["ros2", "bag", "record", "-o", out_dir, *CONTRACT_TOPICS],
                output="screen",
            ),
        ]
    )
