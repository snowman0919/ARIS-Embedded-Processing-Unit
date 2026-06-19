import pytest

from aris_planning.astar import CellCost, GridPlanner
from aris_planning.pure_pursuit import Pose2D, PurePursuit


def test_astar_finds_path_around_obstacle():
    planner = GridPlanner(width=5, height=5, blocked={(1, 0), (1, 1), (1, 2)})
    path = planner.plan((0, 0), (4, 4))
    assert path[0] == (0, 0)
    assert path[-1] == (4, 4)
    assert not any(point in planner.blocked for point in path)


def test_astar_uses_semantic_penalty():
    planner = GridPlanner(
        width=4,
        height=3,
        blocked=set(),
        costs={(1, 1): CellCost(semantic_penalty=50.0), (2, 1): CellCost(semantic_penalty=50.0)},
    )
    path = planner.plan((0, 1), (3, 1))
    assert (1, 1) not in path
    assert (2, 1) not in path


def test_astar_no_path():
    planner = GridPlanner(width=2, height=2, blocked={(1, 0), (0, 1)})
    with pytest.raises(ValueError, match="no path"):
        planner.plan((0, 0), (1, 1))


def test_pure_pursuit_dry_run_by_default(monkeypatch):
    monkeypatch.delenv("ARIS_ENABLE_REAL_ACTUATION", raising=False)
    command = PurePursuit().command(Pose2D(0.0, 0.0, 0.0), [(3.0, 0.2)])
    assert command.target_velocity_mps > 0.0
    assert command.brake == 0.0
    assert command.dry_run is True


def test_pure_pursuit_estop_brakes():
    command = PurePursuit().command(Pose2D(0.0, 0.0, 0.0), [(3.0, 0.0)], estop=True)
    assert command.target_velocity_mps == 0.0
    assert command.brake == 1.0


def test_pure_pursuit_ignores_waypoints_behind_vehicle():
    path = [(2.0, 0.0), (3.0, 0.0), (7.0, 0.2)]
    command = PurePursuit().command(Pose2D(4.0, 0.0, 0.0), path)
    assert command.target_velocity_mps > 0.0
    assert command.brake == 0.0


def test_local_plan_to_ackermann_folds_brake_into_speed():
    from aris_planning.cmd_drive import local_plan_to_ackermann
    from aris_planning.pure_pursuit import LocalPlanCommand

    cmd = LocalPlanCommand(
        target_steering_rad=0.1, target_velocity_mps=2.0, brake=0.5, dry_run=True
    )
    fields = local_plan_to_ackermann(cmd)
    assert fields.steering_angle_rad == 0.1
    assert fields.speed_mps == 1.0  # 2.0 * (1 - 0.5)
    assert fields.acceleration_mps2 == -0.5  # normalized brake intent


def test_local_plan_to_ackermann_full_brake_zero_speed():
    from aris_planning.cmd_drive import ackermann_to_brake, local_plan_to_ackermann
    from aris_planning.pure_pursuit import LocalPlanCommand

    cmd = LocalPlanCommand(
        target_steering_rad=0.0, target_velocity_mps=3.0, brake=1.0, dry_run=True
    )
    fields = local_plan_to_ackermann(cmd)
    assert fields.speed_mps == 0.0
    assert ackermann_to_brake(fields.acceleration_mps2) == 1.0


def test_ackermann_to_brake_is_clamped():
    from aris_planning.cmd_drive import ackermann_to_brake

    assert ackermann_to_brake(0.5) == 0.0  # positive accel = no brake
    assert ackermann_to_brake(-2.0) == 1.0  # clamped to 1.0
