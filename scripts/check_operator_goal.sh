#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
aris_load_env
export ROS_DOMAIN_ID="${ARIS_OPERATOR_SMOKE_ROS_DOMAIN_ID:-143}"

aris_compose run --rm aris-ros2-dev bash -lc '
  set -euo pipefail
  colcon build --symlink-install
  set +u
  source install/setup.bash
  set -u

  launch_log=/tmp/aris_operator_goal_launch.log
  timeout -s INT 20s ros2 launch aris_planning v4_goal_nav_sim.launch.py \
    >"$launch_log" 2>&1 &
  launch_pid=$!
  sleep 5

  python3 - <<PY
import json
import time

import rclpy
from std_msgs.msg import String

summaries = []
events = []

def on_summary(msg: String) -> None:
    summaries.append(json.loads(msg.data))

def on_event(msg: String) -> None:
    events.append(json.loads(msg.data))

rclpy.init()
node = rclpy.create_node("aris_operator_goal_smoke")
pub = node.create_publisher(String, "/aris/operator/goal_request", 10)
node.create_subscription(String, "/aris/planning/global_plan", on_summary, 10)
node.create_subscription(String, "/aris/operator/events", on_event, 10)

deadline = time.monotonic() + 8.0
while time.monotonic() < deadline and (not summaries or pub.get_subscription_count() < 1):
    rclpy.spin_once(node, timeout_sec=0.1)

msg = String()
msg.data = json.dumps({"x": 3.0, "y": 1.2, "source": "smoke"})

deadline = time.monotonic() + 12.0
accepted = False
updated = False
while time.monotonic() < deadline:
    pub.publish(msg)
    rclpy.spin_once(node, timeout_sec=0.1)
    accepted = accepted or any(event.get("event") == "goal_accepted" for event in events)
    updated = updated or any(summary.get("goal_x") == 3.0 and summary.get("goal_y") == 1.2 for summary in summaries)
    if accepted and updated:
        break

node.destroy_node()
rclpy.shutdown()

if not accepted:
    raise SystemExit(f"operator API did not acknowledge goal: events={events}")
if not updated:
    raise SystemExit(f"global planner did not update goal from operator request: summaries={summaries[-3:]}")
print(f"operator_goal accepted={accepted} updated={updated} latest_summary={summaries[-1]}")
PY

  kill -INT "$launch_pid" >/dev/null 2>&1 || true
  wait "$launch_pid" || true
'
