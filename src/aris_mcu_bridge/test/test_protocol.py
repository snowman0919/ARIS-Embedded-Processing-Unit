import os
import pty
import time

import pytest

from aris_mcu_bridge.protocol import (
    ControlCommand,
    HeartbeatMonitor,
    MessageType,
    McuFaultReport,
    McuStateReport,
    ProtocolError,
    decode_control,
    decode_fault_report,
    decode_frame,
    decode_state_report,
    encode_control,
    encode_fault_report,
    encode_frame,
    encode_heartbeat,
    encode_state_report,
)
from aris_mcu_bridge.transport import (
    DryRunTransport,
    McuLink,
    MemoryTransport,
    SerialTransport,
    _pop_frame_from_buffer,
)


def test_roundtrip_encode_decode():
    encoded = encode_control(7, ControlCommand(1.5, 0.2, 0.0))
    frame = decode_frame(encoded, expected_sequence=7)
    command = decode_control(frame)
    assert frame.msg_type == MessageType.CMD_CONTROL
    assert command.target_velocity_mps == pytest.approx(1.5)
    assert command.target_steering_rad == pytest.approx(0.2)
    assert command.brake == pytest.approx(0.0)


def test_crc_failure_detection():
    encoded = bytearray(encode_heartbeat(1))
    encoded[-1] ^= 0xFF
    with pytest.raises(ProtocolError, match="crc"):
        decode_frame(bytes(encoded))


def test_sequence_mismatch():
    encoded = encode_frame(MessageType.STATE_REPORT, 10, b"ok")
    with pytest.raises(ProtocolError, match="sequence"):
        decode_frame(encoded, expected_sequence=11)


def test_heartbeat_timeout_simulation():
    monitor = HeartbeatMonitor(timeout_s=0.200)
    monitor.observe(now_s=100.0)
    assert not monitor.safe_stop_required(now_s=100.199)
    assert monitor.safe_stop_required(now_s=100.201)


def test_safe_stop_trigger_after_200_ms_timeout():
    monitor = HeartbeatMonitor()
    monitor.observe(now_s=1.0)
    assert monitor.safe_stop_required(now_s=1.201)


def test_mcu_link_writes_control_and_heartbeat_frames():
    transport = DryRunTransport()
    link = McuLink(transport)

    control_frame = link.send_control(ControlCommand(2.0, 0.1, 0.0))
    heartbeat_frame = link.send_heartbeat()

    assert transport.frames == [control_frame, heartbeat_frame]
    assert decode_frame(control_frame).msg_type == MessageType.CMD_CONTROL
    assert decode_frame(heartbeat_frame).msg_type == MessageType.CMD_HEARTBEAT
    assert decode_frame(heartbeat_frame).sequence == 2


def test_memory_transport_decodes_injected_rx_frame():
    transport = MemoryTransport()
    transport.inject_rx_frame(encode_frame(MessageType.STATE_REPORT, 9, b"ok"))

    frame = transport.read_frame()

    assert frame is not None
    assert frame.msg_type == MessageType.STATE_REPORT
    assert frame.sequence == 9
    assert frame.payload == b"ok"


def test_stream_parser_skips_noise_and_bad_crc():
    good = encode_heartbeat(4)
    bad = bytearray(encode_heartbeat(3))
    bad[-1] ^= 0xFF
    buffer = bytearray(b"noise" + bytes(bad) + good)

    frame = _pop_frame_from_buffer(buffer)

    assert frame is not None
    assert frame.msg_type == MessageType.CMD_HEARTBEAT
    assert frame.sequence == 4
    assert buffer == bytearray()


def test_state_report_payload_roundtrip():
    encoded = encode_state_report(
        12,
        McuStateReport(
            steering_angle_rad=0.12,
            wheel_speed_mps=1.5,
            brake=0.25,
            battery_voltage=48.5,
            fault_code=3,
            estop=True,
            heartbeat_ok=False,
            ups_ok=True,
        ),
    )

    report = decode_state_report(decode_frame(encoded))

    assert report.steering_angle_rad == pytest.approx(0.12)
    assert report.wheel_speed_mps == pytest.approx(1.5)
    assert report.brake == pytest.approx(0.25)
    assert report.battery_voltage == pytest.approx(48.5)
    assert report.fault_code == 3
    assert report.estop
    assert not report.heartbeat_ok
    assert report.ups_ok


def test_fault_report_payload_roundtrip():
    encoded = encode_fault_report(13, McuFaultReport(fault_code=5, reason="power_loss"))

    report = decode_fault_report(decode_frame(encoded))

    assert report.fault_code == 5
    assert report.reason == "power_loss"


def test_mcu_link_polls_state_report():
    transport = MemoryTransport()
    transport.inject_rx_frame(
        encode_state_report(
            1,
            McuStateReport(
                steering_angle_rad=0.2,
                wheel_speed_mps=0.3,
                brake=1.0,
                battery_voltage=12.0,
            ),
        )
    )
    link = McuLink(transport)

    report = link.poll_state_report()

    assert report is not None
    assert report.steering_angle_rad == pytest.approx(0.2)
    assert report.brake == pytest.approx(1.0)


def test_serial_transport_pty_loopback():
    master_fd, slave_fd = pty.openpty()
    slave_name = os.ttyname(slave_fd)
    os.close(slave_fd)
    transport = SerialTransport(slave_name, baud=115200)
    link = McuLink(transport)
    try:
        link.send_control(ControlCommand(1.2, 0.3, 0.0))
        raw = _read_fd_until_frame(master_fd)
        command = decode_control(decode_frame(raw))
        assert command.target_velocity_mps == pytest.approx(1.2)
        assert command.target_steering_rad == pytest.approx(0.3)

        os.write(
            master_fd,
            encode_state_report(
                99,
                McuStateReport(
                    steering_angle_rad=0.31,
                    wheel_speed_mps=1.1,
                    brake=0.0,
                    battery_voltage=51.0,
                ),
            ),
        )
        deadline = time.monotonic() + 1.0
        report = None
        while time.monotonic() < deadline and report is None:
            report = link.poll_state_report()
            time.sleep(0.01)

        assert report is not None
        assert report.steering_angle_rad == pytest.approx(0.31)
        assert report.battery_voltage == pytest.approx(51.0)
    finally:
        link.close()
        os.close(master_fd)


def _read_fd_until_frame(fd: int) -> bytes:
    buffer = bytearray()
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        try:
            chunk = os.read(fd, 4096)
        except BlockingIOError:
            chunk = b""
        if chunk:
            buffer.extend(chunk)
            parser_buffer = bytearray(buffer)
            frame = _pop_frame_from_buffer(parser_buffer)
            if frame is not None:
                return encode_frame(frame.msg_type, frame.sequence, frame.payload)
        time.sleep(0.01)
    raise AssertionError("timed out waiting for serial frame")
