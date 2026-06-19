# Safety

Real motors and brakes must remain disconnected during early development.

Rules:

- All real actuation requires explicit `ARIS_ENABLE_REAL_ACTUATION=1`.
- The default bridge is dry-run.
- The heartbeat timeout is 200 ms.
- Loss of heartbeat must result in throttle 0, brake apply, and safe stop.
- Safe stop must be tested before any vehicle bench test.
- AI output is advisory only and must never directly command steering, throttle, or brake.

Hardware mode is opt-in and must be reviewed before use.
