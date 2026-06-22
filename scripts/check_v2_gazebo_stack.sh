#!/usr/bin/env bash
set -euo pipefail

# Runs the complete headless Gazebo V2 LiDAR stack validation sequence.
# Each child script owns its ROS_DOMAIN_ID and prints detailed logs on failure.

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

checks=(
  "check_v2_gazebo_lidar.sh"
  "check_v2_gazebo_localization.sh"
  "check_v2_gazebo_moving_localization.sh"
  "check_v2_gazebo_physics.sh"
  "check_v2_gazebo_physics_localization.sh"
  "check_v2_gazebo_drift_recovery.sh"
)

for check in "${checks[@]}"; do
  printf '\n==> %s\n' "$check"
  "${script_dir}/${check}"
done

printf '\nV2 Gazebo stack smoke passed (%d checks).\n' "${#checks[@]}"
