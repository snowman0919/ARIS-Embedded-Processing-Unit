#!/usr/bin/env bash
set -euo pipefail

# End-to-end headless pipeline smoke:
# SemanticHDMap artifact -> Route Graph -> LiDAR localization -> goal plan -> /cmd_drive.

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
aris_load_env
export ROS_DOMAIN_ID="${ARIS_CORE_PIPELINE_ROS_DOMAIN_ID:-146}"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
report_dir="${ARIS_LOGS}/pipeline"
map_dir="${ARIS_LOGS}/maps"
report_file="${report_dir}/core_pipeline_flow_${timestamp}.json"
snapshot_file="${map_dir}/core_pipeline_semantic_map_${timestamp}.json"
manifest_file="${map_dir}/core_pipeline_semantic_map_${timestamp}.manifest.json"
mkdir -p "$report_dir" "$map_dir"

container_report_file="${report_file/#$ARIS_LOGS/\/aris\/logs}"
container_snapshot_file="${snapshot_file/#$ARIS_LOGS/\/aris\/logs}"
container_manifest_file="${manifest_file/#$ARIS_LOGS/\/aris\/logs}"

aris_compose run --rm \
  -e ARIS_CORE_PIPELINE_REPORT="$container_report_file" \
  -e ARIS_CORE_PIPELINE_SNAPSHOT="$container_snapshot_file" \
  -e ARIS_CORE_PIPELINE_MANIFEST="$container_manifest_file" \
  aris-ros2-dev bash -lc '
  set -euo pipefail
  colcon build --symlink-install
  set +u
  source install/setup.bash
  set -u

  python3 - <<PY
import os

from aris_mapping.semantic_map import RouteEdge, RouteNode, SemanticHDMap, SemanticObservation
from aris_planning.route_graph import build_bidirectional_edges

hd_map = SemanticHDMap(resolution_m=0.5)
for node in [
    RouteNode("start", 0.0, 0.0),
    RouteNode("approach", 3.0, 0.0),
    RouteNode("blocked", 6.0, 0.0),
    RouteNode("goal", 9.0, 0.0),
    RouteNode("detour_a", 3.0, 1.2),
    RouteNode("detour_b", 6.0, 1.2),
    RouteNode("detour_c", 9.0, 1.2),
]:
    hd_map.add_route_node(node)
for edge in build_bidirectional_edges(
    [
        RouteEdge("start", "approach", 3.0),
        RouteEdge("approach", "blocked", 3.0),
        RouteEdge("blocked", "goal", 3.0),
        RouteEdge("approach", "detour_a", 1.2),
        RouteEdge("detour_a", "detour_b", 3.0),
        RouteEdge("detour_b", "detour_c", 3.0),
        RouteEdge("detour_c", "goal", 1.2),
    ]
):
    hd_map.add_route_edge(edge)
hd_map.apply_semantic_observation(
    SemanticObservation(
        x=6.0,
        y=0.0,
        label="debris",
        confidence=0.95,
        source="core_pipeline_smoke",
    )
)
hd_map.save_snapshot(os.environ["ARIS_CORE_PIPELINE_SNAPSHOT"], map_id="aris-core-pipeline-map")
print("core_pipeline_semantic_map path={}".format(os.environ["ARIS_CORE_PIPELINE_SNAPSHOT"]))
PY

  /workspaces/aris/scripts/validate_semantic_map_snapshot.py \
    "$ARIS_CORE_PIPELINE_SNAPSHOT" \
    --manifest-out "$ARIS_CORE_PIPELINE_MANIFEST" \
    --min-metric-cells 1 \
    --min-semantic-cells 1 \
    --min-route-nodes 7 \
    --min-route-edges 14 \
    --min-review-queue 0 \
    --min-high-risk-cells 1

  launch_log=/tmp/aris_core_pipeline_flow_launch.log
  timeout -s INT 30s ros2 launch aris_planning v4_goal_nav_sim.launch.py \
    use_demo_graph:=false \
    semantic_map_file:="$ARIS_CORE_PIPELINE_SNAPSHOT" \
    enable_dynamic_obstacles:=false \
    >"$launch_log" 2>&1 &
  launch_pid=$!
  sleep 4

  python3 - <<PY
import json
import math
import os
from pathlib import Path
import time

import rclpy
from ackermann_msgs.msg import AckermannDriveStamped
from geometry_msgs.msg import PoseArray
from nav_msgs.msg import Odometry
from sensor_msgs.msg import PointCloud2
from std_msgs.msg import String

cmd_samples = []
filtered = []
truth = []
paths = []
summaries = []
cloud_samples = 0

def stamp_s(msg):
    return msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9

def on_cmd(msg):
    cmd_samples.append((time.monotonic(), float(msg.drive.speed), float(msg.drive.steering_angle)))

def on_filtered(msg):
    filtered.append((stamp_s(msg), float(msg.pose.pose.position.x), float(msg.pose.pose.position.y)))

def on_truth(msg):
    truth.append((stamp_s(msg), float(msg.pose.pose.position.x), float(msg.pose.pose.position.y)))

def on_path(msg):
    paths.append([(float(pose.position.x), float(pose.position.y)) for pose in msg.poses])

def on_summary(msg):
    summaries.append(json.loads(msg.data))

def on_cloud(msg):
    global cloud_samples
    if msg.width > 0:
        cloud_samples += 1

rclpy.init()
node = rclpy.create_node("aris_core_pipeline_flow_smoke")
node.create_subscription(AckermannDriveStamped, "/cmd_drive", on_cmd, 20)
node.create_subscription(Odometry, "/odometry/filtered", on_filtered, 20)
node.create_subscription(Odometry, "/aris/sim/ground_truth", on_truth, 20)
node.create_subscription(PoseArray, "/global_path", on_path, 20)
node.create_subscription(String, "/aris/planning/global_plan", on_summary, 20)
node.create_subscription(PointCloud2, "/scan_cloud", on_cloud, 20)

deadline = time.monotonic() + 18.0
while time.monotonic() < deadline:
    rclpy.spin_once(node, timeout_sec=0.1)

node.destroy_node()
rclpy.shutdown()

failures = []
if not paths:
    failures.append("no /global_path samples")
if not summaries:
    failures.append("no /aris/planning/global_plan summaries")
if not filtered:
    failures.append("no /odometry/filtered samples")
if not truth:
    failures.append("no /aris/sim/ground_truth samples")
if not cmd_samples:
    failures.append("no /cmd_drive samples")
if cloud_samples < 5:
    failures.append(f"too few /scan_cloud samples: {cloud_samples}")

last_path = max(paths, key=lambda path: max((y for _, y in path), default=0.0)) if paths else []
last_summary = max(
    summaries,
    key=lambda item: (bool(item.get("detour")), len(item.get("node_path") or [])),
) if summaries else {}
max_y_path = max((y for path in paths for _, y in path), default=0.0)
min_blocked_distance = min(
    (math.hypot(x - 6.0, y) for path in paths for x, y in path),
    default=math.inf,
)
max_cmd_speed = max((speed for _, speed, _ in cmd_samples), default=0.0)
max_x = max((x for _, x, _ in truth), default=0.0)
final_x = truth[-1][1] if truth else 0.0
final_y = truth[-1][2] if truth else 0.0
goal_error = math.hypot(final_x - 9.0, final_y)

if last_summary.get("map_source") != os.environ["ARIS_CORE_PIPELINE_SNAPSHOT"]:
    failures.append(
        "global planner did not report semantic map source: {}".format(
            last_summary.get("map_source")
        )
    )
if not last_summary.get("detour"):
    failures.append(f"global plan did not use semantic detour: {last_summary}")
if max_y_path < 0.8:
    failures.append(f"global path did not route around semantic obstacle: max_y={max_y_path:.3f}")
if min_blocked_distance < 0.4:
    failures.append(f"global path passed too close to blocked cell: {min_blocked_distance:.3f}")
if max_cmd_speed < 0.5:
    failures.append(f"planner did not publish moving /cmd_drive: max_speed={max_cmd_speed:.3f}")
if max_x < 7.0:
    failures.append(f"vehicle did not make goal progress: max_x={max_x:.3f}")
if goal_error > 1.3:
    failures.append(f"vehicle did not arrive within tolerance: goal_error={goal_error:.3f}")

report = {
    "artifact_type": "aris_core_pipeline_flow_report",
    "schema_version": 1,
    "valid": not failures,
    "failures": failures,
    "semantic_map_snapshot": os.environ["ARIS_CORE_PIPELINE_SNAPSHOT"],
    "semantic_map_manifest": os.environ["ARIS_CORE_PIPELINE_MANIFEST"],
    "stages": {
        "mapping": {"passed": Path(os.environ["ARIS_CORE_PIPELINE_SNAPSHOT"]).exists()},
        "semantic_hd_map": {"passed": Path(os.environ["ARIS_CORE_PIPELINE_MANIFEST"]).exists()},
        "route_graph": {
            "passed": bool(last_summary.get("detour")),
            "node_path": last_summary.get("node_path"),
            "route_nodes": last_summary.get("route_nodes"),
            "route_edges": last_summary.get("route_edges"),
            "map_source": last_summary.get("map_source"),
        },
        "localization": {
            "passed": bool(filtered) and cloud_samples >= 5,
            "filtered_samples": len(filtered),
            "scan_cloud_samples": cloud_samples,
        },
        "goal_based_planning": {
            "passed": bool(paths) and max_y_path >= 0.8,
            "global_path_points": len(last_path),
            "max_y_path": max_y_path,
            "min_blocked_distance": min_blocked_distance,
        },
        "autonomous_driving": {
            "passed": bool(cmd_samples) and max_cmd_speed >= 0.5 and max_x >= 7.0 and goal_error <= 1.3,
            "cmd_samples": len(cmd_samples),
            "max_cmd_speed_mps": max_cmd_speed,
            "max_x_m": max_x,
            "final_pose": {"x": final_x, "y": final_y},
            "goal_error_m": goal_error,
        },
    },
}
Path(os.environ["ARIS_CORE_PIPELINE_REPORT"]).write_text(
    json.dumps(report, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
print(
    "core_pipeline_flow_report path={} valid={} node_path={} goal_error={:.3f} "
    "scan_cloud_samples={} cmd_samples={}".format(
        os.environ["ARIS_CORE_PIPELINE_REPORT"],
        report["valid"],
        last_summary.get("node_path"),
        goal_error,
        cloud_samples,
        len(cmd_samples),
    )
)
if failures:
    raise SystemExit("; ".join(failures))
PY

  kill -INT "$launch_pid" >/dev/null 2>&1 || true
  wait "$launch_pid" || true
'

ln -sf "$report_file" "${report_dir}/latest_core_pipeline_flow.json"
