# MCU Protocol

The starter MCU protocol is framed binary:

- Magic bytes: `AR`.
- Version: `1`.
- Message type.
- Payload length.
- Sequence.
- Payload.
- CRC32.

Message types:

- `CMD_CONTROL`
- `CMD_HEARTBEAT`
- `CMD_ESTOP`
- `STATE_REPORT`
- `FAULT_REPORT`

Implemented payloads:

- `CMD_CONTROL`: `float32 target_velocity_mps`, `float32 target_steering_rad`, `float32 brake`.
- `STATE_REPORT`: `float32 steering_angle_rad`, `float32 wheel_speed_mps`, `float32 brake`,
  `float32 battery_voltage`, `uint16 fault_code`, `bool estop`, `bool heartbeat_ok`,
  `bool ups_ok`.
- `FAULT_REPORT`: `uint16 fault_code`, UTF-8 reason string up to 128 bytes.

CRC failure, unknown message type, unsupported version, malformed length, or sequence mismatch must be treated as communication faults. Loss of heartbeat for more than 200 ms requires safe stop.

Python reference implementation:

```text
src/aris_mcu_bridge/aris_mcu_bridge/protocol.py
```

For the final architecture-level protocol contract, see `communication_protocol.md`.
