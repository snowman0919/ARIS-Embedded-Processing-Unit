#!/usr/bin/env bash
set -euo pipefail

if [[ -f /opt/ros/jazzy/setup.bash ]]; then
  set +u
  # shellcheck disable=SC1091
  source /opt/ros/jazzy/setup.bash
  set -u
fi

if [[ -f /workspaces/aris/install/setup.bash ]]; then
  set +u
  # shellcheck disable=SC1091
  source /workspaces/aris/install/setup.bash
  set -u
fi

exec "$@"
