#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
aris_load_env
export ROS_DOMAIN_ID="${ARIS_V2_GAZEBO_PHYSICS_ROS_DOMAIN_ID:-150}"

aris_compose run --rm aris-ros2-dev bash -lc '
  set -euo pipefail
  colcon build --symlink-install
  set +u
  source install/setup.bash
  set -u

  launch_log=/tmp/aris_v2_gazebo_physics_launch.log
  probe_log=/tmp/aris_v2_gazebo_physics_probe.log
  pose_log=/tmp/aris_v2_gazebo_physics_pose.log

  timeout -s INT 34s ros2 launch aris_localization v2_gazebo_physics.launch.py \
    >"$launch_log" 2>&1 &
  launch_pid=$!
  sleep 7

  code=0
  python3 - <<PY >"$probe_log" 2>&1 || code=$?
import time

from ackermann_msgs.msg import AckermannDriveStamped
from nav_msgs.msg import Odometry
import rclpy
from sensor_msgs.msg import PointCloud2

odom = []
clouds = []

def on_odom(msg: Odometry) -> None:
    odom.append(msg)

def on_cloud(msg: PointCloud2) -> None:
    clouds.append(msg)

rclpy.init()
node = rclpy.create_node("aris_v2_gazebo_physics_probe")
cmd_pub = node.create_publisher(AckermannDriveStamped, "/cmd_drive", 10)
node.create_subscription(Odometry, "/gazebo/odom", on_odom, 10)
node.create_subscription(PointCloud2, "/scan_cloud", on_cloud, 10)

start = time.monotonic()
while time.monotonic() - start < 8.0:
    cmd = AckermannDriveStamped()
    cmd.header.stamp = node.get_clock().now().to_msg()
    cmd.drive.speed = 0.6 if time.monotonic() - start < 6.0 else 0.0
    cmd.drive.steering_angle = 0.0
    cmd_pub.publish(cmd)
    rclpy.spin_once(node, timeout_sec=0.05)
    time.sleep(0.05)

node.destroy_node()
rclpy.shutdown()

failures = []
if len(odom) < 3:
    failures.append(f"too few /gazebo/odom samples: {len(odom)}")
if not clouds:
    failures.append("no /scan_cloud samples")
if failures:
    raise SystemExit("; ".join(failures))

first = odom[0].pose.pose.position
last = odom[-1].pose.pose.position
delta_x = float(last.x - first.x)
if delta_x < 0.25:
    failures.append(
        f"Gazebo odom did not move far enough: delta_x={delta_x:.3f}, samples={len(odom)}"
    )
if abs(float(last.y)) > 0.25:
    failures.append(f"Gazebo odom y drift too high: y={float(last.y):.3f}")
if clouds[-1].header.frame_id != "lidar_link":
    failures.append(f"cloud frame={clouds[-1].header.frame_id!r}, expected lidar_link")
if failures:
    raise SystemExit("; ".join(failures))

print(
    "v2_gazebo_physics odom_samples={} cloud_samples={} odom_start=({:.3f},{:.3f}) "
    "odom_last=({:.3f},{:.3f}) delta_x={:.3f}".format(
        len(odom),
        len(clouds),
        float(first.x),
        float(first.y),
        float(last.x),
        float(last.y),
        delta_x,
    )
)
PY

  timeout 3s gz topic -e -t /world/aris_lidar_smoke/pose/info >"$pose_log" 2>/dev/null || true

  python3 - <<PY >>"$probe_log" 2>&1 || code=$?
from pathlib import Path
import re

text = Path("$pose_log").read_text(errors="replace")
matches = list(
    re.finditer(
        r"name: \"aris\".*?position \\{\\s*x: ([^\\s]+).*?\\}",
        text,
        flags=re.DOTALL,
    )
)
if not matches:
    raise SystemExit("could not find aris pose in Gazebo pose/info")
x = float(matches[-1].group(1))
if x < 0.25:
    raise SystemExit(f"Gazebo aris entity did not move far enough: x={x:.3f}")
print(f"gazebo_aris_pose_x={x:.3f}")
PY

  kill -INT "$launch_pid" >/dev/null 2>&1 || true
  wait "$launch_pid" || true

  if [[ "$code" != "0" ]]; then
    echo "ERROR: Gazebo physics motion smoke failed."
    echo "--- ROS topics ---"
    ros2 topic list -t | sort || true
    echo "--- Gazebo topics ---"
    gz topic -l | sort || true
    echo "--- launch log ---"
    sed -n "1,260p" "$launch_log"
    echo "--- probe log ---"
    sed -n "1,220p" "$probe_log"
    echo "--- Gazebo pose log excerpt ---"
    sed -n "1,120p" "$pose_log"
    exit "$code"
  fi

  sed -n "1,120p" "$probe_log"
'
