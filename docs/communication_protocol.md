# ARIS Communication Protocol

Source: `260617 - AI System Architecture Specification v1.0.pdf`

Controlling Korean final: `FINAL_ARCHITECTURE_SPEC.md`

This document defines communication contracts for ARIS: ROS2 internal interfaces, PC-to-MCU binary protocol, state reporting, safety timing, fault behavior, and the USB UART to CAN migration path.

## 1. Communication Domains

| Domain | Scope | Transport | Owner |
|---|---|---|---|
| Main computer internal | ROS nodes on DGX Spark/KR260 | ROS2 DDS | ROS packages |
| HAL to simulator | `/cmd_drive` and simulated feedback | ROS2 | `aris_vehicle_sim` |
| HAL to STM32 safety MCU | actuation, heartbeat, state, fault | Custom binary protocol | `aris_mcu_bridge` + firmware |
| Operator GUI | map view, goal selection, editing, monitor | ROS2/service/API layer | `aris_gui` |
| AI advisory | annotation review, event explanation, logs | files/services, not real-time control | `aris_ai_semantics` |

## 2. ROS2 Interface Matrix

| Topic | Type | Direction | Rate/QoS Target | Meaning |
|---|---|---|---|---|
| `/cmd_drive` | `ackermann_msgs/AckermannDriveStamped` | planner/teleop -> HAL | control loop, reliable | single vehicle command contract |
| `/odometry/filtered` | `nav_msgs/Odometry` | localization -> planner | localization loop | fused pose and velocity |
| `/wheel_odom` | `nav_msgs/Odometry` | odometry source -> localization | encoder/sim loop | odometry source |
| `/vehicle/state` | `aris_interfaces/StateReport` | HAL -> system | HAL loop, reliable | vehicle state and safety health |
| `/estop` | `std_msgs/Bool` | safety/operator -> system | event/reliable | E-stop latch |
| `/global_path` | `geometry_msgs/PoseArray` | global planner -> local planner | on plan/replan | global route |
| `/aris/planned_path` | `geometry_msgs/PoseArray` | local planner -> GUI/RViz | visualization loop | current planned path |
| `/cmd_vel` | `geometry_msgs/Twist` | teleop input -> bridge | manual loop | manual input |

Planned sensor topics:

| Topic | Type Class | Source |
|---|---|---|
| `/scan_cloud` | point cloud | Unitree L2 4D LiDAR |
| `/imu/data` | IMU | IMU |
| `/gps/fix` | GNSS fix | GPS |
| `/camera/front/image` | image | front camera |
| `/camera/front_left/image` | image | front-left camera |
| `/camera/front_right/image` | image | front-right camera |
| `/camera/left/image` | image | left camera |
| `/camera/right/image` | image | right camera |
| `/camera/rear/image` | image | rear camera |

## 3. State Report Contract

`/vehicle/state` is HAL feedback. In real mode it is decoded from STM32 `STATE_REPORT`. In simulation it may be synthesized by the simulator/HAL.

Current ROS fields:

| Field | Unit | Meaning |
|---|---|---|
| `steering_angle_rad` | rad | measured front steering angle |
| `wheel_speed_mps` | m/s | measured longitudinal wheel speed |
| `brake` | 0..1 | applied brake fraction |
| `battery_voltage` | V | pack voltage, 0 if unknown |
| `fault_code` | bitfield | 0 means OK |
| `estop` | bool | true while E-stop is latched |
| `heartbeat_ok` | bool | true when heartbeat is inside timeout |
| `dry_run` | bool | true when real actuation is disabled |

Target extensions: UPS state, motor enable state, brake state enum, last MCU sequence number, MCU uptime, transport counters.

## 4. Binary MCU Frame

The MCU path uses a deterministic custom binary protocol rather than Micro-ROS.

Current frame shape in `aris_mcu_bridge.protocol`:

| Field | Type | Size | Description |
|---|---:|---:|---|
| Magic | bytes | 2 | ASCII `AR` |
| Version | uint8 | 1 | protocol version, currently `1` |
| Message type | uint8 | 1 | enum value |
| Payload length | uint16 LE | 2 | payload byte length |
| Sequence | uint32 LE | 4 | monotonically increasing sender sequence |
| Payload | bytes | variable | message-specific payload |
| CRC32 | uint32 LE | 4 | CRC over header and payload |

Validation failures are communication faults: bad magic, unsupported version, unknown message type, bad length, CRC mismatch, sequence mismatch, payload schema mismatch.

## 5. Message Types

| Direction | Name | Type ID | Current Payload | Target Payload |
|---|---|---:|---|---|
| PC -> MCU | `CMD_CONTROL` | `0x01` | `float32 target_velocity_mps`, `float32 target_steering_rad`, `float32 brake` | optionally add mode through versioned payload or separate mode command |
| PC -> MCU | `CMD_HEARTBEAT` | `0x02` | empty | timestamp or monotonic heartbeat time |
| PC -> MCU | `CMD_ESTOP` | `0x03` | UTF-8 reason up to 128 bytes | reason code plus text |
| PC -> MCU | `CMD_MODE_SET` | `0x04` | reserved for protocol v2 | requested vehicle/autonomy mode |
| PC -> MCU | `CMD_CLEAR_FAULT` | `0x05` | reserved for protocol v2 | explicit operator-reviewed recovery command |
| MCU -> PC | `ACK` | `0x40` | reserved for protocol v2 | accepted sequence/message |
| MCU -> PC | `NACK` | `0x41` | reserved for protocol v2 | rejected sequence/message and reason |
| MCU -> PC | `STATE_REPORT` | `0x81` | `float32 steering_angle_rad`, `float32 wheel_speed_mps`, `float32 brake`, `float32 battery_voltage`, `uint16 fault_code`, `bool estop`, `bool heartbeat_ok`, `bool ups_ok` | steering, wheel speed, brake, battery, UPS, fault |
| MCU -> PC | `FAULT_REPORT` | `0x82` | `uint16 fault_code`, UTF-8 reason up to 128 bytes | overcurrent, power loss, E-stop, steering fault, comm fault |
| MCU -> PC | `SAFETY_EVENT` | `0x83` | reserved for protocol v2 | latched safety transition |

Compatibility note: the source PDF lists `CMD_CONTROL` fields as target speed, target steering, brake command, mode, and sequence. Protocol v1 carries sequence in the common header and speed/steering/brake in payload. Add mode only with a versioned payload change or separate command so older decoders fail cleanly.

## 6. Units, Ranges, and Timing

| Value | Unit | Range / Rule |
|---|---|---|
| Target velocity | m/s | non-negative in normal forward mode; bounded by active mode |
| Target steering | rad | bounded by URDF and controller config |
| Brake | fraction | 0.0 to 1.0 |
| Heartbeat timeout | seconds | 0.200 |
| Sequence | uint32 | wrap only with explicit receiver handling |
| Battery voltage | V | 0.0 means unknown |

Heartbeat behavior:

1. PC sends heartbeat faster than the 200 ms timeout.
2. MCU records the last valid heartbeat time.
3. If no valid heartbeat is seen for more than 200 ms, MCU enters safe stop.
4. Safe stop commands throttle 0 and brake apply.
5. E-stop immediately disables motor output and applies brake.

## 7. Fault Code Model

Recommended bitfield:

| Bit | Fault | Required Action |
|---:|---|---|
| 0 | communication fault | safe stop if active |
| 1 | heartbeat timeout | safe stop |
| 2 | E-stop latched | motor disable, brake apply |
| 3 | overcurrent | motor disable, brake apply |
| 4 | power loss | UPS logging, brake apply, state save |
| 5 | steering fault | reject steering output, brake apply |
| 6 | brake fault | inhibit motion |
| 7 | sequence fault | safe stop if repeated or active |

## 8. Physical Transport

Initial transport: USB UART for early debug and bench testing.

Final transport: CAN for electrical robustness and deterministic bus semantics.

Migration rule: binary payload schema and validation should remain transport-neutral. If CAN frame size requires fragmentation or compact fixed frames, introduce protocol version 2 with compatibility tests.

## 9. Required Protocol Tests

- Encode/decode every message.
- CRC failure.
- Unknown type.
- Bad length.
- Version mismatch.
- Sequence mismatch.
- Duplicate or reversed sequence if strict ordering is enabled.
- Heartbeat timeout boundary at 200 ms.
- Safe stop on communication fault.
- USB UART framing test before bench use.
- CAN bus-off handling before CAN field use.
