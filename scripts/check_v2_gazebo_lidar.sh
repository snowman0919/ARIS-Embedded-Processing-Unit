#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
aris_load_env
export ROS_DOMAIN_ID="${ARIS_V2_GAZEBO_LIDAR_ROS_DOMAIN_ID:-146}"

aris_compose run --rm aris-ros2-dev bash -lc '
  set -euo pipefail
  colcon build --symlink-install
  set +u
  source install/setup.bash
  set -u

  launch_log=/tmp/aris_v2_gazebo_lidar_launch.log
  probe_log=/tmp/aris_v2_scan_cloud_probe.log
  timeout -s INT 24s ros2 launch aris_localization v2_gazebo_lidar.launch.py \
    >"$launch_log" 2>&1 &
  launch_pid=$!
  sleep 4

  code=0
  python3 - <<PY >"$probe_log" 2>&1 || code=$?
import math
import struct
import time

import rclpy
from sensor_msgs.msg import PointCloud2, PointField

clouds = []

def on_cloud(msg: PointCloud2) -> None:
    clouds.append(msg)

rclpy.init()
node = rclpy.create_node("aris_v2_gazebo_lidar_probe")
node.create_subscription(PointCloud2, "/scan_cloud", on_cloud, 10)

deadline = time.monotonic() + 12.0
while time.monotonic() < deadline and not clouds:
    rclpy.spin_once(node, timeout_sec=0.1)

node.destroy_node()
rclpy.shutdown()

if not clouds:
    raise SystemExit("no /scan_cloud PointCloud2 sample received")

msg = clouds[-1]
fields = {field.name: field for field in msg.fields}
failures = []
if msg.header.frame_id != "lidar_link":
    failures.append(f"frame_id={msg.header.frame_id!r}, expected lidar_link")
if msg.height != 1:
    failures.append(f"height={msg.height}, expected 1")
if msg.width < 100:
    failures.append(f"width={msg.width}, expected >= 100")
if msg.is_bigendian:
    failures.append("cloud must be little-endian")
if msg.point_step != 24:
    failures.append(f"point_step={msg.point_step}, expected 24")
if msg.row_step != msg.width * msg.point_step:
    failures.append(f"row_step={msg.row_step}, expected {msg.width * msg.point_step}")
if len(msg.data) != msg.row_step * msg.height:
    failures.append(f"data length={len(msg.data)}, expected {msg.row_step * msg.height}")

expected = {
    "x": (0, PointField.FLOAT32),
    "y": (4, PointField.FLOAT32),
    "z": (8, PointField.FLOAT32),
    "intensity": (12, PointField.FLOAT32),
    "ring": (16, PointField.UINT16),
    "time": (20, PointField.FLOAT32),
}
for name, (offset, datatype) in expected.items():
    field = fields.get(name)
    if field is None:
        failures.append(f"missing field {name}")
        continue
    if field.offset != offset or field.datatype != datatype or field.count != 1:
        failures.append(
            f"field {name} has offset/datatype/count "
            f"{field.offset}/{field.datatype}/{field.count}, expected {offset}/{datatype}/1"
        )

finite_points = 0
rings = set()
times = []
for index in range(min(int(msg.width), 128)):
    offset = index * msg.point_step
    x, y, z, intensity, ring, rel_time = struct.unpack_from("<ffffH2xf", msg.data, offset)
    if all(math.isfinite(value) for value in (x, y, z, intensity, rel_time)):
        finite_points += 1
    rings.add(ring)
    times.append(rel_time)
if finite_points == 0:
    failures.append("no finite sample points")
if not rings or max(rings) > 64:
    failures.append(f"unexpected ring values: {sorted(rings)[:8]}")
if any(value < 0.0 or value > 0.2 for value in times):
    failures.append("relative point time outside expected frame window")

if failures:
    raise SystemExit("; ".join(failures))

print(
    "v2_gazebo_lidar frame={} width={} point_step={} fields={} finite_samples={}".format(
        msg.header.frame_id,
        msg.width,
        msg.point_step,
        sorted(fields),
        finite_points,
    )
)
PY

  kill -INT "$launch_pid" >/dev/null 2>&1 || true
  wait "$launch_pid" || true

  if [[ "$code" != "0" ]]; then
    echo "BLOCKED: no /scan_cloud PointCloud2 sample from Gazebo gpu_lidar."
    echo "The launch log and topic list show whether Gazebo spawn, sensor rendering,"
    echo "raw bridge, or cloud normalization failed."
    echo "--- ROS topics ---"
    ros2 topic list -t | sort || true
    echo "--- Gazebo topics ---"
    gz topic -l | sort || true
    echo "--- launch log ---"
    sed -n "1,220p" "$launch_log"
    echo "--- probe log ---"
    sed -n "1,160p" "$probe_log"
    exit 1
  fi

  sed -n "1,80p" "$probe_log"
'
