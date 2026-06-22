# Isaac Sim Notes

Isaac Sim is optional and is not part of the default simulation path.

Use the `isaac` Compose profile only after selecting a current arm64/DGX Spark compatible image:

```bash
ISAAC_SIM_IMAGE=nvcr.io/nvidia/isaac-sim:<choose-current-arm64-compatible-tag> \
docker compose -f docker/compose.yaml --profile isaac run --rm aris-isaac
```

Authenticate first:

```bash
docker login nvcr.io
```

Keep Isaac assets, caches, logs, and generated data under `ARIS_HOME` or another configured non-repository path. Do not commit generated assets or simulator caches.
