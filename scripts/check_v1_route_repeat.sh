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

  route_file="/aris/data/routes/v1_smoke_route_$(date +%Y%m%d_%H%M%S).csv"
  metrics_file=/tmp/aris_v1_route_metrics.txt
  teach_log=/tmp/aris_v1_teach_launch.log
  recorder_log=/tmp/aris_v1_recorder_launch.log
  repeat_log=/tmp/aris_v1_repeat_launch.log
  mkdir -p /aris/data/routes

  timeout -s INT 14s ros2 launch aris_bringup bringup.launch.py \
    use_sim:=true mode:=teleop >"$teach_log" 2>&1 &
  teach_pid=$!
  sleep 2

  timeout -s INT 10s ros2 launch aris_planning path_recorder.launch.py \
    route_file:="$route_file" waypoint_spacing_m:=0.2 v_target_mps:=1.2 \
    >"$recorder_log" 2>&1 &
  recorder_pid=$!
  sleep 1

  python3 - <<"PY"
import time

import rclpy
from geometry_msgs.msg import Twist

rclpy.init()
node = rclpy.create_node("aris_v1_teach_driver")
pub = node.create_publisher(Twist, "/cmd_vel", 10)
deadline = time.monotonic() + 7.0
while time.monotonic() < deadline:
    msg = Twist()
    msg.linear.x = 1.2
    msg.angular.z = 0.0
    pub.publish(msg)
    rclpy.spin_once(node, timeout_sec=0.02)
    time.sleep(0.08)
stop = Twist()
for _ in range(5):
    pub.publish(stop)
    rclpy.spin_once(node, timeout_sec=0.02)
    time.sleep(0.05)
node.destroy_node()
rclpy.shutdown()
PY

  kill -INT "$recorder_pid" >/dev/null 2>&1 || true
  kill -INT "$teach_pid" >/dev/null 2>&1 || true
  recorder_code=0
  wait "$recorder_pid" || recorder_code=$?
  teach_code=0
  wait "$teach_pid" || teach_code=$?
  if [[ "$recorder_code" != "0" && "$recorder_code" != "124" && "$recorder_code" != "130" ]]; then
    cat "$recorder_log"
    exit "$recorder_code"
  fi
  if [[ "$teach_code" != "0" && "$teach_code" != "124" && "$teach_code" != "130" ]]; then
    cat "$teach_log"
    exit "$teach_code"
  fi

  python3 - <<PY
import csv
import math
from pathlib import Path

route_file = Path("$route_file")
with route_file.open(newline="") as handle:
    rows = list(csv.DictReader(handle))
if len(rows) < 20:
    raise SystemExit(f"recorded route is too short: {len(rows)} waypoints in {route_file}")
points = [(float(row["x"]), float(row["y"])) for row in rows]
length = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(points, points[1:]))
if length < 4.0:
    raise SystemExit(f"recorded route is too short: length={length:.3f} m")
print(f"recorded_route={route_file} waypoints={len(rows)} length={length:.3f}m")
PY

  timeout -s INT 14s ros2 launch aris_bringup bringup.launch.py \
    use_sim:=true mode:=auto route_file:="$route_file" >"$repeat_log" 2>&1 &
  repeat_pid=$!

  python3 - <<PY
import csv
import math
import time
from pathlib import Path

import rclpy
from nav_msgs.msg import Odometry

with Path("$route_file").open(newline="") as handle:
    route = [(float(row["x"]), float(row["y"])) for row in csv.DictReader(handle)]
samples = []

def on_odom(msg: Odometry) -> None:
    samples.append((float(msg.pose.pose.position.x), float(msg.pose.pose.position.y)))

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
    return min(
        point_to_segment_distance(point, a, b)
        for a, b in zip(route, route[1:])
    )

rclpy.init()
node = rclpy.create_node("aris_v1_route_smoke")
node.create_subscription(Odometry, "/odometry/filtered", on_odom, 20)
deadline = time.monotonic() + 9.0
while time.monotonic() < deadline:
    rclpy.spin_once(node, timeout_sec=0.1)
node.destroy_node()
rclpy.shutdown()

if not samples:
    raise SystemExit("no /odometry/filtered samples received")

usable = [(x, y) for x, y in samples if x >= 0.5]
max_lateral_error = max((route_error(point) for point in usable), default=route_error(samples[-1]))
max_x = max(x for x, _ in samples)
Path("/tmp/aris_v1_route_metrics.txt").write_text(
    f"route_file=$route_file samples={len(samples)} max_x={max_x:.3f} "
    f"max_lateral_error={max_lateral_error:.3f}\n"
)
if max_x < 4.0:
    raise SystemExit(f"vehicle did not progress far enough: max_x={max_x:.3f} m")
if max_lateral_error > 0.3:
    raise SystemExit(
        f"route tracking exceeded 0.3 m: max_lateral_error={max_lateral_error:.3f} m"
    )
PY

  kill -INT "$repeat_pid" >/dev/null 2>&1 || true
  code=0
  wait "$repeat_pid" || code=$?
  if [[ "$code" != "0" && "$code" != "124" && "$code" != "130" ]]; then
    cat "$repeat_log"
    exit "$code"
  fi
  cat "$metrics_file"
'
