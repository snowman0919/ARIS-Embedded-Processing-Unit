#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
aris_load_env
export ROS_DOMAIN_ID="${ARIS_V5_OBSTACLE_BAG_REPLAY_ROS_DOMAIN_ID:-154}"

if [[ $# -ne 1 ]]; then
  printf 'Usage: %s <bag-dir-or-metadata.yaml>\n' "$0" >&2
  exit 2
fi

bag_input="$1"
if [[ ! -e "$bag_input" ]]; then
  aris_die "Bag path does not exist: $bag_input"
fi

bag_path="$(realpath "$bag_input")"
if [[ -f "$bag_path" ]]; then
  if [[ "$(basename "$bag_path")" != "metadata.yaml" ]]; then
    aris_die "File input must be a rosbag metadata.yaml: $bag_path"
  fi
  bag_path="$(dirname "$bag_path")"
fi

python3 "$(dirname "${BASH_SOURCE[0]}")/validate_v2_lidar_bag.py" \
  --scan-only \
  --min-topic /scan_cloud="${ARIS_V5_OBSTACLE_REPLAY_MIN_CLOUD_SAMPLES:-10}" \
  "$bag_path"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
report_dir="${ARIS_LOGS}/obstacles"
report_file="${report_dir}/v5_obstacle_bag_replay_${timestamp}.json"
mkdir -p "$report_dir"
container_report_file="${report_file/#$ARIS_LOGS/\/aris\/logs}"

aris_compose run --rm \
  -e ARIS_REPLAY_BAG_PATH="$bag_path" \
  -e ARIS_V5_OBSTACLE_BAG_REPLAY_REPORT="$container_report_file" \
  -e ARIS_REPLAY_WAIT_S="${ARIS_REPLAY_WAIT_S:-20.0}" \
  -e ARIS_V5_OBSTACLE_REPLAY_MIN_CLOUD_SAMPLES="${ARIS_V5_OBSTACLE_REPLAY_MIN_CLOUD_SAMPLES:-10}" \
  -e ARIS_V5_OBSTACLE_REPLAY_MIN_ADVISORIES="${ARIS_V5_OBSTACLE_REPLAY_MIN_ADVISORIES:-1}" \
  -e ARIS_V5_OBSTACLE_REPLAY_REQUIRED_ACTIONS="${ARIS_V5_OBSTACLE_REPLAY_REQUIRED_ACTIONS:-detour,slow,stop}" \
  -v "$bag_path:$bag_path:ro" \
  aris-ros2-dev bash -lc '
    set -euo pipefail

    bag_path="${ARIS_REPLAY_BAG_PATH:?}"
    report_path="${ARIS_V5_OBSTACLE_BAG_REPLAY_REPORT:?}"
    launch_log=/tmp/aris_v5_obstacle_bag_replay_detector.log
    play_log=/tmp/aris_v5_obstacle_bag_replay_play.log
    probe_log=/tmp/aris_v5_obstacle_bag_replay_probe.log

    colcon build --symlink-install
    set +u
    source install/setup.bash
    set -u

    ros2 run aris_perception dynamic_obstacle_node \
      >"$launch_log" 2>&1 &
    detector_pid=$!

    code=0
    python3 - <<'"'"'PY'"'"' >"$probe_log" 2>&1 &
import json
import os
from pathlib import Path
import time

import rclpy
from sensor_msgs.msg import PointCloud2
from std_msgs.msg import String


wait_s = float(os.environ.get("ARIS_REPLAY_WAIT_S", "20.0"))
min_clouds = int(os.environ.get("ARIS_V5_OBSTACLE_REPLAY_MIN_CLOUD_SAMPLES", "10"))
min_advisories = int(os.environ.get("ARIS_V5_OBSTACLE_REPLAY_MIN_ADVISORIES", "1"))
required_actions = [
    action.strip()
    for action in os.environ.get("ARIS_V5_OBSTACLE_REPLAY_REQUIRED_ACTIONS", "detour,slow,stop").split(",")
    if action.strip()
]
report_path = Path(os.environ["ARIS_V5_OBSTACLE_BAG_REPLAY_REPORT"])
bag_path = os.environ["ARIS_REPLAY_BAG_PATH"]

cloud_samples = []
advisories = []
invalid_advisories = []


def on_cloud(msg: PointCloud2) -> None:
    cloud_samples.append(
        {
            "frame_id": msg.header.frame_id,
            "width": int(msg.width),
            "height": int(msg.height),
            "point_step": int(msg.point_step),
            "row_step": int(msg.row_step),
        }
    )


def on_advisory(msg: String) -> None:
    try:
        data = json.loads(msg.data)
    except json.JSONDecodeError as exc:
        invalid_advisories.append(f"invalid JSON advisory: {exc}")
        return
    if not isinstance(data, dict):
        invalid_advisories.append("advisory is not a JSON object")
        return
    advisories.append(data)


rclpy.init()
node = rclpy.create_node("aris_v5_obstacle_bag_replay_score")
node.create_subscription(PointCloud2, "/scan_cloud", on_cloud, 20)
node.create_subscription(String, "/aris/perception/dynamic_obstacle", on_advisory, 20)

start = time.monotonic()
while time.monotonic() - start < wait_s:
    rclpy.spin_once(node, timeout_sec=0.1)

node.destroy_node()
rclpy.shutdown()

action_counts = {}
closest_distances = []
track_ages = []
for advisory in advisories:
    action = str(advisory.get("action", ""))
    action_counts[action] = action_counts.get(action, 0) + 1
    closest = advisory.get("closest_distance_m")
    if closest is not None:
        closest_distances.append(float(closest))
    track_ages.append(int(advisory.get("track_age", 0) or 0))

meaningful_actions = {
    action: count
    for action, count in action_counts.items()
    if action in required_actions and count > 0
}
failures = []
if len(cloud_samples) < min_clouds:
    failures.append(f"too few /scan_cloud samples: {len(cloud_samples)}")
if len(advisories) < min_advisories:
    failures.append(f"too few dynamic obstacle advisories: {len(advisories)}")
if required_actions and not meaningful_actions:
    failures.append(f"no required obstacle actions observed: required={required_actions}")
if invalid_advisories:
    failures.extend(invalid_advisories)

report = {
    "artifact_type": "aris_v5_obstacle_bag_replay_report",
    "schema_version": 1,
    "valid": not failures,
    "bag_path": bag_path,
    "failures": failures,
    "thresholds": {
        "min_cloud_samples": min_clouds,
        "min_advisories": min_advisories,
        "required_actions": required_actions,
    },
    "metrics": {
        "cloud_samples": len(cloud_samples),
        "advisory_samples": len(advisories),
        "action_counts": action_counts,
        "meaningful_actions": meaningful_actions,
        "min_closest_distance_m": min(closest_distances) if closest_distances else None,
        "max_track_age": max(track_ages) if track_ages else 0,
        "cloud_frames": sorted({sample["frame_id"] for sample in cloud_samples}),
    },
}
report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

print(
    "v5_obstacle_bag_replay_report path={} valid={} cloud_samples={} "
    "advisory_samples={} action_counts={}".format(
        report_path,
        report["valid"],
        len(cloud_samples),
        len(advisories),
        action_counts,
    )
)
if failures:
    raise SystemExit("; ".join(failures))
PY
    probe_pid=$!

    sleep 2
    timeout -s INT "$(( ${ARIS_REPLAY_WAIT_S%.*} + 6 ))s" ros2 bag play "$bag_path" \
      >"$play_log" 2>&1 || code=$?

    wait "$probe_pid" || code=$?

    kill -INT "$detector_pid" >/dev/null 2>&1 || true
    for _ in $(seq 1 20); do
      if ! kill -0 "$detector_pid" >/dev/null 2>&1; then
        break
      fi
      sleep 0.1
    done
    if kill -0 "$detector_pid" >/dev/null 2>&1; then
      kill -TERM "$detector_pid" >/dev/null 2>&1 || true
    fi
    for _ in $(seq 1 20); do
      if ! kill -0 "$detector_pid" >/dev/null 2>&1; then
        break
      fi
      sleep 0.1
    done
    if kill -0 "$detector_pid" >/dev/null 2>&1; then
      kill -KILL "$detector_pid" >/dev/null 2>&1 || true
    fi
    wait "$detector_pid" >/dev/null 2>&1 || true

    if [[ "$code" != "0" ]]; then
      echo "ERROR: V5 obstacle bag replay scoring failed."
      echo "--- detector log ---"
      sed -n "1,220p" "$launch_log"
      echo "--- play log ---"
      sed -n "1,220p" "$play_log"
      echo "--- probe log ---"
      sed -n "1,220p" "$probe_log"
      exit "$code"
    fi

    sed -n "1,160p" "$probe_log"
  '
