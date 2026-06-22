# Embedded

The embedded container provides Rust for STM32, ARM embedded GCC/binutils for low-level support, OpenOCD, probe-rs where available, and native firmware simulation tests.

Run:

```bash
just firmware-test
```

This runs host-side Rust tests, formatting, clippy, and a `thumbv7em-none-eabihf` build for STM32F446 inside `aris-embedded-dev`. It does not require hardware.

Flashing and HIL require explicit USB access through hardware mode and must keep real actuators disconnected until safe-stop behavior has been validated.
