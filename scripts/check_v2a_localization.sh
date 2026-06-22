#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
aris_load_env

aris_compose run --rm aris-ros2-dev bash -lc '
  set -euo pipefail
  colcon build --symlink-install
  set +u
  source install/setup.bash
  set -u

  launch_log=/tmp/aris_v2a_localization_launch.log
  metrics_file=/tmp/aris_v2a_localization_metrics.txt
  status_file=/tmp/aris_v2a_localization_status.txt

  timeout -s INT 14s ros2 launch aris_localization v2a_lidar_localization.launch.py \
    >"$launch_log" 2>&1 &
  launch_pid=$!
  sleep 3

  python3 - <<"PY"
import math
import time

import rclpy
from ackermann_msgs.msg import AckermannDriveStamped
from nav_msgs.msg import Odometry

wheel = []
filtered = []

def stamp_s(msg: Odometry) -> float:
    return msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9

def yaw(msg: Odometry) -> float:
    q = msg.pose.pose.orientation
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))

def on_wheel(msg: Odometry) -> None:
    wheel.append((stamp_s(msg), msg.pose.pose.position.x, msg.pose.pose.position.y, yaw(msg)))

def on_filtered(msg: Odometry) -> None:
    filtered.append((stamp_s(msg), msg.pose.pose.position.x, msg.pose.pose.position.y, yaw(msg)))

rclpy.init()
node = rclpy.create_node("aris_v2a_localization_smoke")
cmd_pub = node.create_publisher(AckermannDriveStamped, "/cmd_drive", 10)
node.create_subscription(Odometry, "/wheel_odom", on_wheel, 20)
node.create_subscription(Odometry, "/odometry/filtered", on_filtered, 20)

deadline = time.monotonic() + 7.0
while time.monotonic() < deadline:
    cmd = AckermannDriveStamped()
    cmd.drive.speed = 1.0
    cmd.drive.steering_angle = 0.0
    cmd_pub.publish(cmd)
    rclpy.spin_once(node, timeout_sec=0.05)
    time.sleep(0.05)

stop = AckermannDriveStamped()
for _ in range(5):
    cmd_pub.publish(stop)
    rclpy.spin_once(node, timeout_sec=0.05)

node.destroy_node()
rclpy.shutdown()

if not wheel:
    raise SystemExit("no /wheel_odom samples")
if not filtered:
    raise SystemExit("no localization-owned /odometry/filtered samples")

matched_errors = []
for ft, fx, fy, fyaw in filtered:
    wt, wx, wy, wyaw = min(wheel, key=lambda sample: abs(sample[0] - ft))
    if abs(wt - ft) > 0.04:
        continue
    matched_errors.append(
        (
            math.hypot(fx - wx, fy - wy),
            abs(math.atan2(math.sin(fyaw - wyaw), math.cos(fyaw - wyaw))),
            abs(wt - ft),
        )
    )
if not matched_errors:
    raise SystemExit("no timestamp-aligned wheel/localization samples")

position_error = max(item[0] for item in matched_errors)
yaw_error = max(item[1] for item in matched_errors)
max_dt = max(item[2] for item in matched_errors)
max_x = max(sample[1] for sample in filtered)

with open("/tmp/aris_v2a_localization_metrics.txt", "w") as handle:
    handle.write(
        f"wheel_samples={len(wheel)} filtered_samples={len(filtered)} "
        f"matched_samples={len(matched_errors)} max_x={max_x:.3f} "
        f"max_position_error={position_error:.3f} max_yaw_error={yaw_error:.3f} max_dt={max_dt:.3f}\n"
    )

status = "OK"
reason = ""
if max_x < 2.0:
    status = "FAIL"
    reason = f"vehicle did not move far enough: max_x={max_x:.3f}"
elif position_error > 0.05:
    status = "FAIL"
    reason = f"localization position error exceeds 5 cm: {position_error:.3f}"
elif yaw_error > 0.03:
    status = "FAIL"
    reason = f"localization yaw error too high: {yaw_error:.3f}"
with open("/tmp/aris_v2a_localization_status.txt", "w") as handle:
    handle.write(status + "\n" + reason + "\n")
PY

  kill -INT "$launch_pid" >/dev/null 2>&1 || true
  wait "$launch_pid" || true
  cat "$metrics_file"
  if [[ "$(head -n1 "$status_file")" != "OK" ]]; then
    tail -n +2 "$status_file"
    echo "--- launch log ---"
    sed -n "1,220p" "$launch_log"
    exit 1
  fi
'
