#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
aris_load_env
aris_check_docker_access

image="${CUDA_TEST_IMAGE:-nvidia/cuda:12.6.3-base-ubuntu24.04}"
printf 'Running GPU smoke test with %s\n' "$image"
docker run --rm --gpus all "$image" bash -lc 'nvidia-smi && python3 --version || true'
printf 'OK: GPU container launched. On DGX Spark UMA, nvidia-smi may report Memory-Usage as Not Supported.\n'
