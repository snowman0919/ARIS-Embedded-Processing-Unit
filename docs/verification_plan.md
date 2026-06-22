# ARIS Verification Plan

Source: `260617 - AI System Architecture Specification v1.0.pdf`

Controlling Korean final: `FINAL_ARCHITECTURE_SPEC.md`

This document defines the verification checklist for the final architecture framework.

## 1. Verification Levels

| Level | Meaning | Examples |
|---|---|---|
| Unit | Pure logic tests | protocol encode/decode, Pure Pursuit, route graph cost |
| Integration | ROS package wiring | topic publication, TF, launch composition |
| SIL | Simulation-in-the-loop | route replay, obstacle simulation, localization with recorded data |
| HIL | Hardware-in-the-loop | STM32 bridge, serial/CAN, sensors on bench |
| Field | Closed-site ODD test | goal navigation, obstacle avoidance, map update |

## 2. Architecture Contract Tests

- `/cmd_drive` remains the only control command contract.
- HAL is the only layer that branches between sim and real.
- `/vehicle/state` is published by sim HAL and MCU HAL.
- `map -> odom -> base_link` TF tree exists.
- AI layer has no publisher path to `/cmd_drive` or MCU control commands.
- Current README/docs command references resolve to real Just recipes or scripts:

```bash
just documented-commands
```
- Headless bootstrap assumptions are valid for the current user-space environment:

```bash
just bootstrap-doctor
```

This verifies required repository files, core commands, ARIS environment variables/directories,
safe headless defaults, and that real actuation is disabled before running heavier Docker/Gazebo
checks.
- Static architecture guardrails remain intact:

```bash
just architecture-contracts
```
- Host entrypoints keep the no-sudo/no-host-apt policy:

```bash
just host-policy
```
- Local and `origin/*` branches use approved ARIS feature/milestone names:

```bash
just branch-policy
```

## 3. Communication Tests

- CRC error is rejected.
- Unknown message type is rejected.
- Unsupported version is rejected.
- Bad length is rejected.
- Sequence mismatch is rejected when expected.
- Heartbeat timeout triggers safe stop after 200 ms.
- E-stop frame latches safety state.
- Fault report maps to `/vehicle/state.fault_code` or safety event topic.
- USB UART framing is validated before bench actuation.
- CAN bus-off and recovery are validated before CAN field use.

## 4. Safety Tests

- Real actuation stays disabled unless `ARIS_ENABLE_REAL_ACTUATION=1`.
- Loss of heartbeat applies brake and sets throttle 0.
- E-stop disables motor and applies brake.
- Power loss path logs fault and saves state using UPS-backed MCU time.
- Fault latch requires operator-reviewed clear.
- Localization loss limits speed, attempts relocalization, then safe stops.

## 5. Mapping Tests

- Metric layer loads and is spatially aligned.
- Occupancy layer distinguishes occupied/free/unknown.
- Semantic label enum is stable.
- Traversability cost is bounded and documented.
- Route graph nodes/edges carry distance, risk, width, curvature, speed limit.
- Confidence increases with repeated observations.
- Confidence decreases with stale observations.
- Change candidates require review before driveability-changing publication.

## 6. Localization Tests

- IMU/odom prediction works without LiDAR for short intervals.
- LiDAR correction reduces drift.
- GPS jumps are rejected or downweighted.
- Camera place recognition can aid relocalization when available.
- `/odometry/filtered` and `map -> odom` are owned by localization after V2.
- Localization confidence drives speed limiting and safe-stop fallback.

## 7. Planning Tests

- A* or Dijkstra finds a route between reachable graph nodes.
- Unreachable goals are reported, not driven toward blindly.
- No-go zones are avoided.
- Narrow passages raise cost.
- Curvature and speed limit affect path/speed profile.
- Dynamic obstacles cause stop, slow, or local detour.
- Goal reached condition stops the vehicle.

## 8. GUI and Operator Tests

- Map viewer displays pose, route, semantic layer, and fault state.
- Goal selection creates a planning request.
- Map editing requires proper authority.
- Vehicle monitor shows velocity, battery, localization confidence, dry-run, E-stop, and fault.
- Operator can see why autonomy stopped.

## 9. Acceptance Traceability

Every milestone must record:

- Requirement ID or document section.
- Test ID.
- Environment: unit, integration, SIL, HIL, or field.
- Input data or route/map version.
- Numeric pass criteria.
- Result.
- Known limitations.

A milestone is complete only when its acceptance evidence exists. A compiling build alone is not evidence.

## 10. Branch Policy

Remote branches are ARIS feature/milestone baselines, not task branches:

| Branch | Meaning |
|---|---|
| `milestone/teach-repeat-route-replay` | V1 teach-and-repeat route replay baseline |
| `milestone/lidar-localization-gazebo` | V2 LiDAR localization, Gazebo, and recorded-bag evidence baseline |
| `milestone/semantic-hd-map` | V3 semantic map artifact, manifest, and repeat-pass compare baseline |
| `milestone/goal-based-navigation` | V4 route graph and goal-based navigation baseline |
| `milestone/dynamic-obstacle-advisory` | V5 dynamic obstacle advisory, tracking, and recorded replay baseline |
| `milestone/headless-simulation-embedded` | Current hardware-free simulation and embedded-software integration baseline |

Task-level remote branches such as `codex/v2-*` or `codex/v3-*`, and version-only branches such as
`v6`, should not be kept. New changes advance the relevant ARIS milestone branch after their
evidence is recorded. The `just branch-policy` gate enforces this local/origin branch set.

Current hardware scope is headless. No serial, CAN, camera, LiDAR, actuator, or vehicle bench
hardware is assumed to be attached. HIL and field sections below define future evidence contracts;
they are not active execution blockers for simulation and embedded dry-run software work.

## 11. Current Headless Readiness Gate

The current reproducible software readiness command is:

```bash
just core-readiness
```

It runs unit, MCU protocol loopback, `/scan_cloud` contract, operator goal, V3 semantic map
snapshot/manifest/compare acceptance, V4 goal navigation, V5 dynamic-obstacle detour/slow/stop
advisory with persistent-track evidence, V6 advisory-only semantic review, and V2 Gazebo stack
smokes. The Gazebo stack includes cloud contract, static localization, moving pose-sync localization,
pose-sync-free Ackermann physics motion, physics-fed localization, and drift recovery. Set
`ARIS_CORE_READINESS_SKIP_V3=1` only when the environment cannot run the V3 map artifact gate; that
skip weakens the evidence and must be recorded in the run log. Set
`ARIS_CORE_READINESS_SKIP_GAZEBO=1` only when the environment cannot run headless Gazebo; that skip
weakens the evidence and must be recorded in the run log.

The cross-milestone pipeline flow command is:

```bash
just core-pipeline-flow
```

It generates a Semantic HD Map snapshot, validates its route graph, launches the V4 planner with
that snapshot as `semantic_map_file`, and verifies Mapping -> Semantic HD Map -> Route Graph ->
Localization -> Goal Based Planning -> Autonomous Driving evidence in one JSON report under
`$ARIS_LOGS/pipeline/`.

To verify repeatability of that same headless flow:

```bash
just core-pipeline-repeatability
```

By default it runs `core-pipeline-flow` twice, requires both runs to pass all six stages, requires
the route-graph signature to remain stable, bounds final goal-error spread, and records minimum
sample floors across the repeated runs for `/scan_cloud`, `/global_path`, and `/cmd_drive`. Route
stability is evaluated on the final detour suffix, so a later run may start at `detour_b` instead
of `detour_a` after vehicle progress, but a different final detour still fails. Set
`ARIS_CORE_PIPELINE_REPEAT_RUNS=<N>` to increase the repeat count. It writes
`$ARIS_LOGS/pipeline/core_pipeline_repeatability_<timestamp>.json`.

To store timestamped evidence:

```bash
just core-readiness-report
```

Reports are written to `$ARIS_LOGS/readiness/core_readiness_<timestamp>.log`, with
`$ARIS_LOGS/readiness/latest.log` pointing at the most recent run. The report wrapper also writes
an evidence index:

```text
$ARIS_LOGS/readiness/evidence_index_<timestamp>.json
$ARIS_LOGS/readiness/latest_evidence_index.json
```

The index points at the latest readiness report, latest V2 LiDAR bag metadata, latest V3 semantic
map manifest, latest V3 repeat-pass compare report, latest V5 dynamic-obstacle report plus
detour/slow/stop metrics with persistent-track evidence, and latest V6 semantic review report when
present. It also links the latest embedded dry-run, HIL preflight, operational audit, and headless
readiness audit reports when available. It is the quick
machine-readable view of the current software evidence bundle.

## 12. Headless Simulation And Embedded Audit

The current hardware-free completion audit commands are:

```bash
just embedded-dry-run
just headless-readiness-audit
```

It writes `$ARIS_LOGS/readiness/headless_readiness_audit_<timestamp>.json` and updates
`$ARIS_LOGS/readiness/latest_headless_readiness_audit.json`. The audit requires no-skip core
readiness, V2 Gazebo/LiDAR bag evidence, V3/V6 semantic map review evidence, V5 obstacle smoke and
recorded replay evidence, and a valid embedded dry-run report from `just embedded-dry-run`. HIL
preflight and field validation are recorded as future blockers outside the current headless scope,
not as active blockers.

For a release-candidate style run on a headless machine, use:

```bash
just headless-release-candidate
```

It runs bootstrap doctor, embedded dry-run, documented-command validation, architecture-contract
validation, host-policy validation, branch-policy validation, core pipeline flow, core pipeline
repeatability, no-skip core readiness report, and headless readiness audit in sequence. It writes
`$ARIS_LOGS/readiness/headless_release_candidate_<timestamp>.json` and updates
`$ARIS_LOGS/readiness/latest_headless_release_candidate.json`. At the end of the run it also
refreshes `$ARIS_LOGS/readiness/latest_evidence_index.json` so the index links back to the release
candidate report that produced it. The final report is validated by
`scripts/validate_headless_release_candidate.py`, which requires every release step to pass and
requires the release report and final evidence index to point at each other.

To inspect the latest release, audit, pipeline, and repeatability evidence without opening raw JSON:

```bash
just headless-status
```

The same summary is available as JSON with `./scripts/check_headless_status.sh --json`.
The text and JSON summaries include repeatability sample floors so operators can see whether the
latest repeated run observed enough LiDAR clouds, global-path points, and command samples.

## 13. Operational Readiness Audit

The current completion audit command is:

```bash
just operational-readiness-audit
```

It writes `$ARIS_LOGS/readiness/operational_readiness_audit_<timestamp>.json` and updates
`$ARIS_LOGS/readiness/latest_operational_readiness_audit.json`. The audit aggregates the latest
readiness index, V2 Gazebo/LiDAR evidence, V3 map manifest and repeat-pass compare, V5 dynamic
obstacle report, V5 obstacle bag replay score, V6 advisory-only semantic review, repeated core
pipeline evidence, HIL preflight, and field-validation evidence.
It records `achieved`, `practical_use_ready`, `safe_to_enable_real_actuation`, per-criterion pass
states, and blockers. This audit is the machine-readable guardrail for deciding whether the
project can be considered practically usable; current simulation evidence can pass while HIL or
field criteria still keep `achieved=false`.

## 14. HIL Preflight Gate

Before hardware-in-the-loop or bench work, run:

```bash
just hil-preflight
```

This writes `$ARIS_LOGS/hil/hil_preflight_<timestamp>.json` and updates
`$ARIS_LOGS/hil/latest_hil_preflight.json`. The report is non-actuating: it never enables real
actuation and always records `safe_to_enable_real_actuation=false`. It checks host command
availability, Docker access, user groups, visible serial/video/GPU/CAN/input devices, latest
no-skip readiness evidence, latest V5 obstacle report, and latest V6 semantic review report. Missing
hardware is reported as blockers instead of causing destructive setup actions.

## 15. Recorded LiDAR Acceptance Gate

The current reproducible recorded-data command is:

```bash
just v2-recorded-lidar-bag-smoke
```

It records a short Gazebo physics-localization run to `$ARIS_LOGS/bags/` and validates the rosbag
metadata for `/scan_cloud`, `/gazebo/odom`, `/odometry/filtered`, `/cmd_drive`, and `/tf`. Real
LiDAR bags must pass the same topic/type/count contract before they can be accepted as V2 evidence.

To validate an existing operator-provided bag:

```bash
just v2-lidar-bag-contract /path/to/bag
```

This command does not launch simulation. It only validates `metadata.yaml`, making it suitable as
the first gate for real LiDAR recordings before replay or localization scoring.

The replay-scoring gate is:

```bash
just v2-lidar-bag-replay /path/to/bag
```

It first applies the same metadata contract, then mounts the bag read-only into the ROS 2
container, plays it back, and listens for `/cmd_drive`, `/scan_cloud`, `/gazebo/odom`,
`/odometry/filtered`, and `/tf`. The gate requires enough replayed samples, a `lidar_link`
cloud frame, nonzero moving drive commands, bounded filtered-vs-Gazebo final pose gap, and
forward motion in both Gazebo odometry and filtered odometry.

To produce synthetic evidence end-to-end:

```bash
just v2-recorded-lidar-replay-smoke
```

This records the Gazebo physics-localization path, validates the new bag metadata, finds the
newly written bag under `$ARIS_LOGS/bags`, and immediately replay-scores it. Operator-provided
real LiDAR bags should pass `v2-lidar-bag-contract` before `v2-lidar-bag-replay`.

## 16. V5 Obstacle Bag Replay Gate

The operator-data obstacle replay command is:

```bash
just v5-obstacle-bag-replay /path/to/bag
```

The deterministic recorded-obstacle replay smoke is:

```bash
just v5-recorded-obstacle-replay-smoke
```

It records a short `/scan_cloud` rosbag with corridor obstacle points under
`$ARIS_LOGS/bags/v5_recorded_obstacle_<timestamp>/`, then runs the same
`v5-obstacle-bag-replay` scorer against that bag.

This gate accepts a rosbag directory or `metadata.yaml`, validates a sensor-focused `/scan_cloud`
contract, replays the bag inside the ROS 2 container, runs `dynamic_obstacle_node`, and scores
`/aris/perception/dynamic_obstacle` advisories. It writes:

```text
$ARIS_LOGS/obstacles/v5_obstacle_bag_replay_<timestamp>.json
```

The report records bag path, cloud sample count, advisory count, action counts, closest obstacle
distance, max track age, thresholds, and failures. This is the bridge between simulation-only V5
evidence and real/operator obstacle recordings. A missing or invalid replay score keeps the
operational readiness audit from claiming practical-use readiness.

## 17. Semantic Map Snapshot Acceptance Gate

The current reproducible V3 simulation map-generation command is:

```bash
just v3-semantic-smoke
```

It launches V2A route repeat, deterministic simulation perception, and `semantic_map_node`.
The node consumes `/scan_cloud`, `/aris/perception/semantic_observation`, and the route CSV,
then writes a semantic HD map snapshot under `$ARIS_LOGS/maps/`.

The gate validates both the live `/aris/mapping/semantic_map` summary and the persisted JSON
snapshot. The snapshot must reload through `SemanticHDMap.load_snapshot`, use schema version `1`
and map id `aris-v3-sim`, contain metric cells, semantic labels, a high-risk traversability cell,
review queue entries, and a route graph with route nodes and edges.

The same smoke also writes a promotion manifest next to the snapshot:

```text
$ARIS_LOGS/maps/v3_semantic_map_<timestamp>.manifest.json
```

The manifest records snapshot path, SHA-256, schema version, map id, layer counts, label counts,
route graph size, review queue size, and validation status. Existing snapshots can be checked with:

```bash
./scripts/validate_semantic_map_snapshot.py /path/to/v3_semantic_map.json
```

When a previous V3 semantic map snapshot exists in `$ARIS_LOGS/maps`, the same smoke also writes a
repeat-pass comparison report:

```text
$ARIS_LOGS/maps/v3_semantic_map_<timestamp>.compare.json
```

The compare report records baseline/candidate SHA-256 values, metric-cell overlap, route-graph
overlap, semantic top-label changes, high-risk cell delta, and review-queue delta. The default
V3 smoke requires at least 70% metric-cell overlap, 95% route-edge overlap, no more than two
top-label changes, no more than two high-risk-cell changes, and no more than eight review-queue
entries of delta. The review queue is a timing-sensitive operator workload signal, so it is bounded
more loosely than route structure and semantic label stability. Existing snapshot pairs can be
scored with:

```bash
./scripts/compare_semantic_map_snapshots.py /path/to/baseline.json /path/to/candidate.json
```

This is simulation-only V3 map artifact evidence. Production V3 still requires camera streams,
segmentation model selection, calibrated camera/LiDAR projection, review tooling, and real
repeat-pass map data.

## 18. Closed-Site Field Validation Gate

The field validation command is:

```bash
just field-validation /path/to/field_validation_manifest.json
```

It writes:

```text
$ARIS_LOGS/field/field_validation_<timestamp>.json
$ARIS_LOGS/field/latest_field_validation.json
```

The manifest must describe a closed-site run and include:

- `site_id`, `operator`, `route_id`, and `field_run_id`.
- `odd.closed_site=true` and `odd.pedestrian_separated=true`.
- `metrics.route_completed=true`.
- `metrics.goal_error_m <= metrics.max_goal_error_m`.
- `metrics.max_speed_mps <= metrics.speed_limit_mps`.
- zero `estop_count`, `fault_count`, and `operator_takeover_count`.
- cited `evidence.hil_preflight_report`, `evidence.v5_obstacle_bag_replay_report`, and
  `evidence.field_bag`.
- `approvals.operator_reviewed=true` and `approvals.safety_reviewed=true`.

The generated report records `valid`, failures, run summary, the original manifest, and the latest
linked HIL/V5 replay artifacts visible under `$ARIS_LOGS`. The operational readiness audit only
accepts field evidence when this report is valid.
