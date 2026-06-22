#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
aris_load_env
export ROS_DOMAIN_ID="${ARIS_V2_GAZEBO_MOVING_LOCALIZATION_ROS_DOMAIN_ID:-148}"

aris_compose run --rm aris-ros2-dev bash -lc '
  set -euo pipefail
  colcon build --symlink-install
  set +u
  source install/setup.bash
  set -u

  launch_log=/tmp/aris_v2_gazebo_moving_localization_launch.log
  probe_log=/tmp/aris_v2_gazebo_moving_localization_probe.log
  pose_log=/tmp/aris_v2_gazebo_moving_localization_pose.log
  timeout -s INT 36s ros2 launch aris_localization v2_gazebo_moving_localization.launch.py \
    >"$launch_log" 2>&1 &
  launch_pid=$!
  sleep 6

  code=0
  python3 - <<PY >"$probe_log" 2>&1 || code=$?
import math
import struct
import time

from ackermann_msgs.msg import AckermannDriveStamped
from nav_msgs.msg import Odometry
import rclpy
from sensor_msgs.msg import PointCloud2

clouds = []
filtered = []

def _forward_range_median(msg: PointCloud2) -> float:
    offsets = {field.name: field.offset for field in msg.fields}
    if not {"x", "y", "z"}.issubset(offsets):
        raise SystemExit("cloud is missing x/y/z fields")
    endian = ">" if msg.is_bigendian else "<"
    source = bytes(msg.data)
    ranges = []
    for offset in range(0, len(source), int(msg.point_step)):
        x = struct.unpack_from(endian + "f", source, offset + offsets["x"])[0]
        y = struct.unpack_from(endian + "f", source, offset + offsets["y"])[0]
        z = struct.unpack_from(endian + "f", source, offset + offsets["z"])[0]
        if (
            math.isfinite(x)
            and math.isfinite(y)
            and math.isfinite(z)
            and 0.2 < x < 20.0
            and abs(y) < 2.5
            and -2.0 < z < 2.0
        ):
            ranges.append(float(x))
    if len(ranges) < 20:
        raise SystemExit(f"not enough finite forward LiDAR points: {len(ranges)}")
    ranges.sort()
    return ranges[len(ranges) // 2]

def on_cloud(msg: PointCloud2) -> None:
    clouds.append(msg)

def on_filtered(msg: Odometry) -> None:
    filtered.append(msg)

rclpy.init()
node = rclpy.create_node("aris_v2_gazebo_moving_localization_probe")
cmd_pub = node.create_publisher(AckermannDriveStamped, "/cmd_drive", 10)
node.create_subscription(PointCloud2, "/scan_cloud", on_cloud, 10)
node.create_subscription(Odometry, "/odometry/filtered", on_filtered, 10)

initial_deadline = time.monotonic() + 4.0
while time.monotonic() < initial_deadline and not clouds:
    rclpy.spin_once(node, timeout_sec=0.1)

start = time.monotonic()
deadline = start + 8.0
while time.monotonic() < deadline:
    cmd = AckermannDriveStamped()
    cmd.header.stamp = node.get_clock().now().to_msg()
    cmd.drive.speed = 0.45 if time.monotonic() - start < 5.0 else 0.0
    cmd.drive.steering_angle = 0.0
    cmd_pub.publish(cmd)
    rclpy.spin_once(node, timeout_sec=0.05)
    time.sleep(0.05)

node.destroy_node()
rclpy.shutdown()

failures = []
if not clouds:
    failures.append("no /scan_cloud sample")
if len(clouds) < 2:
    failures.append(f"too few /scan_cloud samples: {len(clouds)}")
if len(filtered) < 3:
    failures.append(f"too few /odometry/filtered samples: {len(filtered)}")
if failures:
    raise SystemExit("; ".join(failures))

first = filtered[0].pose.pose.position
last = filtered[-1].pose.pose.position
delta_x = float(last.x - first.x)
first_range = _forward_range_median(clouds[0])
last_range = _forward_range_median(clouds[-1])
range_delta = first_range - last_range
if clouds[-1].header.frame_id != "lidar_link":
    failures.append(f"cloud frame={clouds[-1].header.frame_id!r}, expected lidar_link")
if clouds[-1].point_step != 24 or clouds[-1].width < 100:
    failures.append(f"unexpected cloud width/point_step={clouds[-1].width}/{clouds[-1].point_step}")
if delta_x < 0.35:
    failures.append(f"filtered pose did not move far enough: delta_x={delta_x:.3f}")
if abs(float(last.y)) > 0.25:
    failures.append(f"filtered y drift too high: y={float(last.y):.3f}")
if range_delta < 0.25:
    failures.append(
        "Gazebo LiDAR forward range did not shrink enough: "
        f"initial={first_range:.3f}, final={last_range:.3f}, delta={range_delta:.3f}"
    )
if failures:
    raise SystemExit("; ".join(failures))

print(
    "v2_gazebo_moving_localization cloud_width={} filtered_start=({:.3f},{:.3f}) "
    "filtered_last=({:.3f},{:.3f}) delta_x={:.3f} "
    "front_range_delta={:.3f} ({:.3f}->{:.3f})".format(
        clouds[-1].width,
        float(first.x),
        float(first.y),
        float(last.x),
        float(last.y),
        delta_x,
        range_delta,
        first_range,
        last_range,
    )
)
PY

  timeout 3s gz topic -e -t /world/aris_lidar_smoke/pose/info >"$pose_log" 2>/dev/null || true

  python3 - <<PY >>"$probe_log" 2>&1 || code=$?
from pathlib import Path
import re

text = Path("$pose_log").read_text(errors="replace")
matches = list(
    re.finditer(
        r"name: \"aris\".*?position \\{\\s*x: ([^\\s]+).*?\\}",
        text,
        flags=re.DOTALL,
    )
)
if not matches:
    raise SystemExit("could not find aris pose in Gazebo pose/info")
x = float(matches[-1].group(1))
if x < 0.35:
    raise SystemExit(f"Gazebo aris entity did not move far enough: x={x:.3f}")
print(f"gazebo_aris_pose_x={x:.3f}")
PY

  kill -INT "$launch_pid" >/dev/null 2>&1 || true
  wait "$launch_pid" || true

  if [[ "$code" != "0" ]]; then
    echo "ERROR: moving Gazebo LiDAR localization smoke failed."
    echo "--- ROS topics ---"
    ros2 topic list -t | sort || true
    echo "--- Gazebo topics ---"
    gz topic -l | sort || true
    echo "--- launch log ---"
    sed -n "1,260p" "$launch_log"
    echo "--- probe log ---"
    sed -n "1,200p" "$probe_log"
    echo "--- Gazebo pose log excerpt ---"
    sed -n "1,120p" "$pose_log"
    exit "$code"
  fi

  sed -n "1,120p" "$probe_log"
'
