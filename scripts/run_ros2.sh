#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
aris_load_env

if [[ "$#" -eq 0 ]]; then
  aris_compose run --rm aris-ros2-dev bash
else
  aris_compose run --rm aris-ros2-dev "$@"
fi
