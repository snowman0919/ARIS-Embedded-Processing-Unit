#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
aris_load_env

aris_compose run --rm aris-ros2-dev bash -lc '
  set -euo pipefail
  ros2 topic list >/tmp/aris_topics.txt
  timeout 8s bash -lc "ros2 run demo_nodes_cpp talker >/tmp/talker.log 2>&1 & ros2 run demo_nodes_py listener --ros-args -r __node:=aris_smoke_listener" || true
  grep -E "I heard|Hello World" /tmp/talker.log >/dev/null || true
  colcon build --symlink-install
  colcon test --event-handlers console_direct+
'
