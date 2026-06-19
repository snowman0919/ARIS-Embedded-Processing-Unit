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

CRC failure, unknown message type, unsupported version, malformed length, or sequence mismatch must be treated as communication faults. Loss of heartbeat for more than 200 ms requires safe stop.

Python reference implementation:

```text
src/aris_mcu_bridge/aris_mcu_bridge/protocol.py
```
