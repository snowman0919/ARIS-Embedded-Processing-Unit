#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
aris_load_env

aris_check_gui_env
aris_compose --profile gui run --rm aris-ros2-dev bash -lc 'source install/setup.bash 2>/dev/null || true; ros2 launch aris_vehicle_sim gazebo.launch.py'
