#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
aris_load_env

printf 'ARIS host check\n'
printf '  repo: %s\n' "$(aris_repo_root)"
printf '  arch: %s\n' "$(uname -m)"
printf '  ARIS_HOME: %s\n' "$ARIS_HOME"

case "$(uname -m)" in
  aarch64|arm64) ;;
  *) printf 'WARNING: host is not aarch64. This repo supports x86_64 for editing, but DGX Spark target is aarch64-linux.\n' >&2 ;;
esac

for cmd in git python3 docker; do
  aris_need_cmd "$cmd"
done

missing_optional=()
for cmd in git-lfs just jq yq rg fd tree tmux nvim uv ruff mypy pre-commit cmake ninja pkg-config clang gdb lsof socat; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    missing_optional+=("$cmd")
  fi
done

if [[ "${#missing_optional[@]}" -gt 0 ]]; then
  printf 'WARNING: optional dev tools missing: %s\n' "${missing_optional[*]}" >&2
  printf '         Enter nix develop for the full toolchain. Direct scripts still work for core checks.\n' >&2
fi

aris_check_docker_access

if ! docker compose version >/dev/null 2>&1; then
  aris_die "Docker Compose v2 is unavailable. Enter nix develop or add a Compose package to flake.nix for this nixpkgs revision."
fi

if ! docker run --rm hello-world >/dev/null 2>&1; then
  aris_die "Docker can run but failed the hello-world smoke test. Check Docker daemon status and user group membership."
fi

printf 'OK: required host tools, Docker access, and ARIS directories are ready.\n'
