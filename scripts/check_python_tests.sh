#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
aris_load_env

cd "$ARIS_WS"

python_paths=()
while IFS= read -r package_dir; do
  package_name="$(basename "$package_dir")"
  if [[ -d "$package_dir/$package_name" ]]; then
    python_paths+=("$package_dir")
  fi
done < <(find src -mindepth 1 -maxdepth 1 -type d | sort)

if [[ "${#python_paths[@]}" -eq 0 ]]; then
  aris_die "No Python packages found under src/."
fi

joined_path="$(IFS=:; printf '%s' "${python_paths[*]}")"
if [[ -n "${PYTHONPATH:-}" ]]; then
  export PYTHONPATH="${joined_path}:${PYTHONPATH}"
else
  export PYTHONPATH="$joined_path"
fi

if [[ "$#" -gt 0 ]]; then
  python3 -m pytest "$@" -q
else
  python3 -m pytest src tests -q
fi
