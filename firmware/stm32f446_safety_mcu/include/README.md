# Include Directory

ARIS STM32 firmware is Rust-first. This directory is reserved for generated or hand-written C ABI headers if the safety MCU later exposes a C-compatible boundary for HIL tooling, bootloader integration, or external test harnesses.

Do not place actuator-enable defaults here. Real actuation remains disabled in firmware state until explicitly enabled and heartbeat safety is satisfied.
