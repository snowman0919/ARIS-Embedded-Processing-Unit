#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
aris_load_env
export ROS_DOMAIN_ID="${ARIS_V2_GAZEBO_LOCALIZATION_ROS_DOMAIN_ID:-147}"

aris_compose run --rm aris-ros2-dev bash -lc '
  set -euo pipefail
  colcon build --symlink-install
  set +u
  source install/setup.bash
  set -u

  launch_log=/tmp/aris_v2_gazebo_localization_launch.log
  probe_log=/tmp/aris_v2_gazebo_localization_probe.log
  timeout -s INT 28s ros2 launch aris_localization v2_gazebo_localization.launch.py \
    >"$launch_log" 2>&1 &
  launch_pid=$!
  sleep 5

  code=0
  python3 - <<PY >"$probe_log" 2>&1 || code=$?
import math
import time

from nav_msgs.msg import Odometry
import rclpy
from rclpy.duration import Duration
from rclpy.time import Time
from sensor_msgs.msg import PointCloud2
import tf2_ros

clouds = []
filtered = []

def on_cloud(msg: PointCloud2) -> None:
    clouds.append(msg)

def on_filtered(msg: Odometry) -> None:
    filtered.append(msg)

rclpy.init()
node = rclpy.create_node("aris_v2_gazebo_localization_probe")
node.create_subscription(PointCloud2, "/scan_cloud", on_cloud, 10)
node.create_subscription(Odometry, "/odometry/filtered", on_filtered, 10)
tf_buffer = tf2_ros.Buffer()
listener = tf2_ros.TransformListener(tf_buffer, node)

deadline = time.monotonic() + 14.0
map_to_odom = None
while time.monotonic() < deadline:
    rclpy.spin_once(node, timeout_sec=0.1)
    if map_to_odom is None:
        try:
            map_to_odom = tf_buffer.lookup_transform(
                "map",
                "odom",
                Time(),
                timeout=Duration(seconds=0.05),
            )
        except Exception:
            map_to_odom = None
    if clouds and filtered and map_to_odom is not None:
        break

node.destroy_node()
rclpy.shutdown()

failures = []
if not clouds:
    failures.append("no /scan_cloud sample")
if not filtered:
    failures.append("no /odometry/filtered sample")
if map_to_odom is None:
    failures.append("missing map->odom transform")
if failures:
    raise SystemExit("; ".join(failures))

cloud = clouds[-1]
odom = filtered[-1]
x = float(odom.pose.pose.position.x)
y = float(odom.pose.pose.position.y)
q = odom.pose.pose.orientation
yaw = math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))
if cloud.header.frame_id != "lidar_link":
    failures.append(f"cloud frame={cloud.header.frame_id!r}, expected lidar_link")
if cloud.width < 100 or cloud.point_step != 24:
    failures.append(f"unexpected cloud width/point_step={cloud.width}/{cloud.point_step}")
if abs(x) > 0.75 or abs(y) > 0.75 or abs(yaw) > 0.4:
    failures.append(f"unexpected filtered pose ({x:.3f}, {y:.3f}, {yaw:.3f})")
if failures:
    raise SystemExit("; ".join(failures))

tf = map_to_odom.transform.translation
print(
    "v2_gazebo_localization cloud_width={} filtered=({:.3f},{:.3f},{:.3f}) "
    "map_to_odom=({:.3f},{:.3f})".format(
        cloud.width,
        x,
        y,
        yaw,
        tf.x,
        tf.y,
    )
)
PY

  kill -INT "$launch_pid" >/dev/null 2>&1 || true
  wait "$launch_pid" || true

  if [[ "$code" != "0" ]]; then
    echo "ERROR: Gazebo LiDAR localization smoke failed."
    echo "--- ROS topics ---"
    ros2 topic list -t | sort || true
    echo "--- Gazebo topics ---"
    gz topic -l | sort || true
    echo "--- launch log ---"
    sed -n "1,240p" "$launch_log"
    echo "--- probe log ---"
    sed -n "1,160p" "$probe_log"
    exit "$code"
  fi

  sed -n "1,80p" "$probe_log"
'
