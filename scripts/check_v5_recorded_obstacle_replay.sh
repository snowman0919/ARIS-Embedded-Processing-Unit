#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
aris_load_env
export ROS_DOMAIN_ID="${ARIS_V5_RECORDED_OBSTACLE_ROS_DOMAIN_ID:-155}"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
bag_dir="${ARIS_LOGS}/bags/v5_recorded_obstacle_${timestamp}"
container_bag_dir="${bag_dir/#$ARIS_LOGS/\/aris\/logs}"

aris_compose run --rm \
  -e ARIS_V5_RECORDED_OBSTACLE_BAG_DIR="$container_bag_dir" \
  aris-ros2-dev bash -lc '
  set -euo pipefail
  colcon build --symlink-install
  set +u
  source install/setup.bash
  set -u

  bag_dir="${ARIS_V5_RECORDED_OBSTACLE_BAG_DIR:?}"
  record_log=/tmp/aris_v5_recorded_obstacle_record.log
  publish_log=/tmp/aris_v5_recorded_obstacle_publish.log

  mkdir -p "$(dirname "$bag_dir")"
  rm -rf "$bag_dir"

  timeout -k 8s -s INT 10s ros2 bag record -s mcap -o "$bag_dir" /scan_cloud \
    >"$record_log" 2>&1 &
  record_pid=$!
  sleep 1

  code=0
  python3 - <<'"'"'PY'"'"' >"$publish_log" 2>&1 || code=$?
import time

import rclpy
from sensor_msgs.msg import PointCloud2
from sensor_msgs_py import point_cloud2
from std_msgs.msg import Header


def obstacle_points(distance_m: float) -> list[tuple[float, float, float]]:
    return [
        (distance_m + 0.00, -0.20, 0.0),
        (distance_m + 0.05, 0.00, 0.0),
        (distance_m + 0.10, 0.20, 0.0),
        (distance_m + 0.15, -0.10, 0.1),
        (distance_m + 0.20, 0.10, 0.1),
        (distance_m + 0.25, 0.00, -0.1),
    ]


rclpy.init()
node = rclpy.create_node("aris_v5_recorded_obstacle_cloud_source")
pub = node.create_publisher(PointCloud2, "/scan_cloud", 10)

start = time.monotonic()
published = 0
while time.monotonic() - start < 6.0:
    elapsed = time.monotonic() - start
    distance = 3.0 if elapsed < 3.0 else 1.0
    header = Header()
    header.stamp = node.get_clock().now().to_msg()
    header.frame_id = "lidar_link"
    cloud = point_cloud2.create_cloud_xyz32(header, obstacle_points(distance))
    pub.publish(cloud)
    published += 1
    rclpy.spin_once(node, timeout_sec=0.02)
    time.sleep(0.1)

node.destroy_node()
rclpy.shutdown()
print(f"v5_recorded_obstacle_clouds_published={published}")
PY

  record_status=0
  wait "$record_pid" || record_status=$?
  if [[ "$record_status" != "0" && "$record_status" != "124" && "$record_status" != "130" ]]; then
    code="$record_status"
  fi

  /workspaces/aris/scripts/validate_v2_lidar_bag.py --scan-only "$bag_dir" >>"$publish_log" 2>&1 || code=$?

  if [[ "$code" != "0" ]]; then
    echo "ERROR: V5 recorded obstacle bag creation failed."
    echo "--- record log ---"
    sed -n "1,220p" "$record_log"
    echo "--- publish log ---"
    sed -n "1,220p" "$publish_log"
    [[ -f "$bag_dir/metadata.yaml" ]] && sed -n "1,220p" "$bag_dir/metadata.yaml"
    exit "$code"
  fi

  sed -n "1,160p" "$publish_log"
  printf "v5_recorded_obstacle_bag=%s\n" "$bag_dir"
'

"$(dirname "${BASH_SOURCE[0]}")/check_v5_obstacle_bag_replay.sh" "$bag_dir"
