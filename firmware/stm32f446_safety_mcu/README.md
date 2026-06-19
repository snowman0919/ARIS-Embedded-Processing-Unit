# STM32F446 Safety MCU Rust Starter

This firmware scaffold is the Rust-first path for the ARIS safety MCU. The starter crate is a small `no_std` safety core that can be unit-tested on the host and built for the STM32F446 Cortex-M4F target.

Safety defaults:

- Real actuator enable is off by default.
- Loss of heartbeat for more than 200 ms must force throttle 0, brake apply, and safe stop.
- Protocol frames must include version, sequence, and CRC checks.
- Sequence mismatch or CRC failure must be treated as a communication fault.
- Protocol changes must bump or explicitly document the protocol version.

Development flow inside the embedded container:

```bash
just firmware-test
```

That command runs:

- `cargo test` for host-side simulated safety logic.
- `cargo fmt --check`.
- `cargo clippy -D warnings`.
- `cargo build --target thumbv7em-none-eabihf`.

Direct commands:

```bash
cargo test --manifest-path firmware/stm32f446_safety_mcu/Cargo.toml
./scripts/run_embedded.sh cargo build --manifest-path firmware/stm32f446_safety_mcu/Cargo.toml --target thumbv7em-none-eabihf
```

The default test path is simulated and does not require hardware.

Hardware-in-the-loop flashing requires explicit USB device access through the `hardware` Compose profile or a dedicated helper command. Do not assume STM32CubeIDE. Use Cargo, OpenOCD, and probe-rs where applicable, and keep real motors/brakes disconnected during early development.

Rust target:

- STM32F446 is Cortex-M4F, so the starter target is `thumbv7em-none-eabihf`.
- The crate is `no_std` outside tests.
- HAL/PAC dependencies are intentionally not added yet; introduce `stm32f4xx-hal`, `cortex-m-rt`, and a linker script when board pinout and clock configuration are chosen.

`CMakeLists.txt` is a compatibility shim for tools that expect CMake. It delegates to Cargo and does not introduce a C firmware path.
