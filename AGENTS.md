# ARIS Development Environment Guidance

This repository is a user-space development environment for ARIS on NVIDIA DGX Spark.

Hard rules:

- Do not require `sudo` on the host.
- Do not install host apt packages.
- Do not modify `/etc`, systemd services, udev rules, Docker daemon config, kernel modules, or global system files.
- Use Nix for host tools.
- Use Docker containers for ROS2, CUDA/AI, simulation, and embedded build tooling.
- Keep default commands simulation-safe. Real actuator output requires `ARIS_ENABLE_REAL_ACTUATION=1`.
- Keep secrets out of git. `.env` is intentionally ignored.
- Keep large data, logs, model files, and caches under `ARIS_HOME`, defaulting to `~/aris`.

Hardware access is opt-in. Use Compose profiles or helper scripts that clearly state when device access or elevated container capabilities are being used.
