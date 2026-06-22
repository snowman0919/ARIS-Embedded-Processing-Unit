#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
aris_load_env
export ROS_DOMAIN_ID="${ARIS_V2_GAZEBO_DRIFT_RECOVERY_ROS_DOMAIN_ID:-149}"

aris_compose run --rm aris-ros2-dev bash -lc '
  set -euo pipefail
  colcon build --symlink-install
  set +u
  source install/setup.bash
  set -u

  launch_log=/tmp/aris_v2_gazebo_drift_recovery_launch.log
  metrics_file=/tmp/aris_v2_gazebo_drift_recovery_metrics.txt
  status_file=/tmp/aris_v2_gazebo_drift_recovery_status.txt

  timeout -s INT 36s ros2 launch aris_localization v2_gazebo_drift_recovery.launch.py \
    >"$launch_log" 2>&1 &
  launch_pid=$!
  sleep 6

  code=0
  python3 - <<PY || code=$?
import math
import time

from ackermann_msgs.msg import AckermannDriveStamped
from nav_msgs.msg import Odometry
import rclpy
from sensor_msgs.msg import PointCloud2

wheel = []
truth = []
filtered = []
clouds = []

def stamp_s(msg) -> float:
    return msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9

def yaw(msg: Odometry) -> float:
    q = msg.pose.pose.orientation
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))

def append_pose(store, msg: Odometry) -> None:
    store.append((stamp_s(msg), msg.pose.pose.position.x, msg.pose.pose.position.y, yaw(msg)))

def on_cloud(msg: PointCloud2) -> None:
    clouds.append(msg)

rclpy.init()
node = rclpy.create_node("aris_v2_gazebo_drift_recovery_smoke")
cmd_pub = node.create_publisher(AckermannDriveStamped, "/cmd_drive", 10)
node.create_subscription(Odometry, "/wheel_odom", lambda msg: append_pose(wheel, msg), 20)
node.create_subscription(Odometry, "/aris/sim/ground_truth", lambda msg: append_pose(truth, msg), 20)
node.create_subscription(Odometry, "/odometry/filtered", lambda msg: append_pose(filtered, msg), 20)
node.create_subscription(PointCloud2, "/scan_cloud", on_cloud, 10)

deadline = time.monotonic() + 9.0
while time.monotonic() < deadline:
    cmd = AckermannDriveStamped()
    cmd.header.stamp = node.get_clock().now().to_msg()
    cmd.drive.speed = 0.55
    cmd.drive.steering_angle = 0.0
    cmd_pub.publish(cmd)
    rclpy.spin_once(node, timeout_sec=0.05)
    time.sleep(0.05)

stop = AckermannDriveStamped()
for _ in range(10):
    cmd_pub.publish(stop)
    rclpy.spin_once(node, timeout_sec=0.05)

node.destroy_node()
rclpy.shutdown()

def sample_at(samples, stamp):
    ordered = sorted(samples, key=lambda sample: sample[0])
    if stamp <= ordered[0][0]:
        return ordered[0], abs(ordered[0][0] - stamp)
    if stamp >= ordered[-1][0]:
        return ordered[-1], abs(ordered[-1][0] - stamp)
    for before, after in zip(ordered, ordered[1:]):
        if before[0] <= stamp <= after[0]:
            span = max(after[0] - before[0], 1e-9)
            ratio = (stamp - before[0]) / span
            yaw_delta = math.atan2(math.sin(after[3] - before[3]), math.cos(after[3] - before[3]))
            return (
                stamp,
                before[1] + (after[1] - before[1]) * ratio,
                before[2] + (after[2] - before[2]) * ratio,
                before[3] + yaw_delta * ratio,
            ), max(abs(stamp - before[0]), abs(after[0] - stamp))
    nearest = min(ordered, key=lambda sample: abs(sample[0] - stamp))
    return nearest, abs(nearest[0] - stamp)

failures = []
if not wheel:
    failures.append("no /wheel_odom samples")
if not truth:
    failures.append("no /aris/sim/ground_truth samples")
if not filtered:
    failures.append("no /odometry/filtered samples")
if not clouds:
    failures.append("no /scan_cloud samples")
if failures:
    raise SystemExit("; ".join(failures))

matched = []
for ft, fx, fy, fyaw in filtered:
    (tt, tx, ty, tyaw), truth_dt = sample_at(truth, ft)
    (wt, wx, wy, wyaw), wheel_dt = sample_at(wheel, ft)
    if max(truth_dt, wheel_dt) > 0.20:
        continue
    filtered_error = abs(fy - ty)
    wheel_error = abs(wy - ty)
    yaw_error = abs(math.atan2(math.sin(fyaw - tyaw), math.cos(fyaw - tyaw)))
    matched.append((filtered_error, wheel_error, yaw_error, fx, tx, truth_dt, wheel_dt))

if not matched:
    raise SystemExit("no timestamp-aligned truth/wheel/localization samples")

max_filtered_error = max(item[0] for item in matched)
max_wheel_error = max(item[1] for item in matched)
max_yaw_error = max(item[2] for item in matched)
max_x = max(item[3] for item in matched)
max_dt = max(max(item[5], item[6]) for item in matched)
final_filtered_error = matched[-1][0]
final_wheel_error = matched[-1][1]

with open("/tmp/aris_v2_gazebo_drift_recovery_metrics.txt", "w") as handle:
    handle.write(
        f"wheel_samples={len(wheel)} truth_samples={len(truth)} filtered_samples={len(filtered)} "
        f"cloud_samples={len(clouds)} matched_samples={len(matched)} max_x={max_x:.3f} "
        f"max_wheel_error={max_wheel_error:.3f} max_filtered_error={max_filtered_error:.3f} "
        f"final_wheel_error={final_wheel_error:.3f} final_filtered_error={final_filtered_error:.3f} "
        f"max_yaw_error={max_yaw_error:.3f} max_dt={max_dt:.3f}\\n"
    )

status = "OK"
reason = ""
if max_x < 1.8:
    status = "FAIL"
    reason = f"vehicle did not move far enough: max_x={max_x:.3f}"
elif max_wheel_error < 0.08:
    status = "FAIL"
    reason = f"wheel odom drift was too small to prove recovery: {max_wheel_error:.3f}"
elif max_filtered_error > 0.10:
    status = "FAIL"
    reason = f"Gazebo LiDAR localization failed 10 cm lateral recovery gate: {max_filtered_error:.3f}"
elif final_filtered_error >= final_wheel_error:
    status = "FAIL"
    reason = (
        "Gazebo LiDAR localization did not improve final lateral error: "
        f"wheel={final_wheel_error:.3f}, filtered={final_filtered_error:.3f}"
    )
elif max_yaw_error > 0.05:
    status = "FAIL"
    reason = f"localization yaw error too high: {max_yaw_error:.3f}"

with open("/tmp/aris_v2_gazebo_drift_recovery_status.txt", "w") as handle:
    handle.write(status + "\\n" + reason + "\\n")
PY

  kill -INT "$launch_pid" >/dev/null 2>&1 || true
  wait "$launch_pid" || true

  cat "$metrics_file"
  if [[ "$code" != "0" || "$(head -n1 "$status_file")" != "OK" ]]; then
    [[ "$code" == "0" ]] || echo "probe failed with code $code"
    tail -n +2 "$status_file" 2>/dev/null || true
    echo "--- launch log ---"
    sed -n "1,260p" "$launch_log"
    exit 1
  fi
'
