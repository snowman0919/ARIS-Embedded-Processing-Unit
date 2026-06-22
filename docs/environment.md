# Environment

The host environment is intentionally small and user-space only.

- Host tools come from Nix.
- Heavy runtimes run inside Docker.
- Data, logs, models, and caches live under `ARIS_HOME`, defaulting to `~/aris`.
- Default ROS2 traffic is local-only with `ROS_LOCALHOST_ONLY=1`.

Enter the environment:

```bash
nix develop
```

Then inspect:

```bash
just nix-shell-info
```
