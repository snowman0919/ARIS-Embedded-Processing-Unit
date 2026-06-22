#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
aris_load_env

if [[ "$#" -ne 1 ]]; then
  printf 'Usage: %s <bag-dir-or-metadata.yaml>\n' "$0" >&2
  exit 2
fi

python3 "$(dirname "${BASH_SOURCE[0]}")/validate_v2_lidar_bag.py" "$1"
