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
  snapshot_file="/aris/logs/maps/v3_semantic_map_$(date +%Y%m%d_%H%M%S).json"
  manifest_file="${snapshot_file%.json}.manifest.json"
  compare_file="${snapshot_file%.json}.compare.json"
  launch_log=/tmp/aris_v3_semantic_map_launch.log
  summary_file=/tmp/aris_v3_semantic_map_summary.json
  mkdir -p /aris/data/routes
  mkdir -p /aris/logs/maps
  baseline_snapshot="$(
    find /aris/logs/maps -maxdepth 1 -type f -name "v3_semantic_map_*.json" \
      ! -name "*.manifest.json" ! -name "*.compare.json" ! -name "*.v6_review.json" \
      -printf "%T@ %p\n" 2>/dev/null \
      | sort -n \
      | tail -1 \
      | cut -d" " -f2-
  )"

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
    route_file:="$route_file" snapshot_file:="$snapshot_file" >"$launch_log" 2>&1 &
  launch_pid=$!
  cleanup_launch() {
    kill -INT "$launch_pid" >/dev/null 2>&1 || true
    wait "$launch_pid" || true
  }
  trap cleanup_launch EXIT
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
if summary.get("route_nodes", 0) < 40:
    failures.append(f"route graph has too few nodes: {summary.get('route_nodes')}")
if summary.get("route_edges", 0) < 39:
    failures.append(f"route graph has too few edges: {summary.get('route_edges')}")
if "debris" not in summary.get("labels", {}):
    failures.append("expected debris label in map summary: " + json.dumps(summary.get("labels", {}), sort_keys=True))
if failures:
    raise SystemExit("; ".join(failures))
PY

  cleanup_launch
  trap - EXIT

  python3 - <<PY
import json
from pathlib import Path

from aris_mapping.semantic_map import SemanticHDMap

snapshot_path = Path("$snapshot_file")
summary = json.loads(Path("$summary_file").read_text())
if not snapshot_path.exists():
    raise SystemExit(f"semantic map snapshot was not written: {snapshot_path}")

snapshot = json.loads(snapshot_path.read_text())
loaded = SemanticHDMap.load_snapshot(snapshot_path)
failures = []
if snapshot.get("schema_version") != 1:
    failures.append(f"schema_version={snapshot.get('schema_version')!r}, expected 1")
if snapshot.get("map_id") != "aris-v3-sim":
    failures.append(f"map_id={snapshot.get('map_id')!r}, expected aris-v3-sim")
if len(loaded.metric_cells) < summary.get("metric_cells", 0):
    failures.append(
        f"snapshot metric_cells={len(loaded.metric_cells)} summary={summary.get('metric_cells')}"
    )
semantic_cells = sum(1 for state in loaded.cells.values() if state.labels)
if semantic_cells < summary.get("semantic_cells", 0):
    failures.append(f"snapshot semantic_cells={semantic_cells} summary={summary.get('semantic_cells')}")
if len(loaded.route_nodes) < 40:
    failures.append(f"snapshot route_nodes={len(loaded.route_nodes)}, expected >= 40")
if len(loaded.route_edges) < 39:
    failures.append(f"snapshot route_edges={len(loaded.route_edges)}, expected >= 39")
if not loaded.review_queue:
    failures.append("snapshot review_queue is empty")
if not any("debris" in state.labels for state in loaded.cells.values()):
    failures.append("snapshot has no debris label")
if not any(state.traversability >= 0.8 for state in loaded.cells.values()):
    failures.append("snapshot has no high-risk traversability cell")
if failures:
    raise SystemExit("; ".join(failures))
print(
    "v3_semantic_map_snapshot path={} metric_cells={} semantic_cells={} "
    "route_nodes={} route_edges={} review_queue={}".format(
        snapshot_path,
        len(loaded.metric_cells),
        semantic_cells,
        len(loaded.route_nodes),
        len(loaded.route_edges),
        len(loaded.review_queue),
    )
)
PY

  /workspaces/aris/scripts/validate_semantic_map_snapshot.py \
    "$snapshot_file" \
    --manifest-out "$manifest_file" \
    --min-metric-cells 40 \
    --min-semantic-cells 1 \
    --min-route-nodes 40 \
    --min-route-edges 39 \
    --min-review-queue 1 \
    --min-high-risk-cells 1
  echo "v3_semantic_map_manifest path=$manifest_file"

  if [[ -n "$baseline_snapshot" && -f "$baseline_snapshot" ]]; then
    /workspaces/aris/scripts/compare_semantic_map_snapshots.py \
      "$baseline_snapshot" \
      "$snapshot_file" \
      --report-out "$compare_file" \
      --min-metric-overlap 0.70 \
      --min-route-overlap 0.95 \
      --max-label-changes 2 \
      --max-high-risk-delta 2 \
      --max-review-queue-delta 8
    echo "v3_semantic_map_compare path=$compare_file baseline=$baseline_snapshot"
  else
    echo "v3_semantic_map_compare skipped=no-baseline"
  fi
'
