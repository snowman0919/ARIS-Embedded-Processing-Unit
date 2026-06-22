#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
aris_load_env

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
  printf 'Run: nix develop -c just v4-teach %s\n' "$route_name" >&2
  exit 1
fi

printf '\nARIS V4 manual follow\n'
printf '  route file: %s\n' "$route_host"
printf '  flow: V2A LiDAR localization -> V4 global route graph -> /global_path -> PurePursuit -> /cmd_drive\n'
printf 'Press Ctrl-C to stop.\n\n'

aris_compose run --rm aris-ros2-dev bash -lc "
  set -euo pipefail
  colcon build --symlink-install
  set +u
  source install/setup.bash
  set -u
  ros2 launch aris_planning v4_goal_nav_sim.launch.py route_file:='$route_container' use_demo_graph:=false
"
