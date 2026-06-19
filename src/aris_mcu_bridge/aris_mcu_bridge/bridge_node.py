"""STM32 bridge ROS wrapper (the real-vehicle side of the HAL).

Consumes the same /cmd_drive contract topic as the simulator, encodes each
command as the binary CMD_CONTROL frame (protocol.py), and reports vehicle state
on /vehicle/state. Output stays in dry-run unless ARIS_ENABLE_REAL_ACTUATION=1,
so this node is safe to run in simulation. A lost command stream trips the
200 ms heartbeat watchdog and raises /estop, mirroring the MCU safe-stop.

The algorithm nodes never change between sim and real; only which bridge is
launched does (the use_sim switch).
"""

from __future__ import annotations

import os

import rclpy
from ackermann_msgs.msg import AckermannDriveStamped
from rclpy.node import Node
from std_msgs.msg import Bool

from aris_interfaces.msg import StateReport

from .protocol import ControlCommand, HeartbeatMonitor, encode_control


class McuBridgeNode(Node):
    def __init__(self) -> None:
        super().__init__("aris_mcu_bridge")
        self.declare_parameter("heartbeat_timeout_s", 0.2)
        self.declare_parameter("control_rate_hz", 50.0)
        self.declare_parameter("state_rate_hz", 20.0)

        self.monitor = HeartbeatMonitor(
            timeout_s=float(self.get_parameter("heartbeat_timeout_s").value)
        )
        self.dry_run = os.environ.get("ARIS_ENABLE_REAL_ACTUATION", "0") != "1"
        self.sequence = 0
        self.last_command = ControlCommand(0.0, 0.0, 0.0)
        self.last_estop_published: bool | None = None

        self.estop_pub = self.create_publisher(Bool, "/estop", 10)
        self.state_pub = self.create_publisher(StateReport, "/vehicle/state", 10)
        self.create_subscription(AckermannDriveStamped, "/cmd_drive", self._on_cmd_drive, 10)
        self.create_timer(
            1.0 / float(self.get_parameter("control_rate_hz").value), self._control_tick
        )
        self.create_timer(
            1.0 / float(self.get_parameter("state_rate_hz").value), self._state_tick
        )

        mode = "DRY-RUN (no actuation)" if self.dry_run else "REAL ACTUATION ENABLED"
        self.get_logger().info(f"ARIS MCU bridge up: {mode}. Heartbeat watchdog 200 ms.")

    def _on_cmd_drive(self, msg: AckermannDriveStamped) -> None:
        brake = max(0.0, -float(msg.drive.acceleration))
        self.last_command = ControlCommand(
            target_velocity_mps=float(msg.drive.speed),
            target_steering_rad=float(msg.drive.steering_angle),
            brake=brake,
        )
        self.monitor.observe()

    def _control_tick(self) -> None:
        # Build the binary frame every cycle so the protocol path is exercised
        # even in dry-run; only real mode writes it to the serial/CAN link.
        self.sequence = (self.sequence + 1) & 0xFFFFFFFF
        frame = encode_control(self.sequence, self.last_command)
        if not self.dry_run:
            # TODO(real-hal): write `frame` to the STM32 serial/CAN transport.
            _ = frame

        self._publish_estop(self.monitor.safe_stop_required())

    def _state_tick(self) -> None:
        safe_stop = self.monitor.safe_stop_required()
        report = StateReport()
        report.header.stamp = self.get_clock().now().to_msg()
        report.header.frame_id = "base_link"
        report.steering_angle_rad = self.last_command.target_steering_rad
        report.wheel_speed_mps = self.last_command.target_velocity_mps
        report.brake = self.last_command.brake
        report.battery_voltage = 0.0
        report.fault_code = 0
        report.estop = bool(safe_stop)
        report.heartbeat_ok = not safe_stop
        report.dry_run = bool(self.dry_run)
        self.state_pub.publish(report)

    def _publish_estop(self, value: bool) -> None:
        if value == self.last_estop_published:
            return
        self.last_estop_published = value
        self.estop_pub.publish(Bool(data=value))


def main() -> None:
    rclpy.init()
    node = McuBridgeNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
