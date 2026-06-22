# ARIS Architecture Mapping and Gap Matrix

Source: `260617 - AI System Architecture Specification v1.0.pdf`

Controlling Korean final: `FINAL_ARCHITECTURE_SPEC.md`

This document maps the PDF requirements to the current repository and identifies production gaps.

## 1. Requirement Mapping

| PDF Requirement | Current Repository Mapping | Status |
|---|---|---|
| Level 4-oriented outdoor platform | `README.md`, docs, simulation-first stack | Framework defined, field target not validated |
| 500 m x 500 m ODD | architecture docs | Needs detailed ODD limits |
| Semantic HD Map | `aris_mapping` target package | Scaffold/target, production map incomplete |
| Route Graph | `aris_planning` target logic, route graph references | Simulation scaffold, production graph incomplete |
| LiDAR-first localization | `aris_localization`, Gazebo `/scan_cloud`, static Gazebo localization smoke, V2A known-map localization scaffold | Real Unitree/NDT/EKF work remains |
| Goal-based planning | `aris_planning` | Simulation/early route work, GUI goal flow incomplete |
| Pure Pursuit baseline | `aris_planning` | Present in current stack |
| MPC advanced local planner | none | Future work |
| Unitree L2 4D LiDAR | `docs/sensors.md`, Gazebo gpu_lidar smoke, deterministic LiDAR surrogate | Driver and real data integration pending |
| 6 synchronized cameras | `docs/sensors.md` | Hardware sync and perception pending |
| GPS/IMU/encoders | sensor docs and target packages | Real integration pending |
| DGX Spark main compute | Docker/Nix environment | Environment scaffold present |
| STM32F446 safety MCU | firmware package and MCU bridge | Dry-run/protocol foundation present; real transport pending |
| Custom binary MCU protocol | `aris_mcu_bridge.protocol`, docs | Present, needs full state/fault extensions |
| USB UART initial transport | docs/bridge target | Real serial validation pending |
| CAN final transport | docs/bridge target | Design and validation pending |
| Heartbeat 200 ms | protocol code/tests | Present |
| AI advisory only | `docs/ai_layer.md`, `aris_ai_semantics` | Policy present; Cosmos pipeline pending |
| GUI map/goal/edit/monitor | `aris_gui` target package | Placeholder/requirements pending |

## 2. Production Gap Matrix

| Milestone | Simulation/Current Capability | Production Gap | Required Evidence |
|---|---|---|---|
| V0 | Manual/sim/dry-run contract foundation | Hardware-safe manual bench flow | `/cmd_drive`, `/vehicle/state`, E-stop evidence |
| V1 | Teach-and-repeat route replay | Drift-bounded real/sensor-backed replay | route load, tracking error report |
| V2 | Gazebo gpu_lidar `/scan_cloud`, static Gazebo localization smoke, deterministic LiDAR surrogate, V2A known-map localization scaffold | Moving Gazebo pose sync, Unitree L2 driver, production NDT/EKF, GPS/camera correction, real map generation | Gazebo/real drift and relocalization metrics |
| V3 | Semantic map target/scaffold | 5-layer persisted map, camera segmentation, review workflow | map version with layers and confidence |
| V4 | Goal navigation target/scaffold | GUI goal selection, production route graph, no-go handling | multiple goals, route differences, arrival |
| V5 | Obstacle avoidance target | dynamic obstacle detection and local replan | stop/avoid timing and false positive report |
| V6 | AI advisory policy | Cosmos 3 pipeline, offline review UI, provenance | reviewed map updates and event explanations |

## 3. Documents Added by This Finalization

- `architecture_framework.md`: final architecture framework.
- `communication_protocol.md`: ROS2 and MCU communication contracts.
- `internal_structure.md`: package boundaries and data ownership.
- `workflows.md`: runtime, milestone, safety, and map update workflows.
- `verification_plan.md`: acceptance tests, safety gates, and traceability checklist.
- `FINAL_ARCHITECTURE_SPEC.md`: Korean master final specification.

## 4. Immediate Next Documentation Gaps

- `sensor_integration_plan.md`: Unitree L2, six cameras, GPS/IMU/encoder drivers, timestamp sync, calibration artifacts.
- `localization_design.md`: NDT/scan matching, EKF, GPS/camera correction, confidence model.
- `semantic_hd_map_design.md`: storage schema, cell size, label enum, confidence formula, map versioning.
- `gui_requirements.md`: screen-level behavior and operator authority.
- `ai_semantics_design.md`: Cosmos 3/offline advisory pipeline.
- `mcu_transport_design.md`: USB UART to CAN adapter and bench validation.
