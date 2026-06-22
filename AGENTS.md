# ARIS Development Environment Guidance

This repository is a user-space development environment for ARIS on NVIDIA DGX Spark.

Hard rules:

- Treat this workspace as fully user-space: administrator/root privileges are not available for project work.
- Do not require `sudo` on the host.
- Do not install host apt packages.
- Do not modify `/etc`, systemd services, udev rules, Docker daemon config, kernel modules, or global system files.
- If a package or host-side tool is needed, add or use it through Nix rather than system package managers.
- Use Docker containers for ROS2, CUDA/AI, simulation, and embedded build tooling.
- Keep default commands simulation-safe. Real actuator output requires `ARIS_ENABLE_REAL_ACTUATION=1`.
- Keep secrets out of git. `.env` is intentionally ignored.
- Keep large data, logs, model files, and caches under `ARIS_HOME`, defaulting to `~/aris`.


Agent permissions:

- All project work is allowed within this repository and its documented workspace paths.
- Agents may inspect, create, edit, move, and delete project files as needed to complete assigned work.
- Agents may run builds, tests, formatters, linters, simulations, container commands, and Nix commands when they are relevant to the task.
- Do not ask for host administrator privileges; adapt the workflow to Nix, containers, or user-writable paths instead.

Hardware access is opt-in. Use Compose profiles or helper scripts that clearly state when device access or elevated container capabilities are being used.
