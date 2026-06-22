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

from .protocol import ControlCommand, HeartbeatMonitor, McuStateReport
from .transport import McuLink, TransportError, create_transport


class McuBridgeNode(Node):
    def __init__(self) -> None:
        super().__init__("aris_mcu_bridge")
        self.declare_parameter("heartbeat_timeout_s", 0.2)
        self.declare_parameter("control_rate_hz", 50.0)
        self.declare_parameter("state_rate_hz", 20.0)
        self.declare_parameter("transport", "dry-run")
        self.declare_parameter("serial_device", "")
        self.declare_parameter("serial_baud", 115200)

        self.monitor = HeartbeatMonitor(
            timeout_s=float(self.get_parameter("heartbeat_timeout_s").value)
        )
        self.dry_run = os.environ.get("ARIS_ENABLE_REAL_ACTUATION", "0") != "1"
        self.last_command = ControlCommand(0.0, 0.0, 0.0)
        self.last_mcu_state: McuStateReport | None = None
        self.last_estop_published: bool | None = None
        transport_kind = str(self.get_parameter("transport").value)
        if self.dry_run and transport_kind == "serial":
            self.get_logger().warn("Ignoring serial transport while ARIS_ENABLE_REAL_ACTUATION is not 1.")
            transport_kind = "dry-run"
        try:
            self.link = McuLink(
                create_transport(
                    transport_kind,
                    serial_device=str(self.get_parameter("serial_device").value),
                    serial_baud=int(self.get_parameter("serial_baud").value),
                )
            )
        except TransportError as exc:
            raise RuntimeError(f"failed to initialize MCU transport: {exc}") from exc

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
        # Dry-run and real mode both traverse the same binary link path. The
        # selected transport decides whether frames are recorded or sent out.
        try:
            self.link.send_control(self.last_command)
            state = self.link.poll_state_report()
            if state is not None:
                self.last_mcu_state = state
        except TransportError as exc:
            self.get_logger().error(f"MCU transport write failed: {exc}")
            self._publish_estop(True)
            return

        self._publish_estop(self.monitor.safe_stop_required())

    def _state_tick(self) -> None:
        safe_stop = self.monitor.safe_stop_required()
        report = StateReport()
        report.header.stamp = self.get_clock().now().to_msg()
        report.header.frame_id = "base_link"
        if self.last_mcu_state is not None:
            report.steering_angle_rad = self.last_mcu_state.steering_angle_rad
            report.wheel_speed_mps = self.last_mcu_state.wheel_speed_mps
            report.brake = self.last_mcu_state.brake
            report.battery_voltage = self.last_mcu_state.battery_voltage
            report.fault_code = self.last_mcu_state.fault_code
            report.estop = bool(safe_stop or self.last_mcu_state.estop)
            report.heartbeat_ok = (not safe_stop) and self.last_mcu_state.heartbeat_ok
        else:
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
        node.link.close()
        node.destroy_node()
        rclpy.shutdown()
