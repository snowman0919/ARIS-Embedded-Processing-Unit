#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
aris_load_env

python3 "${ARIS_WS}/scripts/check_architecture_contracts.py" --workspace "$ARIS_WS"
