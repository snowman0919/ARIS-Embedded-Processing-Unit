#!/usr/bin/env bash
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
err_file="$(mktemp "${TMPDIR:-/tmp}/aris-clean-rm.XXXXXX")"
trap 'rm -f "$err_file"' EXIT

if ! rm -rf "$repo/build" "$repo/install" "$repo/log" "$repo/firmware/stm32f446_safety_mcu/target" 2>"$err_file"; then
  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    docker run --rm -v "$repo:/workspaces/aris" ubuntu:24.04 \
      chown -R "$(id -u):$(id -g)" \
        /workspaces/aris/build \
        /workspaces/aris/install \
        /workspaces/aris/log \
        /workspaces/aris/firmware/stm32f446_safety_mcu/target \
        2>/dev/null || true
    rm -rf "$repo/build" "$repo/install" "$repo/log" "$repo/firmware/stm32f446_safety_mcu/target"
  else
    cat "$err_file" >&2
    printf 'ERROR: Could not remove root-owned build artifacts and Docker is unavailable for the no-sudo ownership repair helper.\n' >&2
    exit 1
  fi
fi

rm -rf "$repo/.pytest_cache" "$repo/.ruff_cache" "$repo/.mypy_cache"
find "$repo" -type d -name __pycache__ -prune -exec rm -rf {} +
printf 'Cleaned generated build/test state under %s\n' "$repo"
