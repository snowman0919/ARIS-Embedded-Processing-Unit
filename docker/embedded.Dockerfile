FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl git build-essential cmake ninja-build pkg-config \
    gcc-arm-none-eabi binutils-arm-none-eabi gdb-multiarch \
    openocd python3 python3-pip python3-pytest \
    clang clang-tools \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://probe.rs/files/install.sh | bash -s -- --non-interactive \
    || echo "WARNING: probe-rs install failed; use Nix host probe-rs or install manually in this container."

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | \
      sh -s -- -y --profile minimal --default-toolchain stable --target thumbv7em-none-eabihf \
    && source /root/.cargo/env \
    && rustup component add rustfmt clippy llvm-tools-preview \
    && cargo install cargo-binutils \
    || (echo "ERROR: Rust STM32 toolchain setup failed. Check network access and rustup availability." >&2; exit 1)

ENV PATH="/root/.cargo/bin:${PATH}"
WORKDIR /workspaces/aris
CMD ["bash"]
