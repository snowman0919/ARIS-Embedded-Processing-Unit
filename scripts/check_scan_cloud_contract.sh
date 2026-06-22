#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
aris_load_env
export ROS_DOMAIN_ID="${ARIS_SCAN_CLOUD_CONTRACT_ROS_DOMAIN_ID:-144}"

aris_compose run --rm aris-ros2-dev bash -lc '
  set -euo pipefail
  colcon build --symlink-install
  set +u
  source install/setup.bash
  set -u

  sim_log=/tmp/aris_scan_cloud_contract_sim.log
  lidar_log=/tmp/aris_scan_cloud_contract_lidar.log

  timeout -s INT 12s ros2 launch aris_vehicle_sim pure_sim.launch.py >"$sim_log" 2>&1 &
  sim_pid=$!
  sleep 2

  timeout -s INT 10s ros2 launch aris_vehicle_sim lidar_sim.launch.py >"$lidar_log" 2>&1 &
  lidar_pid=$!
  sleep 2

  code=0
  python3 - <<PY || code=$?
import math
import struct
import time

import rclpy
from rclpy.duration import Duration
from rclpy.time import Time
from sensor_msgs.msg import PointCloud2, PointField
import tf2_ros

clouds = []

def on_cloud(msg: PointCloud2) -> None:
    clouds.append(msg)

rclpy.init()
node = rclpy.create_node("aris_scan_cloud_contract")
node.create_subscription(PointCloud2, "/scan_cloud", on_cloud, 10)
tf_buffer = tf2_ros.Buffer()
listener = tf2_ros.TransformListener(tf_buffer, node)

deadline = time.monotonic() + 8.0
transform = None
while time.monotonic() < deadline:
    rclpy.spin_once(node, timeout_sec=0.1)
    if transform is None:
        try:
            transform = tf_buffer.lookup_transform(
                "base_link",
                "lidar_link",
                Time(),
                timeout=Duration(seconds=0.05),
            )
        except Exception:
            transform = None
    if clouds and transform is not None:
        break

node.destroy_node()
rclpy.shutdown()

if not clouds:
    raise SystemExit("no /scan_cloud message received")
if transform is None:
    raise SystemExit("missing TF base_link -> lidar_link")

msg = clouds[-1]
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

fields = {field.name: field for field in msg.fields}
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

sample_count = min(int(msg.width), 64)
finite_points = 0
rings = set()
times = []
for index in range(sample_count):
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

translation = transform.transform.translation
if abs(translation.x - 0.6) > 0.05 or abs(translation.y) > 0.05 or abs(translation.z - 0.9) > 0.05:
    failures.append(
        "unexpected base_link->lidar_link translation "
        f"({translation.x:.3f}, {translation.y:.3f}, {translation.z:.3f})"
    )

if failures:
    raise SystemExit("; ".join(failures))

print(
    "scan_cloud_contract frame={} width={} point_step={} fields={} "
    "tf=({:.3f},{:.3f},{:.3f}) finite_samples={}".format(
        msg.header.frame_id,
        msg.width,
        msg.point_step,
        sorted(fields),
        translation.x,
        translation.y,
        translation.z,
        finite_points,
    )
)
PY

  kill -INT "$lidar_pid" >/dev/null 2>&1 || true
  kill -INT "$sim_pid" >/dev/null 2>&1 || true
  wait "$lidar_pid" || true
  wait "$sim_pid" || true

  if [[ "$code" != "0" ]]; then
    echo "ERROR: /scan_cloud contract validation failed."
    echo "--- sim log ---"
    sed -n "1,180p" "$sim_log"
    echo "--- lidar log ---"
    sed -n "1,180p" "$lidar_log"
    exit "$code"
  fi
'
