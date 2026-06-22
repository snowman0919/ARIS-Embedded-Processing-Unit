# ARIS Internal Structure

Source: `260617 - AI System Architecture Specification v1.0.pdf`

Controlling Korean final: `FINAL_ARCHITECTURE_SPEC.md`

This document defines package ownership, runtime boundaries, data ownership, and extension rules.

## 1. Repository Layout

```text
aris-dev-env/
├── docs/                    architecture, operation, handoff documents
├── docker/                  ROS2, AI, embedded containers
├── scripts/                 entrypoints, checks, simulation helpers
├── sim/                     simulation maps, models, launch references
├── src/
│   ├── aris_ai_semantics/   advisory AI semantic tooling
│   ├── aris_bringup/        launch composition and mode switches
│   ├── aris_description/    URDF/xacro and fixed frame definitions
│   ├── aris_gui/            operator interface target package
│   ├── aris_interfaces/     custom ROS messages
│   ├── aris_localization/   target localization package
│   ├── aris_mapping/        target map-build/update package
│   ├── aris_mcu_bridge/     STM32 HAL and binary protocol
│   ├── aris_perception/     target perception package
│   ├── aris_planning/       route, global, and local planning
│   └── aris_vehicle_sim/    simulator HAL
└── firmware/
    └── stm32f446_safety_mcu/ safety MCU firmware
```

Runtime data lives outside the repository under `ARIS_DATA`, `ARIS_LOGS`, and `ARIS_MODELS`.

## 2. Package Ownership

| Package | Owns | Must Not Own |
|---|---|---|
| `aris_description` | physical model, fixed sensor links, URDF geometry | runtime localization state |
| `aris_interfaces` | ROS custom message schemas | business logic |
| `aris_bringup` | launch composition, sim/real mode choice | algorithm internals |
| `aris_vehicle_sim` | sim HAL, kinematic simulation, simulated feedback | real hardware access |
| `aris_mcu_bridge` | binary protocol, heartbeat, STM32 HAL, dry-run gate | planner decisions |
| `aris_planning` | route loading, route graph search, local path tracking | sim-vs-real branching |
| `aris_localization` | fused pose, `map -> odom`, LiDAR scan matching | map editing |
| `aris_mapping` | layered map, cell updates, route graph generation | direct actuation |
| `aris_perception` | static/dynamic object detection and classification | motion command authority |
| `aris_gui` | map viewer, goal selection, map editing, vehicle monitor | safety override internals |
| `aris_ai_semantics` | semantic indexing, annotation review, explanations, log analysis | real-time control |
| `stm32f446_safety_mcu` | motor/brake safety, watchdog, E-stop, faults | high-level route planning |

## 3. Control Boundary

```text
planner or teleop -> /cmd_drive -> HAL -> simulator or STM32
```

Rules:

- No planner publishes serial/CAN frames.
- No planner changes behavior based on simulator-vs-real mode.
- HAL translates `/cmd_drive` to simulator dynamics or MCU frames.
- `/vehicle/state` is the feedback contract from HAL.
- Safety can override HAL output at any time.

## 4. Pure Core and ROS Wrapper Pattern

Pure core:

- No ROS imports.
- Deterministic inputs and outputs.
- Unit-tested on host.
- Reusable in simulation and hardware.

ROS wrapper:

- Subscribes/publishes topics.
- Converts ROS messages into pure data structures.
- Loads parameters.
- Owns timers and lifecycle behavior.

Examples: `pure_pursuit.py`, `cmd_drive.py`, `protocol.py`, `local_planner_node.py`.

## 5. Map Data Structure

Metric layer stores point cloud tiles, voxel grid, timestamp, and source metadata.

Occupancy layer stores occupied/free/unknown/confidence.

Semantic layer stores labels such as road, sidewalk, grass, wall, fence, building, pole, tree, intersection, parking, no-go zone, and narrow passage.

Traversability layer stores cost, slope, clearance, confidence, and traversable.

Route graph stores nodes with ID, position, tag, confidence and edges with distance, risk, width, curvature, speed limit.

## 6. Localization Structure

Prediction sources: IMU and wheel odometry.

Correction sources: LiDAR scan matching, camera place recognition, GPS weak global anchor.

Output ownership:

- `aris_localization` owns `/odometry/filtered` after V2.
- `aris_localization` owns `map -> odom` after V2.
- Sim publishes temporary placeholders only before localization is active.

## 7. Planning Structure

Global planner consumes current pose, goal, semantic map, and route graph. It produces `/global_path` using A* or Dijkstra initially.

Local planner consumes `/odometry/filtered`, `/global_path`, obstacle state, and `/estop`. It produces `/cmd_drive` using Pure Pursuit baseline and later MPC if justified.

Route recorder records pose samples to `ARIS_DATA/routes` for V1. It must not become the final navigation model.

## 8. GUI Structure

Required views:

- Map viewer.
- Goal selection.
- Map editing.
- Vehicle monitor.
- Fault and safety panel.

Required actions:

- Set start and goal.
- Mark semantic tags.
- Mark no-go zones.
- Review change candidates.
- Inspect localization confidence.
- Inspect fault state.

## 9. AI Layer Structure

Allowed: semantic indexing, map annotation suggestions, change detection review, event explanation, log analysis.

Disallowed: direct steering, throttle, brake, E-stop release, motor enable, and unreviewed fault clearing.

Target model family: NVIDIA Cosmos 3 or later compatible multimodal model.

## 10. Extension Rules

When adding a subsystem:

1. Define ROS topics, services, actions, and data ownership.
2. Keep algorithm logic in a pure core when practical.
3. Add unit tests for pure logic.
4. Add integration smoke tests for ROS wiring.
5. Update `architecture_framework.md` if a boundary changes.
6. Update `communication_protocol.md` if a message changes.
7. Update `workflows.md` if operator or validation steps change.
