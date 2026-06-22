# Embedded

This processing-unit repository owns the ROS 2 MCU bridge, binary protocol implementation, and
hardware-free serial loopback checks. Standalone STM32 firmware sources live in
`snowman0919/ARIS-Embedded-MCU`.

For current repository readiness evidence, run:

```bash
just embedded-dry-run
```

This runs the MCU bridge protocol tests, protocol reference tests, and PTY serial loopback transport
test. It writes `$ARIS_LOGS/embedded/embedded_dry_run_<timestamp>.json` and updates
`$ARIS_LOGS/embedded/latest_embedded_dry_run.json`. It does not require hardware.

If a checkout includes `firmware/stm32f446_safety_mcu`, the legacy firmware target can be exercised
with:

```bash
just firmware-test
```

That path runs Rust tests, formatting, clippy, and a `thumbv7em-none-eabihf` build inside
`aris-embedded-dev`.

Flashing and HIL require explicit USB access through hardware mode and must keep real actuators disconnected until safe-stop behavior has been validated.
