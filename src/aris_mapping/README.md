# aris_mapping

V3 semantic HD map scaffold.

This package is intentionally ROS-free for now because V3 completion needs camera streams and a
segmentation model that are not available in this environment. The implemented core covers the
five planned layers:

- metric cells
- occupancy probability
- semantic labels with confidence
- traversability cost
- route graph nodes/edges

The current update policy supports repeat-pass confidence and change detection. It is WIP
scaffolding, not a completed V3 map pipeline.

Simulation smoke:

```bash
nix develop -c just v3-semantic-smoke
```

This launches the V2A route-repeat stack, a simulation-only perception source, and
`semantic_map_node`. The node consumes `/scan_cloud` for metric/occupancy cells and
`/aris/perception/semantic_observation` for semantic/traversability/change-detection updates, then
publishes JSON summaries on `/aris/mapping/semantic_map`.
