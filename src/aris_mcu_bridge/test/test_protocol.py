import pytest

from aris_mcu_bridge.protocol import (
    ControlCommand,
    HeartbeatMonitor,
    MessageType,
    ProtocolError,
    decode_control,
    decode_frame,
    encode_control,
    encode_frame,
    encode_heartbeat,
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
