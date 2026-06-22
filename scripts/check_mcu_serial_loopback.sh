#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
aris_load_env

cd "$ARIS_WS"
./scripts/check_python_tests.sh src/aris_mcu_bridge/test/test_protocol.py::test_serial_transport_pty_loopback
