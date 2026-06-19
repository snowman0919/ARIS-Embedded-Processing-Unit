#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
aris_load_env

targets=(aris-ros2-dev aris-embedded-dev)

if [[ "${ARIS_BUILD_AI:-0}" == "1" ]]; then
  aris_check_ngc_image
  targets+=(aris-ai-dev)
elif aris_ngc_image_configured; then
  targets+=(aris-ai-dev)
else
  cat <<'MSG'
Skipping aris-ai-dev because .env does not contain a real NGC_PYTORCH_IMAGE.
To build the AI image:
  cp .env.example .env
  edit .env with a current arm64 DGX Spark compatible NGC PyTorch tag
  docker login nvcr.io
  ARIS_BUILD_AI=1 just docker-build
MSG
fi

aris_compose build "${targets[@]}"
