use aris_stm32f446_safety_mcu::{validate_crc, ActuatorCommand, Fault, ProtocolState, SafetyState};

#[test]
fn integration_safe_stop_after_heartbeat_timeout() {
    let mut state = SafetyState::new();
    state.set_real_actuation_enabled(true);
    state.observe_heartbeat(5_000);

    assert!(!state.safe_stop_required(5_200));
    assert_eq!(state.safe_stop_reason(5_201), Some(Fault::HeartbeatTimeout));
}

#[test]
fn integration_real_command_requires_enable_and_heartbeat() {
    let mut state = SafetyState::new();
    state.observe_heartbeat(10);

    let applied = state.apply_command(
        ActuatorCommand {
            throttle: 0.25,
            brake: 0.0,
        },
        20,
    );

    assert_eq!(applied, ActuatorCommand::safe_stop());
}

#[test]
fn integration_protocol_faults_are_explicit() {
    let mut protocol = ProtocolState::new();
    assert_eq!(protocol.observe_sequence(0), Ok(()));
    assert_eq!(protocol.observe_sequence(0), Err(Fault::SequenceMismatch));
    assert_eq!(validate_crc(false), Err(Fault::CrcFailure));
}
