# Nix

`flake.nix` targets `aarch64-linux` and also permits `x86_64-linux` for editing and CI-style checks.

The dev shell includes Git, direnv, just, Python tools, C/C++ tools, Rust host tools, Docker client/Compose when available, USB/CAN utilities, OpenOCD, probe-rs, and ARM embedded GCC where available in the selected nixpkgs revision.

Rust host tools are intended for formatting, clippy, and host-side firmware unit tests. The STM32 target build uses the embedded Docker image, where rustup installs `thumbv7em-none-eabihf` explicitly.

Some nixpkgs revisions rename embedded packages. The flake uses best-effort alternatives for:

- Docker client and Compose.
- `minicom` or `tio`.
- `gcc-arm-embedded` or `gcc-arm-none-eabi`.

If a package disappears from nixpkgs, update only `flake.nix`; do not install host apt packages.
