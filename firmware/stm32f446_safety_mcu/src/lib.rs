#![cfg_attr(not(test), no_std)]

pub const HEARTBEAT_TIMEOUT_MS: u32 = 200;
pub const PROTOCOL_VERSION: u8 = 1;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Fault {
    NoHeartbeat,
    HeartbeatTimeout,
    EstopLatched,
    ActuationDisabled,
    SequenceMismatch,
    CrcFailure,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct ActuatorCommand {
    pub throttle: f32,
    pub brake: f32,
}

impl ActuatorCommand {
    pub const fn safe_stop() -> Self {
        Self {
            throttle: 0.0,
            brake: 1.0,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ProtocolState {
    expected_sequence: u32,
}

impl ProtocolState {
    pub const fn new() -> Self {
        Self {
            expected_sequence: 0,
        }
    }

    pub fn observe_sequence(&mut self, sequence: u32) -> Result<(), Fault> {
        if sequence != self.expected_sequence {
            return Err(Fault::SequenceMismatch);
        }
        self.expected_sequence = self.expected_sequence.wrapping_add(1);
        Ok(())
    }

    pub const fn expected_sequence(&self) -> u32 {
        self.expected_sequence
    }
}

impl Default for ProtocolState {
    fn default() -> Self {
        Self::new()
    }
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct SafetyState {
    last_heartbeat_ms: u32,
    heartbeat_seen: bool,
    estop_latched: bool,
    real_actuation_enabled: bool,
    command: ActuatorCommand,
}

impl SafetyState {
    pub const fn new() -> Self {
        Self {
            last_heartbeat_ms: 0,
            heartbeat_seen: false,
            estop_latched: false,
            real_actuation_enabled: false,
            command: ActuatorCommand::safe_stop(),
        }
    }

    pub fn set_real_actuation_enabled(&mut self, enabled: bool) {
        self.real_actuation_enabled = enabled;
        if !enabled {
            self.command = ActuatorCommand::safe_stop();
        }
    }

    pub fn observe_heartbeat(&mut self, now_ms: u32) {
        self.last_heartbeat_ms = now_ms;
        self.heartbeat_seen = true;
    }

    pub fn latch_estop(&mut self) {
        self.estop_latched = true;
        self.command = ActuatorCommand::safe_stop();
    }

    pub fn safe_stop_reason(&self, now_ms: u32) -> Option<Fault> {
        if !self.real_actuation_enabled {
            return Some(Fault::ActuationDisabled);
        }
        if self.estop_latched {
            return Some(Fault::EstopLatched);
        }
        if !self.heartbeat_seen {
            return Some(Fault::NoHeartbeat);
        }
        if now_ms.wrapping_sub(self.last_heartbeat_ms) > HEARTBEAT_TIMEOUT_MS {
            return Some(Fault::HeartbeatTimeout);
        }
        None
    }

    pub fn safe_stop_required(&self, now_ms: u32) -> bool {
        self.safe_stop_reason(now_ms).is_some()
    }

    pub fn apply_command(&mut self, command: ActuatorCommand, now_ms: u32) -> ActuatorCommand {
        if self.safe_stop_required(now_ms) {
            self.command = ActuatorCommand::safe_stop();
        } else {
            self.command = command;
        }
        self.command
    }

    pub const fn command(&self) -> ActuatorCommand {
        self.command
    }
}

impl Default for SafetyState {
    fn default() -> Self {
        Self::new()
    }
}

pub fn validate_crc(crc_ok: bool) -> Result<(), Fault> {
    if crc_ok {
        Ok(())
    } else {
        Err(Fault::CrcFailure)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_state_requires_safe_stop() {
        let state = SafetyState::new();
        assert_eq!(state.safe_stop_reason(0), Some(Fault::ActuationDisabled));
        assert_eq!(state.command(), ActuatorCommand::safe_stop());
    }

    #[test]
    fn heartbeat_timeout_triggers_after_200_ms() {
        let mut state = SafetyState::new();
        state.set_real_actuation_enabled(true);
        state.observe_heartbeat(1000);
        assert_eq!(state.safe_stop_reason(1200), None);
        assert_eq!(state.safe_stop_reason(1201), Some(Fault::HeartbeatTimeout));
    }

    #[test]
    fn command_is_blocked_until_real_actuation_is_enabled() {
        let mut state = SafetyState::new();
        state.observe_heartbeat(0);
        let applied = state.apply_command(
            ActuatorCommand {
                throttle: 0.4,
                brake: 0.0,
            },
            1,
        );
        assert_eq!(applied, ActuatorCommand::safe_stop());
    }

    #[test]
    fn sequence_mismatch_is_faulted() {
        let mut protocol = ProtocolState::new();
        assert_eq!(protocol.observe_sequence(0), Ok(()));
        assert_eq!(protocol.observe_sequence(2), Err(Fault::SequenceMismatch));
    }

    #[test]
    fn crc_failure_is_faulted() {
        assert_eq!(validate_crc(false), Err(Fault::CrcFailure));
        assert_eq!(validate_crc(true), Ok(()));
    }
}
