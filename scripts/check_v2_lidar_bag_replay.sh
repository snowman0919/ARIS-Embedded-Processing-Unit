#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
aris_load_env
export ROS_DOMAIN_ID="${ARIS_V2_LIDAR_BAG_REPLAY_ROS_DOMAIN_ID:-153}"

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

python3 "$(dirname "${BASH_SOURCE[0]}")/validate_v2_lidar_bag.py" "$bag_path"

aris_compose run --rm \
  -e ARIS_REPLAY_BAG_PATH="$bag_path" \
  -e ARIS_REPLAY_WAIT_S="${ARIS_REPLAY_WAIT_S:-20.0}" \
  -e ARIS_REPLAY_MIN_TOPIC_SAMPLES="${ARIS_REPLAY_MIN_TOPIC_SAMPLES:-5}" \
  -e ARIS_REPLAY_MIN_DELTA_X="${ARIS_REPLAY_MIN_DELTA_X:-0.20}" \
  -e ARIS_REPLAY_MAX_FINAL_X_GAP="${ARIS_REPLAY_MAX_FINAL_X_GAP:-0.50}" \
  -e ARIS_REPLAY_MAX_FINAL_Y_GAP="${ARIS_REPLAY_MAX_FINAL_Y_GAP:-0.35}" \
  -v "$bag_path:$bag_path:ro" \
  aris-ros2-dev bash -lc '
    set -euo pipefail

    bag_path="${ARIS_REPLAY_BAG_PATH:?}"
    play_log=/tmp/aris_v2_lidar_bag_replay_play.log
    probe_log=/tmp/aris_v2_lidar_bag_replay_probe.log

    code=0
    python3 - <<'"'"'PY'"'"' >"$probe_log" 2>&1 &
import os
import time

from ackermann_msgs.msg import AckermannDriveStamped
from nav_msgs.msg import Odometry
import rclpy
from sensor_msgs.msg import PointCloud2
from tf2_msgs.msg import TFMessage


wait_s = float(os.environ.get("ARIS_REPLAY_WAIT_S", "20.0"))
min_samples = int(os.environ.get("ARIS_REPLAY_MIN_TOPIC_SAMPLES", "5"))
min_delta_x = float(os.environ.get("ARIS_REPLAY_MIN_DELTA_X", "0.20"))
max_final_x_gap = float(os.environ.get("ARIS_REPLAY_MAX_FINAL_X_GAP", "0.50"))
max_final_y_gap = float(os.environ.get("ARIS_REPLAY_MAX_FINAL_Y_GAP", "0.35"))

cmd = []
clouds = []
gazebo = []
filtered = []
tf_messages = []
tf_children = set()


def on_cmd(msg: AckermannDriveStamped) -> None:
    cmd.append(msg)


def on_cloud(msg: PointCloud2) -> None:
    clouds.append(msg)


def on_gazebo(msg: Odometry) -> None:
    gazebo.append(msg)


def on_filtered(msg: Odometry) -> None:
    filtered.append(msg)


def on_tf(msg: TFMessage) -> None:
    tf_messages.append(msg)
    for transform in msg.transforms:
        if transform.child_frame_id:
            tf_children.add(transform.child_frame_id)


rclpy.init()
node = rclpy.create_node("aris_v2_lidar_bag_replay_score")
node.create_subscription(AckermannDriveStamped, "/cmd_drive", on_cmd, 10)
node.create_subscription(PointCloud2, "/scan_cloud", on_cloud, 10)
node.create_subscription(Odometry, "/gazebo/odom", on_gazebo, 10)
node.create_subscription(Odometry, "/odometry/filtered", on_filtered, 10)
node.create_subscription(TFMessage, "/tf", on_tf, 10)

start = time.monotonic()
while time.monotonic() - start < wait_s:
    rclpy.spin_once(node, timeout_sec=0.1)

node.destroy_node()
rclpy.shutdown()

failures = []
if len(cmd) < 1:
    failures.append("no /cmd_drive replay samples")
if len(clouds) < min_samples:
    failures.append(f"too few /scan_cloud replay samples: {len(clouds)}")
if len(gazebo) < min_samples:
    failures.append(f"too few /gazebo/odom replay samples: {len(gazebo)}")
if len(filtered) < min_samples:
    failures.append(f"too few /odometry/filtered replay samples: {len(filtered)}")
if len(tf_messages) < 1:
    failures.append("no /tf replay samples")
if clouds and clouds[-1].header.frame_id != "lidar_link":
    failures.append(f"cloud frame={clouds[-1].header.frame_id!r}, expected lidar_link")

if gazebo and filtered:
    gazebo_first = gazebo[0].pose.pose.position
    gazebo_last = gazebo[-1].pose.pose.position
    filtered_first = filtered[0].pose.pose.position
    filtered_last = filtered[-1].pose.pose.position
    gazebo_delta_x = float(gazebo_last.x - gazebo_first.x)
    filtered_delta_x = float(filtered_last.x - filtered_first.x)
    final_x_gap = abs(float(filtered_last.x - gazebo_last.x))
    final_y_gap = abs(float(filtered_last.y - gazebo_last.y))

    if gazebo_delta_x < min_delta_x:
        failures.append(f"Gazebo odom replay did not move far enough: delta_x={gazebo_delta_x:.3f}")
    if filtered_delta_x < min_delta_x:
        failures.append(f"filtered replay did not move far enough: delta_x={filtered_delta_x:.3f}")
    if final_x_gap > max_final_x_gap:
        failures.append(f"filtered/Gazebo replay final x gap too high: {final_x_gap:.3f}")
    if final_y_gap > max_final_y_gap:
        failures.append(f"filtered/Gazebo replay final y gap too high: {final_y_gap:.3f}")
else:
    gazebo_delta_x = filtered_delta_x = final_x_gap = final_y_gap = 0.0

moving_cmds = [sample.drive.speed for sample in cmd if abs(float(sample.drive.speed)) > 0.01]
if cmd and not moving_cmds:
    failures.append("no moving /cmd_drive speed samples")

if failures:
    raise SystemExit("; ".join(failures))

print(
    "v2_lidar_bag_replay_score cmd_samples={} cloud_samples={} gazebo_samples={} "
    "filtered_samples={} tf_samples={} tf_children={} gazebo_delta_x={:.3f} "
    "filtered_delta_x={:.3f} final_gap=({:.3f},{:.3f})".format(
        len(cmd),
        len(clouds),
        len(gazebo),
        len(filtered),
        len(tf_messages),
        sorted(tf_children)[:8],
        gazebo_delta_x,
        filtered_delta_x,
        final_x_gap,
        final_y_gap,
    )
)
PY
    probe_pid=$!

    sleep 1
    timeout -s INT "$(( ${ARIS_REPLAY_WAIT_S%.*} + 6 ))s" ros2 bag play "$bag_path" \
      >"$play_log" 2>&1 || code=$?

    wait "$probe_pid" || code=$?

    if [[ "$code" != "0" ]]; then
      echo "ERROR: V2 LiDAR bag replay scoring failed."
      echo "--- play log ---"
      sed -n "1,220p" "$play_log"
      echo "--- probe log ---"
      sed -n "1,220p" "$probe_log"
      exit "$code"
    fi

    sed -n "1,160p" "$probe_log"
  '
