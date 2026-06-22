#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
aris_load_env

bags_dir="${ARIS_LOGS}/bags"
mkdir -p "$bags_dir"

before_file="$(mktemp)"
after_file="$(mktemp)"
trap 'rm -f "$before_file" "$after_file"' EXIT

find "$bags_dir" -maxdepth 2 -name metadata.yaml -printf '%T@ %h\n' 2>/dev/null | sort >"$before_file" || true

"$(dirname "${BASH_SOURCE[0]}")/check_v2_recorded_lidar_bag.sh"

find "$bags_dir" -maxdepth 2 -name metadata.yaml -printf '%T@ %h\n' 2>/dev/null | sort >"$after_file" || true

new_bag="$(
  comm -13 "$before_file" "$after_file" \
    | awk '{first=$1; $1=""; sub(/^ /, ""); print first "\t" $0}' \
    | sort -n \
    | tail -1 \
    | cut -f2-
)"

if [[ -z "$new_bag" ]]; then
  new_bag="$(
    find "$bags_dir" -maxdepth 2 -name metadata.yaml -printf '%T@ %h\n' 2>/dev/null \
      | sort -n \
      | tail -1 \
      | cut -d' ' -f2-
  )"
fi

if [[ -z "$new_bag" || ! -f "$new_bag/metadata.yaml" ]]; then
  aris_die "Could not locate the recorded V2 LiDAR bag under $bags_dir"
fi

echo "recorded_lidar_replay_bag=$new_bag"
"$(dirname "${BASH_SOURCE[0]}")/check_v2_lidar_bag_replay.sh" "$new_bag"
