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

mkdir -p "$ARIS_DATA/routes"

printf '\nARIS V4 manual teach\n'
printf '  route file: %s\n\n' "$route_host"
printf 'Open another terminal and run:\n'
printf '  cd %s && nix develop -c just teleop-key\n\n' "$ARIS_WS"
printf 'Drive the route. When done, press Ctrl-C in this teach terminal.\n\n'

aris_compose run --rm aris-ros2-dev bash -lc "
  set -euo pipefail
  colcon build --symlink-install
  set +u
  source install/setup.bash
  set -u
  rm -f '$route_container'
  ros2 launch aris_bringup bringup.launch.py use_sim:=true mode:=teleop >/tmp/aris_manual_v4_teach_bringup.log 2>&1 &
  bringup_pid=\$!
  cleanup() {
    kill -INT \"\$bringup_pid\" >/dev/null 2>&1 || true
    wait \"\$bringup_pid\" >/dev/null 2>&1 || true
  }
  trap cleanup EXIT INT TERM
  sleep 2
  ros2 launch aris_planning path_recorder.launch.py route_file:='$route_container' waypoint_spacing_m:=0.2 v_target_mps:=1.2 || true
"
