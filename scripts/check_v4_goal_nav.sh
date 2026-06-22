#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
aris_load_env
export ROS_DOMAIN_ID="${ARIS_V4_SMOKE_ROS_DOMAIN_ID:-142}"

aris_compose run --rm aris-ros2-dev bash -lc '
  set -euo pipefail
  colcon build --symlink-install
  set +u
  source install/setup.bash
  set -u

  launch_log=/tmp/aris_v4_goal_nav_launch.log

  timeout -s INT 28s ros2 launch aris_planning v4_goal_nav_sim.launch.py \
    >"$launch_log" 2>&1 &
  launch_pid=$!
  sleep 4

  python3 - <<PY
import json
import math
import time

import rclpy
from geometry_msgs.msg import PoseArray
from nav_msgs.msg import Odometry
from std_msgs.msg import String

truth = []
paths = []
summaries = []

def stamp_s(msg: Odometry) -> float:
    return msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9

def on_truth(msg: Odometry) -> None:
    truth.append((stamp_s(msg), msg.pose.pose.position.x, msg.pose.pose.position.y))

def on_path(msg: PoseArray) -> None:
    paths.append([(pose.position.x, pose.position.y) for pose in msg.poses])

def on_summary(msg: String) -> None:
    summaries.append(json.loads(msg.data))

rclpy.init()
node = rclpy.create_node("aris_v4_goal_nav_smoke")
node.create_subscription(Odometry, "/aris/sim/ground_truth", on_truth, 20)
node.create_subscription(PoseArray, "/global_path", on_path, 20)
node.create_subscription(String, "/aris/planning/global_plan", on_summary, 20)

deadline = time.monotonic() + 18.0
while time.monotonic() < deadline:
    rclpy.spin_once(node, timeout_sec=0.1)

node.destroy_node()
rclpy.shutdown()

if not truth:
    raise SystemExit("no /aris/sim/ground_truth samples")
if not paths:
    raise SystemExit("no /global_path samples")
if not summaries:
    raise SystemExit("no /aris/planning/global_plan summaries")

last_path = paths[-1]
last_summary = summaries[-1]
final_x, final_y = truth[-1][1], truth[-1][2]
goal_error = math.hypot(final_x - 9.0, final_y - 0.0)
max_y_path = max(y for _, y in last_path)
max_x = max(x for _, x, _ in truth)
min_blocked_distance = min(math.hypot(x - 6.0, y - 0.0) for x, y in last_path)

print(
    "node_path={} points={} max_y_path={:.3f} min_blocked_distance={:.3f} "
    "final=({:.3f},{:.3f}) goal_error={:.3f} max_x={:.3f}".format(
        last_summary.get("node_path"),
        len(last_path),
        max_y_path,
        min_blocked_distance,
        final_x,
        final_y,
        goal_error,
        max_x,
    )
)

failures = []
if not last_summary.get("detour"):
    failures.append(f"global plan did not use semantic detour: {last_summary}")
if max_y_path < 0.8:
    failures.append(f"global path did not route around semantic obstacle: max_y={max_y_path:.3f}")
if min_blocked_distance < 0.4:
    failures.append(f"global path passed too close to blocked semantic cell: {min_blocked_distance:.3f}")
if max_x < 7.0:
    failures.append(f"vehicle did not make goal progress: max_x={max_x:.3f}")
if goal_error > 1.2:
    failures.append(f"vehicle did not arrive within tolerance: goal_error={goal_error:.3f}")
if failures:
    raise SystemExit("; ".join(failures))
PY

  kill -INT "$launch_pid" >/dev/null 2>&1 || true
  wait "$launch_pid" || true
'
