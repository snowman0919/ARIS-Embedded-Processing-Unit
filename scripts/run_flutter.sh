#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if [[ -z "${ARIS_FLUTTER_SDK:-}" ]] && command -v flutter >/dev/null 2>&1; then
  exec flutter "$@"
fi

SDK="${ARIS_FLUTTER_SDK:-$ROOT/tools/flutter}"

if [[ ! -x "$SDK/bin/flutter" ]]; then
  echo "Flutter SDK not found at $SDK" >&2
  echo "Run through Nix: nix develop -c bash -lc 'cd src/aris_gui && ../../scripts/run_flutter.sh <command>'" >&2
  exit 1
fi

export PATH="$SDK/bin:$PATH"
exec "$SDK/bin/flutter" "$@"
