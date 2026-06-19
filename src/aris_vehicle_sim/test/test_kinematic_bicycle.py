from aris_vehicle_sim.kinematic_bicycle import KinematicBicycleModel, VehicleState


def test_bicycle_model_moves_forward():
    state = VehicleState()
    model = KinematicBicycleModel()
    model.step(state, target_velocity_mps=1.0, target_steering_rad=0.0, dt_s=1.0)
    assert state.x > 0.0
    assert abs(state.y) < 1e-9


def test_bicycle_model_turns():
    state = VehicleState(velocity_mps=1.0)
    model = KinematicBicycleModel()
    model.step(state, target_velocity_mps=1.0, target_steering_rad=0.2, dt_s=1.0)
    assert state.yaw > 0.0
