# ARIS Architecture Framework Final

Source: `260617 - AI System Architecture Specification v1.0.pdf`

Controlling Korean final: `FINAL_ARCHITECTURE_SPEC.md`

This is the final framework-level interpretation of the source architecture specification for the current `aris-dev-env` repository. It is the controlling architecture reference for communication, internal structure, workflow, safety, and verification documents.

## 1. Mission

ARIS is a Level 4-oriented outdoor autonomous-driving research platform for a pre-mapped operational area of about 500 m x 500 m. It targets controlled outdoor sites such as campuses, research complexes, parks, and closed test fields.

The final architecture is not simple waypoint replay. The intended chain is:

```text
Mapping -> Semantic HD Map -> Route Graph -> Localization -> Goal Based Planning -> Autonomous Driving
```

Core goals:

- Destination-based movement rather than fixed path replay.
- Semantic HD Map and route graph-based planning.
- Repeated-drive map improvement.
- Dynamic obstacle avoidance.
- Advisory multimodal AI for semantic review, map annotation, event explanation, and log analysis.
- Safety MCU authority over steering/brake/motor enable/watchdog/E-stop/fault handling.

## 2. Design Principles

1. Map first, route second. V1 teach-and-repeat is a stepping stone; the final system plans over the semantic map and route graph.
2. One control contract. All driving paths output `/cmd_drive` as `ackermann_msgs/AckermannDriveStamped`.
3. HAL owns sim-vs-real differences. Planners do not know whether the target is simulator or real MCU.
4. Safety dominates autonomy. Heartbeat timeout, E-stop, dry-run gates, and MCU faults override planner intent.
5. AI is advisory only. AI never commands steering, throttle, brake, E-stop release, motor enable, or fault clearing.
6. Simulation first. Hardware mode is opt-in and must pass safety validation.

## 3. Operational Design Domain

| Item | Target |
|---|---|
| Environment | Outdoor controlled or semi-controlled area |
| Area | About 500 m x 500 m |
| Examples | Campus, research complex, park, closed test site |
| Basic autonomous speed | 15 km/h class |
| Governed maximum speed | 25 km/h class |
| Non-default upper reference | 45 km/h, requires separate safety review |

ODD gaps still to define before field use: weather, lighting, slope, road surface, pedestrian density, GPS-denied zones, camera visibility limits, and fallback conditions.

## 4. System Layers

```mermaid
flowchart TD
    GUI[GUI / Operator] --> Goal[Goal Selection / Map Editing]
    Goal --> Planning[Global + Local Planning]
    Sensors[LiDAR, Cameras, GPS, IMU, Encoders] --> Perception[Perception]
    Sensors --> Localization[Localization]
    Perception --> Mapping[Semantic HD Map Update]
    Localization --> Planning
    Mapping --> Graph[Route Graph]
    Graph --> Planning
    Planning --> Cmd[/cmd_drive]
    Cmd --> HAL[HAL: Simulator or STM32 Bridge]
    HAL --> Vehicle[Vehicle / Simulation]
    Vehicle --> State[/vehicle/state + Odometry]
    State --> GUI
    State --> Safety[Safety Monitor]
    Safety --> HAL
    AI[Multimodal AI Advisory Layer] -.-> Mapping
    AI -.-> GUI
    AI -.-> Logs[Log Analysis]
```

## 5. Sensors and Priority

| Sensor | Role | Priority |
|---|---|---|
| Unitree L2 4D LiDAR | Mapping, localization, obstacle detection, free-space detection | P0 |
| 6 synchronized USB cameras | Semantic segmentation, place recognition, map tagging, object classification | P1 |
| GPS | Weak global anchor, initial pose aid, long-range drift correction | P2 |
| IMU | Dead reckoning, motion prediction | P1 |
| Wheel encoder | Longitudinal odometry | P1 |
| Steering encoder | Actual steering angle feedback | P1 |

Localization priority: LiDAR > IMU/Odom > Camera > GPS.

## 6. Coordinate and Time Contract

Canonical TF tree:

```text
map
└── odom
    └── base_link
        ├── lidar_link
        ├── camera_front_link
        ├── camera_front_left_link
        ├── camera_front_right_link
        ├── camera_left_link
        ├── camera_right_link
        ├── camera_rear_link
        ├── imu_link
        └── gps_link
```

Required transforms:

- `T_map_base`: localization result.
- `T_base_lidar`: LiDAR extrinsic calibration.
- `T_base_camera_*`: camera extrinsic calibration.
- `T_base_gps`: GPS antenna extrinsic.
- `T_base_imu`: IMU extrinsic.

Rules:

- Fixed sensor transforms live in `aris_description` URDF/xacro.
- Runtime localization owns `map -> odom` after V2.
- `odom -> base_link` is odometry/localization output, not a planner-owned frame.
- Positions use meters, speed uses m/s, steering uses radians, brake uses 0..1 fraction, voltage uses V.
- Sensor timestamps must preserve acquisition time, not only ROS receipt time.

## 7. Map Framework

The final map is a layered Semantic HD Map:

| Layer | Content | Core Use |
|---|---|---|
| Metric Map | 3D point cloud, voxel grid | Scan matching, geometry |
| Occupancy Map | occupied, free, unknown | Collision and free-space checks |
| Semantic Map | road, sidewalk, grass, wall, fence, building, pole, tree, intersection, parking, no-go zone, narrow passage | Cost and rule context |
| Traversability Map | cost, slope, clearance, confidence, traversable | Planning cost |
| Route Graph | nodes and edges with distance, risk, width, curvature, speed limit | Goal-based planning |

Each map cell should track observation count, free count, semantic votes, last seen, confidence, and change score.

Update policy:

- Repeated agreement increases confidence.
- Long absence decreases confidence.
- New mismatch becomes a change candidate.
- Semantic changes affecting drivable space require review.
- AI can suggest labels or explanations, but reviewed map versions are the operational source of truth.

## 8. Planning Framework

Global planner inputs:

- Current pose.
- Goal pose.
- Semantic map.
- Route graph.

Global planner baseline: A* or Dijkstra. Cost terms: distance, risk, narrowness, curvature, semantic penalty.

Local planner inputs:

- Current pose and velocity.
- Global path.
- Current scan or obstacle field.
- Safety state.

Local planner outputs:

- Target steering.
- Target velocity.
- Brake request.

Baseline local planner is Pure Pursuit. MPC is a later option after localization, map quality, and obstacle models are mature.

## 9. State Machines

Vehicle mode:

```text
OFF -> BOOTING -> STANDBY -> ARMED -> AUTONOMOUS -> GOAL_REACHED
                         \-> MANUAL
                         \-> DEGRADED -> SAFE_STOP
                         \-> FAULT
ANY -> ESTOP_LATCHED -> SHUTDOWN
```

Autonomy state:

```text
IDLE -> LOCALIZING -> WAITING_GOAL -> PLANNING -> DRIVING
DRIVING -> AVOIDING_OBSTACLE -> REPLANNING -> DRIVING
DRIVING -> GOAL_REACHED
ANY -> ABORTED
```

Localization state:

```text
UNINITIALIZED -> LOW_CONFIDENCE -> VALID -> DRIFTING -> RELOCALIZING -> VALID
DRIFTING -> LOST -> SAFE_STOP
```

Map update state:

```text
READ_ONLY -> CANDIDATE_CHANGE -> REVIEW_REQUIRED -> APPROVED -> PUBLISHED
REVIEW_REQUIRED -> REJECTED
```

MCU safety state:

```text
NORMAL -> HEARTBEAT_TIMEOUT -> BRAKE_APPLIED
NORMAL -> COMMAND_TIMEOUT -> BRAKE_APPLIED
ANY -> ESTOP -> MOTOR_DISABLED + BRAKE_APPLIED
ANY -> POWER_LOSS -> BRAKE_APPLIED + STATE_SAVE
```

## 10. Communication and Workflow Documents

Detailed contracts live in:

- `docs/communication_protocol.md`: ROS2 topics, binary MCU protocol, states, timing, faults, and transport migration.
- `docs/internal_structure.md`: package ownership, boundaries, data ownership, and extension rules.
- `docs/workflows.md`: V0-V6, runtime, safety, map update, and handoff workflows.
- `docs/architecture_mapping.md`: PDF requirement to implementation/gap mapping.
- `docs/verification_plan.md`: acceptance tests and safety gates.

If there is a conflict, this document and the companion documents above supersede older focused notes.

## 11. Milestone Roadmap

| Milestone | Name | Completion Meaning |
|---|---|---|
| V0 | Manual control and recording | Operator can drive in sim/dry-run and record contract topics |
| V1 | Trajectory replay | Recorded route can be replayed through `/cmd_drive` |
| V2 | LiDAR localization | Localization owns `/odometry/filtered` and `map -> odom` |
| V3 | Semantic HD Map | Layered map and route graph can be built and inspected |
| V4 | Goal-based navigation | User-selected goal produces route and autonomous movement |
| V5 | Dynamic obstacle avoidance | Local planner reacts to changing obstacles |
| V6 | Multimodal semantic update | AI assists map annotation/change review/log explanation offline |

Milestones must be completed in order. A compiling build is not milestone completion.

## 12. Safety Baseline

- Real actuation is disabled unless `ARIS_ENABLE_REAL_ACTUATION=1`.
- Heartbeat timeout is 200 ms.
- Timeout action: throttle 0, brake apply, safe stop.
- E-stop action: motor disable and brake apply immediately.
- Power-loss action: UPS-backed STM32 records fault, commands brake, and saves state.
- Faults remain latched until reviewed by an operator.
- AI output has no authority over actuation.
