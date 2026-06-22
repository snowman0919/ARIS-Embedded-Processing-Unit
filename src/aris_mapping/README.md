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
loads the route CSV into the route-graph layer, publishes JSON summaries on
`/aris/mapping/semantic_map`, and writes a persisted snapshot under `$ARIS_LOGS/maps/`.

The smoke validates the generated snapshot by reloading it through `SemanticHDMap.load_snapshot`
and checking schema version, map id, metric cells, semantic labels, traversability, review queue,
route nodes, and route edges.

It also writes a manifest next to the snapshot:

```text
$ARIS_LOGS/maps/v3_semantic_map_<timestamp>.manifest.json
```

The manifest includes the snapshot SHA-256 and layer counts so map artifacts can be compared or
promoted later without reopening the full JSON by hand. Validate an existing snapshot with:

```bash
./scripts/validate_semantic_map_snapshot.py /path/to/v3_semantic_map.json
```

When an older V3 snapshot is available in `$ARIS_LOGS/maps`, the smoke also writes:

```text
$ARIS_LOGS/maps/v3_semantic_map_<timestamp>.compare.json
```

The compare report scores repeat-pass stability: metric-cell overlap, route-graph overlap, top-label
changes, high-risk cell delta, and review-queue delta. The smoke keeps route and semantic structure
tight while allowing up to eight review-queue entries of delta because that queue reflects
timing-sensitive operator workload rather than map topology. Compare existing snapshots with:

```bash
./scripts/compare_semantic_map_snapshots.py /path/to/baseline.json /path/to/candidate.json
```
