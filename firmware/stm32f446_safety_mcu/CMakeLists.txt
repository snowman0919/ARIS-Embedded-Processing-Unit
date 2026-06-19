cmake_minimum_required(VERSION 3.22)
project(aris_stm32f446_safety_mcu_rust NONE)

# ARIS firmware is Rust-first. This CMake file exists only for tooling that
# expects a CMake entry point and delegates to Cargo.
set(ARIS_FIRMWARE_MANIFEST "${CMAKE_CURRENT_SOURCE_DIR}/Cargo.toml")
set(ARIS_FIRMWARE_TARGET "thumbv7em-none-eabihf" CACHE STRING "Rust target for STM32F446")

find_program(CARGO_EXECUTABLE cargo REQUIRED)

add_custom_target(aris_firmware_test
  COMMAND "${CARGO_EXECUTABLE}" test --manifest-path "${ARIS_FIRMWARE_MANIFEST}"
  WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
  COMMENT "Running host-side Rust safety-core tests"
)

add_custom_target(aris_firmware_build
  COMMAND "${CARGO_EXECUTABLE}" build --manifest-path "${ARIS_FIRMWARE_MANIFEST}" --target "${ARIS_FIRMWARE_TARGET}"
  WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
  COMMENT "Building Rust firmware for ${ARIS_FIRMWARE_TARGET}"
)
