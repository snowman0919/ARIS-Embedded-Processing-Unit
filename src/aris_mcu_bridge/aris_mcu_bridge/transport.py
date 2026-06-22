"""Transport boundary for the ARIS safety MCU link.

The binary protocol stays transport-neutral. This module owns the last hop to
the MCU so ROS nodes can exercise the same frame path in dry-run, tests, serial
bench sessions, and later CAN adapters.
"""

from __future__ import annotations

import os
import termios
from collections import deque
from dataclasses import dataclass, field
from typing import Protocol

from .protocol import (
    CRC,
    HEADER,
    MAGIC,
    ControlCommand,
    Frame,
    McuFaultReport,
    McuStateReport,
    MessageType,
    ProtocolError,
    decode_frame,
    decode_fault_report,
    decode_state_report,
    encode_control,
    encode_estop,
    encode_heartbeat,
)


class TransportError(OSError):
    """Raised when an MCU transport cannot be opened or written."""


class McuTransport(Protocol):
    def write_frame(self, frame: bytes) -> None:
        """Write one complete protocol frame."""

    def read_frame(self) -> Frame | None:
        """Return one decoded frame when available, otherwise None."""

    def close(self) -> None:
        """Release transport resources."""


@dataclass
class DryRunTransport:
    """Transport that records frames without touching hardware."""

    frames: list[bytes] = field(default_factory=list)

    def write_frame(self, frame: bytes) -> None:
        self.frames.append(bytes(frame))

    def read_frame(self) -> Frame | None:
        return None

    def close(self) -> None:
        return None


@dataclass
class MemoryTransport:
    """Deterministic in-memory transport for tests and loopback tools."""

    tx_frames: list[bytes] = field(default_factory=list)
    rx_frames: deque[bytes] = field(default_factory=deque)

    def write_frame(self, frame: bytes) -> None:
        self.tx_frames.append(bytes(frame))

    def inject_rx_frame(self, frame: bytes) -> None:
        self.rx_frames.append(bytes(frame))

    def read_frame(self) -> Frame | None:
        if not self.rx_frames:
            return None
        return decode_frame(self.rx_frames.popleft())

    def close(self) -> None:
        self.rx_frames.clear()


class SerialTransport:
    """POSIX serial transport using only the Python standard library."""

    def __init__(self, device: str, baud: int = 115200) -> None:
        if not device:
            raise TransportError("serial device path is required")
        self.device = device
        self.baud = baud
        self._buffer = bytearray()
        try:
            self._fd = os.open(device, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
            self._configure_port(self._fd, baud)
        except OSError as exc:
            raise TransportError(f"failed to open serial device {device}: {exc}") from exc

    def write_frame(self, frame: bytes) -> None:
        view = memoryview(frame)
        while view:
            try:
                written = os.write(self._fd, view)
            except BlockingIOError:
                continue
            if written <= 0:
                raise TransportError("serial write returned zero bytes")
            view = view[written:]

    def read_frame(self) -> Frame | None:
        while True:
            try:
                chunk = os.read(self._fd, 4096)
            except BlockingIOError:
                break
            if not chunk:
                break
            self._buffer.extend(chunk)
        return _pop_frame_from_buffer(self._buffer)

    def close(self) -> None:
        if getattr(self, "_fd", None) is not None:
            os.close(self._fd)
            self._fd = None

    @staticmethod
    def _configure_port(fd: int, baud: int) -> None:
        attrs = termios.tcgetattr(fd)
        speed = _baud_constant(baud)
        attrs[0] = 0
        attrs[1] = 0
        attrs[2] = termios.CLOCAL | termios.CREAD | termios.CS8
        attrs[3] = 0
        attrs[4] = speed
        attrs[5] = speed
        attrs[6][termios.VMIN] = 0
        attrs[6][termios.VTIME] = 0
        termios.tcsetattr(fd, termios.TCSANOW, attrs)


@dataclass
class McuLink:
    """Versioned safety-MCU link built on the binary protocol."""

    transport: McuTransport
    sequence: int = 0

    def send_control(self, command: ControlCommand) -> bytes:
        return self._write(MessageType.CMD_CONTROL, encode_control(self._next_sequence(), command))

    def send_heartbeat(self) -> bytes:
        return self._write(MessageType.CMD_HEARTBEAT, encode_heartbeat(self._next_sequence()))

    def send_estop(self, reason: str = "operator") -> bytes:
        return self._write(MessageType.CMD_ESTOP, encode_estop(self._next_sequence(), reason))

    def poll(self) -> Frame | None:
        return self.transport.read_frame()

    def poll_state_report(self) -> McuStateReport | None:
        frame = self.poll()
        if frame is None:
            return None
        if frame.msg_type == MessageType.STATE_REPORT:
            return decode_state_report(frame)
        return None

    def poll_fault_report(self) -> McuFaultReport | None:
        frame = self.poll()
        if frame is None:
            return None
        if frame.msg_type == MessageType.FAULT_REPORT:
            return decode_fault_report(frame)
        return None

    def close(self) -> None:
        self.transport.close()

    def _next_sequence(self) -> int:
        self.sequence = (self.sequence + 1) & 0xFFFFFFFF
        return self.sequence

    def _write(self, msg_type: MessageType, frame: bytes) -> bytes:
        # msg_type keeps call sites self-documenting and makes future hooks easy.
        _ = msg_type
        self.transport.write_frame(frame)
        return frame


def create_transport(kind: str, *, serial_device: str = "", serial_baud: int = 115200) -> McuTransport:
    normalized = kind.strip().lower()
    if normalized in {"dry-run", "dry_run", "dryrun", ""}:
        return DryRunTransport()
    if normalized == "serial":
        return SerialTransport(serial_device, baud=serial_baud)
    if normalized == "memory":
        return MemoryTransport()
    raise TransportError(f"unsupported MCU transport kind: {kind}")


def _pop_frame_from_buffer(buffer: bytearray) -> Frame | None:
    while buffer:
        magic_index = buffer.find(MAGIC)
        if magic_index < 0:
            del buffer[:]
            return None
        if magic_index > 0:
            del buffer[:magic_index]
        if len(buffer) < HEADER.size:
            return None
        _, _, _, payload_len, _ = HEADER.unpack(bytes(buffer[: HEADER.size]))
        frame_len = HEADER.size + payload_len + CRC.size
        if len(buffer) < frame_len:
            return None
        raw_frame = bytes(buffer[:frame_len])
        del buffer[:frame_len]
        try:
            return decode_frame(raw_frame)
        except ProtocolError:
            continue
    return None


def _baud_constant(baud: int) -> int:
    name = f"B{int(baud)}"
    if not hasattr(termios, name):
        raise TransportError(f"unsupported serial baud rate: {baud}")
    return int(getattr(termios, name))
