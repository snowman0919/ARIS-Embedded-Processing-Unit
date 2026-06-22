#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
aris_load_env
aris_check_ngc_image

if [[ "$#" -eq 0 ]]; then
  aris_compose run --rm aris-ai-dev bash
else
  aris_compose run --rm aris-ai-dev "$@"
fi
