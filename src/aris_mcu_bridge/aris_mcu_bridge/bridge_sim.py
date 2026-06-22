from __future__ import annotations

import time

from .protocol import HeartbeatMonitor


def main() -> None:
    monitor = HeartbeatMonitor()
    monitor.observe()
    print("ARIS MCU bridge simulation running in dry-run mode.")
    print("Real actuation requires ARIS_ENABLE_REAL_ACTUATION=1 and hardware-mode launch.")
    while True:
        if monitor.safe_stop_required():
            print("safe-stop: heartbeat timeout exceeded 200 ms")
            monitor.observe()
        time.sleep(0.05)
