# ARIS Development Environment

Reproducible user-space development environment for ARIS, an outdoor autonomous driving research platform running on NVIDIA DGX Spark.

The host stays clean: Nix provides lightweight host tools, while ROS2, CUDA/AI, simulation, and embedded toolchains run in Docker. No host command in this repository requires sudo.

## Quick Start

```bash
cd ~/aris-dev-env
nix develop
just check-host
just docker-build
just gpu-test
just ros2-build
just protocol-test
just sim
```

## Host Assumptions

- NVIDIA DGX Spark, Arm/aarch64 Linux.
- User has Nix available.
- User is in the `docker` group and can run Docker without sudo.
- NVIDIA Container Toolkit is already configured by the machine owner.
- No host-level apt installs are required by this repository.

## No-Sudo Policy

This repo must not ask you to run sudo on the host. It does not modify `/etc`, systemd, udev, kernel modules, Docker daemon config, or global package state. Running as root inside Dockerfiles and containers is acceptable.

## Nix Setup

Enter the dev shell:

```bash
nix develop
```

If this repository is a Git working tree and Nix reports that `flake.nix` is not tracked, add the generated scaffold to Git before running the flake:

```bash
git add -A
nix develop
```

Nix flakes read tracked Git content when inside a Git repository.

The shell sets:

- `ARIS_HOME=${HOME}/aris`
- `ARIS_DATA=${ARIS_HOME}/data`
- `ARIS_LOGS=${ARIS_HOME}/logs`
- `ARIS_MODELS=${ARIS_HOME}/models`
- `HF_HOME`, `TRANSFORMERS_CACHE`, `TORCH_HOME`
- `ROS_DOMAIN_ID=42`
- `ROS_LOCALHOST_ONLY=1`
- `RMW_IMPLEMENTATION=rmw_fastrtps_cpp`

It also creates the data, log, and model directories if missing.

## Docker Setup

Build containers:

```bash
just docker-build
```

By default this builds the ROS2 and embedded images. The AI image is skipped until `.env` contains a real NGC PyTorch image tag, because NGC tags and access policy change over time.

Services:

- `aris-ros2-dev`: ROS2 Jazzy, colcon, RViz, Gazebo/ros_gz where available.
- `aris-ai-dev`: NVIDIA NGC PyTorch base with ARIS semantic tooling.
- `aris-embedded-dev`: Rust STM32 build, OpenOCD, probe-rs, firmware tests.

The repository is mounted at `/workspaces/aris`. Data, logs, and model caches are mounted from `ARIS_HOME`.

ROS2 services use host networking because DDS discovery is UDP multicast based and is much less predictable through bridge NAT. The default environment still uses `ROS_LOCALHOST_ONLY=1` for local simulation.

## NGC Login

The AI image comes from NVIDIA NGC. Choose a current arm64/DGX Spark compatible tag in `.env`:

```env
NGC_PYTORCH_IMAGE=nvcr.io/nvidia/pytorch:<choose-current-arm64-dgx-spark-compatible-tag>
```

Then authenticate:

```bash
docker login nvcr.io
```

Use `$oauthtoken` as the username and your NGC API key as the password.

Build the AI image explicitly:

```bash
ARIS_BUILD_AI=1 just docker-build
```

## Smoke Tests

```bash
just check-host      # host tools, Docker access, architecture, ARIS paths
just gpu-test        # CUDA/GPU visibility inside a container
just ros2-test       # ROS2 CLI and demo pub/sub inside container
just ros2-build      # colcon build for starter packages
just protocol-test   # Python MCU protocol tests on host dev shell
just sim             # build and launch pure simulation smoke path
just firmware-test   # Rust STM32 safety-core tests and thumbv7em-none-eabihf build
```

The Nix shell includes Rust host tools for editing, formatting, clippy, and unit tests. The embedded Docker image installs the STM32 Rust target `thumbv7em-none-eabihf` and is the canonical path for firmware target builds.

## Simulation

Default mode is simulation-safe:

```bash
just sim
```

Real actuation is disabled unless `ARIS_ENABLE_REAL_ACTUATION=1` is set. The starter MCU bridge defaults to dry-run behavior.

GUI tools:

```bash
just auto-rviz
just rviz
just gazebo
```

These mount `/tmp/.X11-unix` and pass `DISPLAY` when available.
`just auto-rviz` starts the closed-loop simulator, local planner, simulated MCU bridge, and RViz with the ARIS visualization config. If X11 authorization fails, run the command from a terminal inside the active desktop login or set `ARIS_XAUTHORITY` to a readable Xauthority file.

## Hardware Mode Warning

Hardware mode is opt-in through Compose profiles and explicit scripts. It may map USB, serial, video, or CAN devices into containers. Real motors and brakes must remain disconnected during early development. Safe-stop behavior and the 200 ms heartbeat timeout must be tested before any vehicle bench test.

For vcan testing that requires container network administration, use the separated helper:

```bash
./scripts/can_create_vcan0.sh
```

It uses a privileged helper container only for virtual CAN setup and is not part of the default dev workflow.

## Manual Configuration

- Select a valid `NGC_PYTORCH_IMAGE` in `.env`.
- Ensure Docker can run without sudo.
- Ensure NVIDIA GPU container runtime is configured by the host owner.
- Configure X11 permissions for GUI forwarding if needed.
- Hardware device access depends on group permissions and machine policy.
