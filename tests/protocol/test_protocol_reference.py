from aris_mcu_bridge.protocol import HeartbeatMonitor, MessageType, decode_frame, encode_estop


def test_estop_frame_reference():
    frame = decode_frame(encode_estop(42, "test"))
    assert frame.msg_type == MessageType.CMD_ESTOP
    assert frame.sequence == 42
    assert frame.payload == b"test"


def test_safe_stop_reference_timeout_boundary():
    monitor = HeartbeatMonitor(timeout_s=0.2)
    monitor.observe(now_s=10.0)
    assert not monitor.safe_stop_required(now_s=10.2)
    assert monitor.safe_stop_required(now_s=10.2001)
