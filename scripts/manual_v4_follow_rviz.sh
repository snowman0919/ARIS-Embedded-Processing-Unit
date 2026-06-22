#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
aris_load_env
aris_check_gui_env

route_name="${1:-manual_v4_route.csv}"
if [[ "$route_name" = /* ]]; then
  route_container="$route_name"
  route_host="$route_name"
else
  route_container="/aris/data/routes/$route_name"
  route_host="$ARIS_DATA/routes/$route_name"
fi

if [[ ! -f "$route_host" ]]; then
  printf 'ERROR: route file not found: %s\n' "$route_host" >&2
  printf 'Run: nix develop -c just v4-teach-rviz %s\n' "$route_name" >&2
  exit 1
fi

printf '\nARIS V4 visual follow\n'
printf '  route file: %s\n' "$route_host"
printf '  RViz shows /global_path, /aris/planned_path, /scan_cloud, TF, and vehicle pose.\n'
printf 'Press Ctrl-C to stop.\n\n'

aris_compose --profile gui run --rm aris-ros2-dev bash -lc "
  set -euo pipefail
  colcon build --symlink-install
  set +u
  source install/setup.bash
  set -u
  ros2 launch aris_planning v4_goal_nav_rviz.launch.py route_file:='$route_container' use_demo_graph:=false
"
