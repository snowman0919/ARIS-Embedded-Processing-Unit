#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
aris_load_env
export ROS_DOMAIN_ID="${ARIS_V2_RECORDED_LIDAR_ROS_DOMAIN_ID:-152}"

aris_compose run --rm aris-ros2-dev bash -lc '
  set -euo pipefail
  colcon build --symlink-install
  set +u
  source install/setup.bash
  set -u

  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  bag_dir="${ARIS_V2_RECORDED_LIDAR_BAG_DIR:-/aris/logs/bags/v2_recorded_lidar_${timestamp}}"
  launch_log=/tmp/aris_v2_recorded_lidar_launch.log
  record_log=/tmp/aris_v2_recorded_lidar_record.log
  probe_log=/tmp/aris_v2_recorded_lidar_probe.log

  mkdir -p "$(dirname "$bag_dir")"
  rm -rf "$bag_dir"

  timeout -s INT 42s ros2 launch aris_localization v2_gazebo_physics_localization.launch.py \
    >"$launch_log" 2>&1 &
  launch_pid=$!
  sleep 7

  timeout -k 8s -s INT 14s ros2 bag record -s mcap -o "$bag_dir" \
    /cmd_drive \
    /scan_cloud \
    /gazebo/odom \
    /odometry/filtered \
    /tf \
    >"$record_log" 2>&1 &
  record_pid=$!
  sleep 2

  code=0
  python3 - <<PY >"$probe_log" 2>&1 || code=$?
import time

from ackermann_msgs.msg import AckermannDriveStamped
import rclpy

rclpy.init()
node = rclpy.create_node("aris_v2_recorded_lidar_driver")
cmd_pub = node.create_publisher(AckermannDriveStamped, "/cmd_drive", 10)

start = time.monotonic()
while time.monotonic() - start < 8.0:
    cmd = AckermannDriveStamped()
    cmd.header.stamp = node.get_clock().now().to_msg()
    cmd.drive.speed = 0.55 if time.monotonic() - start < 6.5 else 0.0
    cmd.drive.steering_angle = 0.0
    cmd_pub.publish(cmd)
    rclpy.spin_once(node, timeout_sec=0.05)
    time.sleep(0.05)

node.destroy_node()
rclpy.shutdown()
print("recorded_lidar_drive_commands=sent")
PY

  record_status=0
  wait "$record_pid" || record_status=$?
  if [[ "$record_status" != "0" && "$record_status" != "124" && "$record_status" != "130" ]]; then
    code="$record_status"
  fi
  kill -INT "$launch_pid" >/dev/null 2>&1 || true
  wait "$launch_pid" || true

  /workspaces/aris/scripts/validate_v2_lidar_bag.py "$bag_dir" >>"$probe_log" 2>&1 || code=$?

  if [[ "$code" != "0" ]]; then
    echo "ERROR: recorded LiDAR bag acceptance failed."
    echo "--- launch log ---"
    sed -n "1,260p" "$launch_log"
    echo "--- record log ---"
    sed -n "1,220p" "$record_log"
    echo "--- probe log ---"
    sed -n "1,220p" "$probe_log"
    [[ -f "$bag_dir/metadata.yaml" ]] && sed -n "1,220p" "$bag_dir/metadata.yaml"
    exit "$code"
  fi

  sed -n "1,160p" "$probe_log"
'
