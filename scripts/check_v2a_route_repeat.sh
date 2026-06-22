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

  route_file="/aris/data/routes/v2a_repeat_drift_route_$(date +%Y%m%d_%H%M%S).csv"
  launch_log=/tmp/aris_v2a_route_repeat_launch.log
  metrics_file=/tmp/aris_v2a_route_repeat_metrics.txt
  status_file=/tmp/aris_v2a_route_repeat_status.txt
  mkdir -p /aris/data/routes

  python3 - <<PY
import csv
from pathlib import Path

path = Path("$route_file")
with path.open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=("x", "y", "yaw", "v_target"))
    writer.writeheader()
    for idx in range(46):
        writer.writerow({"x": idx * 0.2, "y": 0.0, "yaw": 0.0, "v_target": 1.2})
print(f"route_file={path}")
PY

  timeout -s INT 18s ros2 launch aris_localization v2a_route_repeat.launch.py \
    route_file:="$route_file" >"$launch_log" 2>&1 &
  launch_pid=$!
  sleep 4

  python3 - <<PY
import csv
import math
import time
from pathlib import Path

import rclpy
from nav_msgs.msg import Odometry

route = []
with Path("$route_file").open(newline="") as handle:
    for row in csv.DictReader(handle):
        route.append((float(row["x"]), float(row["y"])))

wheel = []
truth = []
filtered = []

def stamp_s(msg: Odometry) -> float:
    return msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9

def yaw(msg: Odometry) -> float:
    q = msg.pose.pose.orientation
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))

def append(store, msg: Odometry) -> None:
    store.append((stamp_s(msg), msg.pose.pose.position.x, msg.pose.pose.position.y, yaw(msg)))

def nearest(samples, stamp):
    return min(samples, key=lambda sample: abs(sample[0] - stamp))

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
            sample = (
                stamp,
                before[1] + (after[1] - before[1]) * ratio,
                before[2] + (after[2] - before[2]) * ratio,
                before[3] + yaw_delta * ratio,
            )
            return sample, max(abs(stamp - before[0]), abs(after[0] - stamp))
    nearest_sample = nearest(ordered, stamp)
    return nearest_sample, abs(nearest_sample[0] - stamp)

def point_to_segment_distance(point, a, b) -> float:
    px, py = point
    ax, ay = a
    bx, by = b
    dx = bx - ax
    dy = by - ay
    denom = dx * dx + dy * dy
    if denom <= 1e-12:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / denom))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))

def route_error(point) -> float:
    return min(point_to_segment_distance(point, a, b) for a, b in zip(route, route[1:]))

rclpy.init()
node = rclpy.create_node("aris_v2a_route_repeat_smoke")
node.create_subscription(Odometry, "/wheel_odom", lambda msg: append(wheel, msg), 20)
node.create_subscription(Odometry, "/aris/sim/ground_truth", lambda msg: append(truth, msg), 20)
node.create_subscription(Odometry, "/odometry/filtered", lambda msg: append(filtered, msg), 20)

deadline = time.monotonic() + 10.0
while time.monotonic() < deadline:
    rclpy.spin_once(node, timeout_sec=0.1)

node.destroy_node()
rclpy.shutdown()

if not wheel:
    raise SystemExit("no /wheel_odom samples")
if not truth:
    raise SystemExit("no /aris/sim/ground_truth samples")
if not filtered:
    raise SystemExit("no /odometry/filtered samples")

matched = []
for ft, fx, fy, fyaw in filtered:
    (tt, tx, ty, tyaw), truth_dt = sample_at(truth, ft)
    (wt, wx, wy, wyaw), wheel_dt = sample_at(wheel, ft)
    if max(truth_dt, wheel_dt) > 0.15:
        continue
    matched.append(
        (
            route_error((tx, ty)),
            math.hypot(fx - tx, fy - ty),
            math.hypot(wx - tx, wy - ty),
            abs(math.atan2(math.sin(fyaw - tyaw), math.cos(fyaw - tyaw))),
            tx,
            max(truth_dt, wheel_dt),
        )
    )

if not matched:
    raise SystemExit("no timestamp-aligned truth/wheel/localization samples")

usable = [item for item in matched if item[4] >= 0.5]
if not usable:
    usable = matched

max_lateral_error = max(item[0] for item in usable)
max_filtered_error = max(item[1] for item in matched)
max_wheel_error = max(item[2] for item in matched)
max_yaw_error = max(item[3] for item in matched)
max_x = max(item[4] for item in matched)
max_dt = max(item[5] for item in matched)

with open("/tmp/aris_v2a_route_repeat_metrics.txt", "w") as handle:
    handle.write(
        f"route_file=$route_file wheel_samples={len(wheel)} truth_samples={len(truth)} "
        f"filtered_samples={len(filtered)} matched_samples={len(matched)} max_x={max_x:.3f} "
        f"max_lateral_error={max_lateral_error:.3f} max_wheel_error={max_wheel_error:.3f} "
        f"max_filtered_error={max_filtered_error:.3f} max_yaw_error={max_yaw_error:.3f} "
        f"max_dt={max_dt:.3f}\n"
    )

status = "OK"
reason = ""
if max_x < 4.0:
    status = "FAIL"
    reason = f"vehicle did not progress far enough: max_x={max_x:.3f} m"
elif max_lateral_error > 0.3:
    status = "FAIL"
    reason = f"route tracking exceeded 0.3 m: max_lateral_error={max_lateral_error:.3f} m"
elif max_wheel_error < 0.08:
    status = "FAIL"
    reason = f"wheel odom drift was too small to prove route repeat recovery: {max_wheel_error:.3f}"
elif max_yaw_error > 0.03:
    status = "FAIL"
    reason = f"localization yaw error too high: {max_yaw_error:.3f}"

with open("/tmp/aris_v2a_route_repeat_status.txt", "w") as handle:
    handle.write(status + "\n" + reason + "\n")
PY

  kill -INT "$launch_pid" >/dev/null 2>&1 || true
  wait "$launch_pid" || true
  cat "$metrics_file"
  if [[ "$(head -n1 "$status_file")" != "OK" ]]; then
    tail -n +2 "$status_file"
    echo "--- launch log ---"
    sed -n "1,240p" "$launch_log"
    exit 1
  fi
'
