#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
aris_load_env
export ROS_DOMAIN_ID="${ARIS_LIDAR_SIM_ROS_DOMAIN_ID:-145}"

aris_compose run --rm aris-ros2-dev bash -lc '
  set -euo pipefail
  colcon build --symlink-install
  set +u
  source install/setup.bash
  set -u

  sim_log=/tmp/aris_lidar_sim_stack.log
  lidar_log=/tmp/aris_lidar_sim_node.log

  timeout -s INT 10s ros2 launch aris_vehicle_sim pure_sim.launch.py >"$sim_log" 2>&1 &
  sim_pid=$!
  sleep 2

  timeout -s INT 8s ros2 launch aris_vehicle_sim lidar_sim.launch.py >"$lidar_log" 2>&1 &
  lidar_pid=$!
  sleep 2

  code=0
  python3 - <<PY || code=$?
import time

import rclpy
from sensor_msgs.msg import PointCloud2

clouds = []

def on_cloud(msg: PointCloud2) -> None:
    clouds.append(msg)

rclpy.init()
node = rclpy.create_node("aris_lidar_sim_smoke")
node.create_subscription(PointCloud2, "/scan_cloud", on_cloud, 10)

deadline = time.monotonic() + 8.0
while time.monotonic() < deadline and not clouds:
    rclpy.spin_once(node, timeout_sec=0.1)

node.destroy_node()
rclpy.shutdown()

if not clouds:
    raise SystemExit("no /scan_cloud PointCloud2 sample received")

msg = clouds[-1]
print(f"height: {msg.height}")
print(f"width: {msg.width}")
print(f"point_step: {msg.point_step}")
print("fields:", [field.name for field in msg.fields])
PY

  kill -INT "$lidar_pid" >/dev/null 2>&1 || true
  kill -INT "$sim_pid" >/dev/null 2>&1 || true
  wait "$lidar_pid" || true
  wait "$sim_pid" || true

  if [[ "$code" != "0" ]]; then
    echo "ERROR: /scan_cloud PointCloud2 sample was not published by lidar_sim_node."
    echo "--- sim log ---"
    sed -n "1,180p" "$sim_log"
    echo "--- lidar log ---"
    sed -n "1,180p" "$lidar_log"
    exit "$code"
  fi
'
