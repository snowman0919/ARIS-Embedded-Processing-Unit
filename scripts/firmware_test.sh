#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
aris_load_env

crate="firmware/stm32f446_safety_mcu"

aris_compose run --rm aris-embedded-dev bash -lc "
  set -euo pipefail
  export CARGO_TARGET_DIR=/tmp/aris-firmware-target
  cargo test --manifest-path ${crate}/Cargo.toml
  cargo fmt --manifest-path ${crate}/Cargo.toml -- --check
  cargo clippy --manifest-path ${crate}/Cargo.toml --all-targets -- -D warnings
  cargo build --manifest-path ${crate}/Cargo.toml --target thumbv7em-none-eabihf
"
