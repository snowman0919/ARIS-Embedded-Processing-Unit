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
  timeout 12s ros2 launch aris_vehicle_sim autonomous_sim.launch.py || code=$?
  if [[ "${code:-0}" != "0" && "${code:-0}" != "124" ]]; then
    exit "$code"
  fi
'
