# ARIS Development Environment

Reproducible user-space development environment for ARIS, an outdoor autonomous driving research platform running on NVIDIA DGX Spark.

The host stays clean: Nix provides lightweight host tools, while ROS2, CUDA/AI, simulation, and embedded toolchains run in Docker. No host command in this repository requires sudo.

## Codebase Boundary

This repository is the ARIS processing-unit codebase: ROS 2 packages, simulation, localization, perception, planning, bringup, Docker/Nix tooling, and verification scripts.

Standalone codebases live separately:

- Flutter operator UI: `snowman0919/ARIS-Flutter-Interface`
- STM32 safety MCU firmware: `snowman0919/ARIS-Embedded-MCU`
- DGX Spark AI/Isaac lab: `snowman0919/ARIS-AI`

See `docs/codebase_boundaries.md` for the local directory conventions.

## Branch Policy

Use ARIS `v{num}-{context}` branches only:

- `v1-teach-repeat-route-replay`: teach-and-repeat route replay baseline.
- `v2-lidar-localization-gazebo`: LiDAR localization, Gazebo, and recorded-bag evidence baseline.
- `v3-semantic-hd-map`: semantic map artifact, manifest, and repeat-pass compare baseline.
- `v4-goal-based-navigation`: route graph and goal-based navigation baseline.
- `v5-dynamic-obstacle-advisory`: dynamic obstacle advisory, tracking, and recorded replay baseline.
- `v6-headless-simulation-embedded`: current hardware-free simulation and embedded-software integration baseline.

Do not create task-level remote branches such as `codex/v2-*`, version-only branches such as `v6`,
or stale `milestone/*` branches. New work should advance the relevant ARIS vN-context branch. The
current active branch is `v6-headless-simulation-embedded` because no hardware is attached and it
carries the latest headless simulation and embedded dry-run state.

Current execution scope is headless: no vehicle hardware is assumed to be attached. HIL and field
documents remain as future evidence contracts, but active development should prioritize simulation,
recorded/replayed data, ROS 2 processing software, and embedded dry-run software until hardware is
available.


## Quick Start

```bash
cd /home/sbeen/aris/aris-dev-env
nix develop
just bootstrap-doctor
just branch-policy
just check-host
just docker-build
just headless-release-candidate
```

If `just` is not available yet, the same checks can be run through the scripts
directly:

```bash
./scripts/check_host.sh
./scripts/check_bootstrap_doctor.sh
./scripts/check_branch_policy.sh
./scripts/check_headless_release_candidate.sh
./scripts/check_core_readiness.sh
./scripts/run_core_readiness_report.sh
./scripts/check_core_pipeline_flow.sh
./scripts/check_python_tests.sh
./scripts/check_v2_gazebo_lidar.sh
./scripts/check_v2_gazebo_localization.sh
./scripts/check_v2_gazebo_moving_localization.sh
./scripts/check_v2_gazebo_physics.sh
./scripts/check_v2_gazebo_physics_localization.sh
./scripts/check_v2_recorded_lidar_bag.sh
./scripts/check_v2_recorded_lidar_replay.sh
./scripts/check_v2_lidar_bag_contract.sh /path/to/bag
./scripts/check_v2_lidar_bag_replay.sh /path/to/bag
./scripts/check_v2_gazebo_drift_recovery.sh
./scripts/check_v2_gazebo_stack.sh
./scripts/check_lidar_sim.sh
./scripts/check_scan_cloud_contract.sh
./scripts/check_operator_goal.sh
./scripts/check_mcu_serial_loopback.sh
```


## Architecture Documents

The final framework derived from `260617 - AI System Architecture Specification v1.0.pdf` is maintained in:

- `docs/README.md`
- `docs/FINAL_ARCHITECTURE_SPEC.md`
- `docs/architecture_framework.md`
- `docs/communication_protocol.md`
- `docs/internal_structure.md`
- `docs/workflows.md`
- `docs/architecture_mapping.md`
- `docs/verification_plan.md`

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
just bootstrap-doctor # verify ARIS env, paths, files, Nix/Docker commands, and safe defaults
just core-readiness  # headless readiness gate, including V3/V6 artifacts and Gazebo by default
just core-readiness-report # core-readiness with timestamped log under ARIS_LOGS
just core-pipeline-flow # V3 semantic map artifact -> V4 route graph -> localization -> /cmd_drive
just core-pipeline-repeatability # repeat core-pipeline-flow and summarize stability
just headless-readiness-audit # aggregate current headless simulation + embedded dry-run evidence
just headless-status # human-readable summary of the latest headless release evidence
just headless-release-candidate # run the full hardware-free release-candidate evidence bundle
just gpu-test        # CUDA/GPU visibility inside a container
just ros2-test       # ROS2 CLI and demo pub/sub inside container
just python-test     # ROS-free Python unit tests on the host
just documented-commands # verify README/docs command references resolve to local recipes/scripts
just architecture-contracts # static guardrails for /cmd_drive, HAL, and AI advisory boundaries
just host-policy    # verify host entrypoints keep the no-sudo/no-apt policy
just branch-policy  # verify local/origin branches use ARIS vN-context names only
just ros2-build      # colcon build for starter packages
just protocol-test   # Python MCU protocol tests on host dev shell
just mcu-serial-loopback # PTY serial loopback for MCU binary transport
just sim             # build and launch pure simulation smoke path
just v2-lidar-smoke  # Gazebo gpu_lidar -> normalized /scan_cloud smoke
just v2-gazebo-localization-smoke # Gazebo /scan_cloud -> localization smoke
just v2-gazebo-moving-smoke # moving sim pose -> Gazebo entity -> localization smoke
just v2-gazebo-physics-smoke # /cmd_drive -> Gazebo Ackermann physics motion smoke
just v2-gazebo-physics-localization-smoke # Gazebo physics odom -> localization smoke
just v2-recorded-lidar-bag-smoke # record and validate a V2 LiDAR acceptance bag
just v2-recorded-lidar-replay-smoke # record, validate, and replay-score a V2 LiDAR bag
just v2-lidar-bag-contract /path/to/bag # validate an existing real/operator LiDAR bag
just v2-lidar-bag-replay /path/to/bag # replay-score an accepted real/operator LiDAR bag
just v2-gazebo-drift-smoke # Gazebo gpu_lidar corrects drifted wheel odom
just v2-gazebo-stack-smoke # run all headless Gazebo V2 checks
just v3-semantic-smoke # generate and validate a five-layer semantic map snapshot
just v4-goal-smoke # semantic route-graph goal navigation smoke
just v5-dynamic-obstacle-smoke # V5 advisory detours/slows/stops the local planner
just v5-obstacle-bag-replay /path/to/bag # replay-score operator LiDAR obstacle evidence
just v5-recorded-obstacle-replay-smoke # record then replay-score a deterministic obstacle bag
just v6-semantic-review-smoke # V6 advisory-only semantic map review report
just scan-cloud-contract # validate /scan_cloud PointCloud2 fields, frame, and TF
just operator-goal-smoke # operator JSON goal -> /goal_pose -> V4 planner smoke
just gui-snapshot-route /path/to/route.csv /tmp/gui_snapshot.json # route CSV -> GUI snapshot JSON
just gui-snapshot-map /path/to/semantic_map.json /tmp/gui_snapshot.json # V3 map -> GUI snapshot JSON
just gui-snapshot-serve /tmp/gui_snapshot.json # serve GUI snapshot on localhost:8765
just hil-preflight # hardware/HIL readiness inventory without enabling actuators
just operational-readiness-audit # aggregate repeatability, HIL, field evidence, and practical-use status
just field-validation /path/to/manifest.json # validate closed-site field-run evidence
just embedded-dry-run # MCU bridge/protocol tests plus timestamped hardware-free evidence report
just firmware-test   # standalone STM32 crate test path if firmware/ is present in this checkout
```

`just core-readiness-report` writes both a text report and a machine-readable evidence index under
`$ARIS_LOGS/readiness/`. The latest index is available at
`$ARIS_LOGS/readiness/latest_evidence_index.json`.
`just operational-readiness-audit` writes the current completion audit to
`$ARIS_LOGS/readiness/latest_operational_readiness_audit.json`.
`just headless-readiness-audit` writes the current hardware-free simulation and embedded software
audit to `$ARIS_LOGS/readiness/latest_headless_readiness_audit.json`.
`just headless-status` prints a concise human-readable summary of the latest headless release,
audit, pipeline, and repeatability evidence, including whether that evidence was generated from the
current Git `HEAD`, why the evidence is fresh or stale, each release step pass/fail result, the
per-step evidence paths, the headless audit acceptance thresholds, and whether hardware scope or
real actuation is active. It also reports the modification time and age of the latest release,
audit, index, and repeatability evidence, plus repeatability margins against the thresholds, so
headless operators can judge when a fresh release-candidate run is needed. Use
`./scripts/check_headless_status.sh --json` for the same summary as JSON.
`just headless-release-candidate` runs the hardware-free evidence bundle end to end and writes
`$ARIS_LOGS/readiness/latest_headless_release_candidate.json`.
`just branch-policy` writes the latest local/origin branch policy check to
`$ARIS_LOGS/readiness/latest_branch_policy.json`. The report also includes `main_sync`, which
records how many commits `origin/main` and `origin/v6-headless-simulation-embedded` are ahead of
each other so pending mainline PRs are visible from the local readiness evidence.

The Nix shell includes Rust host tools for editing, formatting, clippy, and unit tests. This
processing-unit repository owns the ROS 2 MCU bridge and binary protocol tests; standalone STM32
firmware sources live in `snowman0919/ARIS-Embedded-MCU`.

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
just gui-snapshot-route /path/to/route.csv /tmp/gui_snapshot.json
just gui-snapshot-map /path/to/v3_semantic_map.json /tmp/gui_snapshot.json
just gui-snapshot-serve /tmp/gui_snapshot.json
```

These mount `/tmp/.X11-unix` and pass `DISPLAY` when available.
`just auto-rviz` starts the closed-loop simulator, local planner, simulated MCU bridge, and RViz with the ARIS visualization config. If X11 authorization fails, run the command from a terminal inside the active desktop login or set `ARIS_XAUTHORITY` to a readable Xauthority file.
The `gui-snapshot-*` commands are headless-safe handoff tools: they export route or V3
SemanticHDMap artifacts to compact JSON containing `vehicle_pose`, `goal`, `global_path`,
`local_path`, `semantic_cells`, and `lidar_returns` for the external Flutter operator UI. The
serve command defaults to `127.0.0.1:8765`; bind `0.0.0.0` only when intentionally exposing the
snapshot to an Android tablet on the lab network.

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


## Android Tablet GUI Bridge

The Flutter tablet app lives at `/home/sbeen/aris/aris-flutter-interface`. The Nix dev shell
provides Flutter, Dart, JDK 17, Android platform tools, and an accepted Android SDK/NDK composition
for local tablet builds. Dev-env can export route or V3 SemanticHDMap artifacts into the GUI
snapshot schema and serve them over HTTP for Android lab testing:

```bash
nix develop --command just gui-snapshot-route /path/to/route.csv /tmp/aris_gui_snapshot.json
nix develop --command just gui-snapshot-serve /tmp/aris_gui_snapshot.json 0.0.0.0 8765
```

Use `gui-snapshot-map /path/to/v3_semantic_map.json /tmp/aris_gui_snapshot.json` when starting from
the V3 `SemanticHDMap.save_snapshot` output.
