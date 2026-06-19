# Troubleshooting

## Docker Permission Denied

If `docker info` fails, the user is probably not in the `docker` group or the daemon is unavailable. Ask the machine owner to fix Docker group membership. Do not use sudo in this repo.

## DGX Spark UMA Memory Reporting

On DGX Spark unified memory architectures, `nvidia-smi` may show `Memory-Usage: Not Supported`. That does not by itself mean CUDA is broken. Prefer running a small CUDA/PyTorch operation inside the AI container.

## Missing NGC Auth

If pulling `nvcr.io/nvidia/pytorch` fails with authentication errors:

```bash
docker login nvcr.io
```

Use `$oauthtoken` as the username and an NGC API key as the password.

## X11 / GUI Issues

If RViz or Gazebo cannot open a display:

- Confirm `DISPLAY` is set.
- Confirm `/tmp/.X11-unix` exists.
- Confirm `XAUTHORITY` points to a file this user can read, or set `ARIS_XAUTHORITY` to a readable file.
- Run GUI commands from a terminal inside the active desktop login session.
- Configure local X11 access according to site policy.

If the script reports that `XAUTHORITY` points to an unreadable path such as another user's `/run/user/.../gdm/Xauthority`, fix the shell environment before launching RViz. As a last-resort debugging path, set `ARIS_SKIP_X11_CHECK=1` only when X access has already been granted by another mechanism such as a site-approved `xhost` rule.

Do not modify system display manager configuration from this repo.

## `/dev/video` Permission Issues

Camera access requires hardware mode and host device permissions. Check:

```bash
./scripts/check_devices.sh
```

Ask the machine owner to adjust group permissions if needed.

## `/dev/ttyUSB` Permission Issues

USB UART access requires hardware mode and serial permissions. Use `/dev/serial/by-id` when possible for stable names.

## CAN / vcan Requires NET_ADMIN

Creating `vcan0` requires `NET_ADMIN`. Use the separated helper:

```bash
./scripts/can_create_vcan0.sh
```

It does not run as the default dev command.

## Disk Space From Docker Images

NGC, ROS2, Isaac, and CUDA images are large. Inspect:

```bash
docker system df
```

Prune only images and caches you know are unused.

## aarch64 Package Incompatibilities

Some Python wheels and simulator binaries lag on aarch64. Prefer source builds, NGC-provided packages, or documented optional degradation. Do not add x86_64-only binaries to the default path.
