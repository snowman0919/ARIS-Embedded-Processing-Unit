#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
aris_load_env
export ROS_DOMAIN_ID="${ARIS_V5_SMOKE_ROS_DOMAIN_ID:-143}"

aris_compose run --rm aris-ros2-dev bash -lc '
  set -euo pipefail
  colcon build --symlink-install
  set +u
  source install/setup.bash
  set -u

  launch_log=/tmp/aris_v5_dynamic_obstacle_launch.log

  timeout -s INT 24s ros2 launch aris_planning v4_goal_nav_sim.launch.py \
    enable_dynamic_obstacles:=false \
    >"$launch_log" 2>&1 &
  launch_pid=$!
  sleep 4

  python3 - <<PY
import json
import time

import rclpy
from ackermann_msgs.msg import AckermannDriveStamped
from aris_perception.dynamic_obstacles import (
    DynamicObstacleConfig,
    DynamicObstacleTracker,
    PointXYZ,
    obstacle_observation,
)
from std_msgs.msg import String

samples = []

def on_cmd(msg: AckermannDriveStamped) -> None:
    samples.append(
        (
            time.monotonic(),
            float(msg.drive.speed),
            float(msg.drive.acceleration),
            float(msg.drive.steering_angle),
        )
    )

rclpy.init()
node = rclpy.create_node("aris_v5_dynamic_obstacle_smoke")
node.create_subscription(AckermannDriveStamped, "/cmd_drive", on_cmd, 20)
pub = node.create_publisher(String, "/aris/perception/dynamic_obstacle", 10)

deadline = time.monotonic() + 3.0
while time.monotonic() < deadline:
    rclpy.spin_once(node, timeout_sec=0.1)

if not samples:
    raise SystemExit("no /cmd_drive samples before advisory")
baseline_speed = max(speed for _, speed, _, _ in samples)
baseline_min_steering = min(steering for _, _, _, steering in samples)

detour_start = time.monotonic()
detour = String()
detour.data = json.dumps(
    {
        "action": "detour",
        "closest_distance_m": 2.4,
        "closing_speed_mps": 0.1,
        "detour_forward_m": 2.0,
        "detour_lateral_m": -1.2,
        "point_count": 8,
        "reason": "inside_detour_distance",
    },
    sort_keys=True,
)
while time.monotonic() - detour_start < 2.0:
    pub.publish(detour)
    rclpy.spin_once(node, timeout_sec=0.05)

detour_samples = [item for item in samples if item[0] >= detour_start + 0.2]
if not detour_samples:
    raise SystemExit("no /cmd_drive samples during detour advisory")
detour_min_speed = min(speed for _, speed, _, _ in detour_samples)
detour_min_accel = min(accel for _, _, accel, _ in detour_samples)
detour_min_steering = min(steering for _, _, _, steering in detour_samples)

slow_start = time.monotonic()
slow = String()
slow.data = json.dumps(
    {
        "action": "slow",
        "closest_distance_m": 2.2,
        "closing_speed_mps": 0.1,
        "point_count": 8,
        "reason": "inside_slow_distance",
    },
    sort_keys=True,
)
while time.monotonic() - slow_start < 2.0:
    pub.publish(slow)
    rclpy.spin_once(node, timeout_sec=0.05)

slow_samples = [item for item in samples if item[0] >= slow_start + 0.2]
if not slow_samples:
    raise SystemExit("no /cmd_drive samples during slow advisory")
slow_min_speed = min(speed for _, speed, _, _ in slow_samples)
slow_min_accel = min(accel for _, _, accel, _ in slow_samples)

stop_start = time.monotonic()
stop = String()
stop.data = json.dumps(
    {
        "action": "stop",
        "closest_distance_m": 0.8,
        "closing_speed_mps": 0.0,
        "point_count": 9,
        "reason": "inside_stop_distance",
    },
    sort_keys=True,
)
while time.monotonic() - stop_start < 2.0:
    pub.publish(stop)
    rclpy.spin_once(node, timeout_sec=0.05)

stop_samples = [item for item in samples if item[0] >= stop_start + 0.2]
if not stop_samples:
    raise SystemExit("no /cmd_drive samples during stop advisory")
stop_min_speed = min(speed for _, speed, _, _ in stop_samples)
stop_min_accel = min(accel for _, _, accel, _ in stop_samples)

tracking_config = DynamicObstacleConfig()
tracker = DynamicObstacleTracker(tracking_config)
first_observation = obstacle_observation(
    [PointXYZ(3.0, 0.1, 0.0), PointXYZ(3.1, 0.0, 0.0), PointXYZ(3.2, -0.1, 0.0)],
    config=tracking_config,
)
second_observation = obstacle_observation(
    [PointXYZ(2.8, 0.1, 0.0), PointXYZ(2.9, 0.0, 0.0), PointXYZ(3.0, -0.1, 0.0)],
    config=tracking_config,
)
tracker.update(first_observation, timestamp_s=1.0)
track = tracker.update(second_observation, timestamp_s=1.2)
if track is None:
    raise SystemExit("dynamic obstacle tracker did not create a persistent track")

node.destroy_node()
rclpy.shutdown()

print(
    "v5_dynamic_obstacle baseline_speed={:.3f} baseline_min_steering={:.3f} "
    "detour_min_speed={:.3f} detour_min_accel={:.3f} detour_min_steering={:.3f} "
    "slow_min_speed={:.3f} slow_min_accel={:.3f} "
    "stop_min_speed={:.3f} stop_min_accel={:.3f} "
    "track_age={} track_persistence_s={:.3f} track_velocity_x_mps={:.3f}".format(
        baseline_speed,
        baseline_min_steering,
        detour_min_speed,
        detour_min_accel,
        detour_min_steering,
        slow_min_speed,
        slow_min_accel,
        stop_min_speed,
        stop_min_accel,
        track.age,
        track.persistence_s,
        track.velocity_x_mps,
    )
)

failures = []
if baseline_speed < 0.5:
    failures.append(f"baseline planner speed too low before advisory: {baseline_speed:.3f}")
if detour_min_speed > 0.35:
    failures.append(f"detour advisory did not cap speed: {detour_min_speed:.3f}")
if detour_min_accel > -0.09:
    failures.append(f"detour advisory did not request gentle braking: {detour_min_accel:.3f}")
if detour_min_steering > -0.05:
    failures.append(f"detour advisory did not steer toward local bypass: {detour_min_steering:.3f}")
if slow_min_speed > 0.35:
    failures.append(f"slow advisory did not cap speed: {slow_min_speed:.3f}")
if slow_min_accel > -0.19:
    failures.append(f"slow advisory did not request braking: {slow_min_accel:.3f}")
if stop_min_speed > 0.05:
    failures.append(f"stop advisory did not command near-zero speed: {stop_min_speed:.3f}")
if stop_min_accel > -0.99:
    failures.append(f"stop advisory did not request full brake: {stop_min_accel:.3f}")
if track.age < 2:
    failures.append(f"tracker did not persist obstacle across frames: age={track.age}")
if track.persistence_s < 0.19:
    failures.append(f"tracker persistence too short: {track.persistence_s:.3f}")
if track.velocity_x_mps >= 0.0:
    failures.append(f"tracker did not estimate closing obstacle velocity: {track.velocity_x_mps:.3f}")
if failures:
    raise SystemExit("; ".join(failures))
PY

  kill -INT "$launch_pid" >/dev/null 2>&1 || true
  wait "$launch_pid" || true
'
