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

## 10. Current Headless Readiness Gate

The current reproducible software readiness command is:

```bash
just core-readiness
```

It runs unit, MCU protocol loopback, `/scan_cloud` contract, operator goal, V4 goal navigation, and
V2 Gazebo stack smokes. The Gazebo stack includes cloud contract, static localization, moving
pose-sync localization, pose-sync-free Ackermann physics motion, physics-fed localization, and
drift recovery. Set
`ARIS_CORE_READINESS_SKIP_GAZEBO=1` only when the environment cannot run headless Gazebo; that skip
weakens the evidence and must be recorded in the run log.

To store timestamped evidence:

```bash
just core-readiness-report
```

Reports are written to `$ARIS_LOGS/readiness/core_readiness_<timestamp>.log`, with
`$ARIS_LOGS/readiness/latest.log` pointing at the most recent run.

## 11. Recorded LiDAR Acceptance Gate

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

## 12. Semantic Map Snapshot Acceptance Gate

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

This is simulation-only V3 map artifact evidence. Production V3 still requires camera streams,
segmentation model selection, calibrated camera/LiDAR projection, review tooling, and real
repeat-pass map data.
