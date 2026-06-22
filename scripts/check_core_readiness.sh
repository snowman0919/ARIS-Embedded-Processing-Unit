#!/usr/bin/env bash
set -euo pipefail

# Headless operational readiness gate for the current ARIS software stack.
# This intentionally excludes GUI and real-hardware checks.

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

checks=(
  "check_python_tests.sh"
  "check_mcu_serial_loopback.sh"
  "check_scan_cloud_contract.sh"
  "check_operator_goal.sh"
)

if [[ "${ARIS_CORE_READINESS_SKIP_V3:-0}" != "1" ]]; then
  checks+=("check_v3_semantic_map.sh")
fi

checks+=("check_v4_goal_nav.sh")

if [[ "${ARIS_CORE_READINESS_SKIP_GAZEBO:-0}" != "1" ]]; then
  checks+=("check_v2_gazebo_stack.sh")
fi

for check in "${checks[@]}"; do
  printf '\n==> %s\n' "$check"
  "${script_dir}/${check}"
done

printf '\nARIS core readiness passed (%d checks).\n' "${#checks[@]}"
