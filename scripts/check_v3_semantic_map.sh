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

  route_file="/aris/data/routes/v3_semantic_route_$(date +%Y%m%d_%H%M%S).csv"
  launch_log=/tmp/aris_v3_semantic_map_launch.log
  summary_file=/tmp/aris_v3_semantic_map_summary.json
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

  timeout -s INT 20s ros2 launch aris_mapping v3_semantic_map_sim.launch.py \
    route_file:="$route_file" >"$launch_log" 2>&1 &
  launch_pid=$!
  sleep 4

  python3 - <<PY
import json
import time
from pathlib import Path

import rclpy
from std_msgs.msg import String

summaries = []

def on_summary(msg: String) -> None:
    summaries.append(json.loads(msg.data))

rclpy.init()
node = rclpy.create_node("aris_v3_semantic_map_smoke")
node.create_subscription(String, "/aris/mapping/semantic_map", on_summary, 20)

deadline = time.monotonic() + 11.0
while time.monotonic() < deadline:
    rclpy.spin_once(node, timeout_sec=0.1)

node.destroy_node()
rclpy.shutdown()

if not summaries:
    raise SystemExit("no /aris/mapping/semantic_map summaries received")

summary = summaries[-1]
Path("$summary_file").write_text(json.dumps(summary, sort_keys=True) + "\n")
print(json.dumps(summary, sort_keys=True))

failures = []
if summary.get("metric_cells", 0) < 20:
    failures.append(f"metric layer too small: {summary.get('metric_cells')}")
if summary.get("semantic_cells", 0) < 1:
    failures.append("semantic layer did not update")
if summary.get("semantic_updates", 0) < 5:
    failures.append(f"too few semantic updates: {summary.get('semantic_updates')}")
if summary.get("change_events", 0) < 1:
    failures.append("repeat-pass change detection did not trigger")
if summary.get("review_events", 0) < 1:
    failures.append("review policy did not trigger")
if summary.get("blocked_cells", 0) < 1:
    failures.append("traversability layer did not mark a blocked/high-risk cell")
if "debris" not in summary.get("labels", {}):
    failures.append("expected debris label in map summary: " + json.dumps(summary.get("labels", {}), sort_keys=True))
if failures:
    raise SystemExit("; ".join(failures))
PY

  kill -INT "$launch_pid" >/dev/null 2>&1 || true
  wait "$launch_pid" || true
'
