#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
aris_load_env

manifest_file="$(
  find "$ARIS_LOGS/maps" -maxdepth 1 -type f -name "v3_semantic_map_*.manifest.json" \
    -printf "%T@ %p\n" 2>/dev/null \
    | sort -n \
    | tail -1 \
    | cut -d" " -f2-
)"

if [[ -z "$manifest_file" || ! -f "$manifest_file" ]]; then
  echo "ERROR: no V3 semantic map manifest found under $ARIS_LOGS/maps" >&2
  echo "Run ./scripts/check_v3_semantic_map.sh first." >&2
  exit 1
fi

compare_file="${manifest_file%.manifest.json}.compare.json"
if [[ ! -f "$compare_file" ]]; then
  compare_file=""
fi

review_file="${manifest_file%.manifest.json}.v6_review.json"
container_manifest_file="${manifest_file/#$ARIS_LOGS/\/aris\/logs}"
container_compare_file="${compare_file/#$ARIS_LOGS/\/aris\/logs}"
container_review_file="${review_file/#$ARIS_LOGS/\/aris\/logs}"

aris_compose run --rm aris-ros2-dev bash -lc "
  set -euo pipefail
  colcon build --symlink-install
  set +u
  source install/setup.bash
  set -u
  /workspaces/aris/scripts/generate_v6_semantic_review.py \
    --manifest '$container_manifest_file' \
    ${container_compare_file:+--compare '$container_compare_file'} \
    --out '$container_review_file'
"
