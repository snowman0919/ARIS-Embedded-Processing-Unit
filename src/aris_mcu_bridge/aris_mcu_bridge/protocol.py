from __future__ import annotations

import enum
import struct
import time
import zlib
from dataclasses import dataclass

MAGIC = b"AR"
VERSION = 1
HEADER = struct.Struct("<2sBBHI")
CRC = struct.Struct("<I")
CONTROL_PAYLOAD = struct.Struct("<fff")
STATE_REPORT_PAYLOAD = struct.Struct("<ffffH???")
HEARTBEAT_TIMEOUT_S = 0.200


class MessageType(enum.IntEnum):
    CMD_CONTROL = 0x01
    CMD_HEARTBEAT = 0x02
    CMD_ESTOP = 0x03
    STATE_REPORT = 0x81
    FAULT_REPORT = 0x82


class ProtocolError(ValueError):
    """Raised when a frame is malformed or fails validation."""


@dataclass(frozen=True)
class Frame:
    msg_type: MessageType
    sequence: int
    payload: bytes = b""
    version: int = VERSION


@dataclass(frozen=True)
class ControlCommand:
    target_velocity_mps: float
    target_steering_rad: float
    brake: float


@dataclass(frozen=True)
class McuStateReport:
    steering_angle_rad: float
    wheel_speed_mps: float
    brake: float
    battery_voltage: float
    fault_code: int = 0
    estop: bool = False
    heartbeat_ok: bool = True
    ups_ok: bool = True


@dataclass(frozen=True)
class McuFaultReport:
    fault_code: int
    reason: str


def encode_frame(msg_type: MessageType, sequence: int, payload: bytes = b"") -> bytes:
    if not 0 <= sequence <= 0xFFFFFFFF:
        raise ProtocolError("sequence must fit uint32")
    if len(payload) > 0xFFFF:
        raise ProtocolError("payload too large")
    header = HEADER.pack(MAGIC, VERSION, int(msg_type), len(payload), sequence)
    crc = zlib.crc32(header + payload) & 0xFFFFFFFF
    return header + payload + CRC.pack(crc)


def decode_frame(data: bytes, expected_sequence: int | None = None) -> Frame:
    min_len = HEADER.size + CRC.size
    if len(data) < min_len:
        raise ProtocolError("frame too short")
    magic, version, msg_type_raw, payload_len, sequence = HEADER.unpack(data[: HEADER.size])
    if magic != MAGIC:
        raise ProtocolError("bad magic")
    if version != VERSION:
        raise ProtocolError(f"unsupported protocol version {version}")
    expected_len = HEADER.size + payload_len + CRC.size
    if len(data) != expected_len:
        raise ProtocolError(f"bad frame length: expected {expected_len}, got {len(data)}")
    payload = data[HEADER.size : HEADER.size + payload_len]
    actual_crc = CRC.unpack(data[-CRC.size :])[0]
    expected_crc = zlib.crc32(data[:-CRC.size]) & 0xFFFFFFFF
    if actual_crc != expected_crc:
        raise ProtocolError("crc mismatch")
    if expected_sequence is not None and sequence != expected_sequence:
        raise ProtocolError(f"sequence mismatch: expected {expected_sequence}, got {sequence}")
    try:
        msg_type = MessageType(msg_type_raw)
    except ValueError as exc:
        raise ProtocolError(f"unknown message type 0x{msg_type_raw:02x}") from exc
    return Frame(msg_type=msg_type, sequence=sequence, payload=payload, version=version)


def encode_control(sequence: int, command: ControlCommand) -> bytes:
    payload = CONTROL_PAYLOAD.pack(
        command.target_velocity_mps,
        command.target_steering_rad,
        command.brake,
    )
    return encode_frame(MessageType.CMD_CONTROL, sequence, payload)


def decode_control(frame: Frame) -> ControlCommand:
    if frame.msg_type != MessageType.CMD_CONTROL:
        raise ProtocolError("not a control command frame")
    if len(frame.payload) != CONTROL_PAYLOAD.size:
        raise ProtocolError("control payload must be 12 bytes")
    velocity, steering, brake = CONTROL_PAYLOAD.unpack(frame.payload)
    return ControlCommand(velocity, steering, brake)


def encode_heartbeat(sequence: int) -> bytes:
    return encode_frame(MessageType.CMD_HEARTBEAT, sequence)


def encode_estop(sequence: int, reason: str = "operator") -> bytes:
    return encode_frame(MessageType.CMD_ESTOP, sequence, reason.encode("utf-8")[:128])


def encode_state_report(sequence: int, report: McuStateReport) -> bytes:
    if not 0 <= report.fault_code <= 0xFFFF:
        raise ProtocolError("fault_code must fit uint16")
    payload = STATE_REPORT_PAYLOAD.pack(
        report.steering_angle_rad,
        report.wheel_speed_mps,
        report.brake,
        report.battery_voltage,
        report.fault_code,
        report.estop,
        report.heartbeat_ok,
        report.ups_ok,
    )
    return encode_frame(MessageType.STATE_REPORT, sequence, payload)


def decode_state_report(frame: Frame) -> McuStateReport:
    if frame.msg_type != MessageType.STATE_REPORT:
        raise ProtocolError("not a state report frame")
    if len(frame.payload) != STATE_REPORT_PAYLOAD.size:
        raise ProtocolError("state report payload has wrong size")
    steering, wheel_speed, brake, battery, fault_code, estop, heartbeat_ok, ups_ok = (
        STATE_REPORT_PAYLOAD.unpack(frame.payload)
    )
    return McuStateReport(
        steering_angle_rad=steering,
        wheel_speed_mps=wheel_speed,
        brake=brake,
        battery_voltage=battery,
        fault_code=fault_code,
        estop=estop,
        heartbeat_ok=heartbeat_ok,
        ups_ok=ups_ok,
    )


def encode_fault_report(sequence: int, report: McuFaultReport) -> bytes:
    if not 0 <= report.fault_code <= 0xFFFF:
        raise ProtocolError("fault_code must fit uint16")
    reason = report.reason.encode("utf-8")[:128]
    payload = struct.pack("<H", report.fault_code) + reason
    return encode_frame(MessageType.FAULT_REPORT, sequence, payload)


def decode_fault_report(frame: Frame) -> McuFaultReport:
    if frame.msg_type != MessageType.FAULT_REPORT:
        raise ProtocolError("not a fault report frame")
    if len(frame.payload) < 2:
        raise ProtocolError("fault report payload too short")
    fault_code = struct.unpack("<H", frame.payload[:2])[0]
    reason = frame.payload[2:].decode("utf-8", errors="replace")
    return McuFaultReport(fault_code=fault_code, reason=reason)


class HeartbeatMonitor:
    def __init__(self, timeout_s: float = HEARTBEAT_TIMEOUT_S) -> None:
        self.timeout_s = timeout_s
        self.last_heartbeat_s: float | None = None

    def observe(self, now_s: float | None = None) -> None:
        self.last_heartbeat_s = time.monotonic() if now_s is None else now_s

    def timed_out(self, now_s: float | None = None) -> bool:
        if self.last_heartbeat_s is None:
            return True
        now = time.monotonic() if now_s is None else now_s
        return (now - self.last_heartbeat_s) > self.timeout_s

    def safe_stop_required(self, now_s: float | None = None) -> bool:
        return self.timed_out(now_s)


def dry_run_actuation_enabled() -> bool:
    """Real output remains disabled unless the operator explicitly opts in."""
    import os

    return os.environ.get("ARIS_ENABLE_REAL_ACTUATION", "0") == "1"
