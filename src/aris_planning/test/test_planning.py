import pytest

from aris_planning.astar import CellCost, GridPlanner
from aris_planning.dynamic_obstacle_advisory import (
    apply_dynamic_obstacle_advisory,
    parse_dynamic_obstacle_advisory,
)
from aris_planning.pure_pursuit import Pose2D, PurePursuit
from aris_planning.route import (
    RouteWaypoint,
    load_route_csv,
    path_xy,
    select_lookahead_waypoint,
    write_route_csv,
)
from aris_planning.route_graph import (
    build_bidirectional_edges,
    densify_path,
    nearest_route_node,
    plan_route_graph,
)
from aris_mapping.semantic_map import RouteEdge, RouteNode, SemanticHDMap, SemanticObservation


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


def test_dynamic_obstacle_stop_advisory_overrides_local_plan():
    from aris_planning.pure_pursuit import LocalPlanCommand

    advisory = parse_dynamic_obstacle_advisory(
        '{"action":"stop","closest_distance_m":0.9,"point_count":5}'
    )
    command = apply_dynamic_obstacle_advisory(
        LocalPlanCommand(0.2, 1.4, 0.0, dry_run=True), advisory
    )

    assert command.target_steering_rad == 0.2
    assert command.target_velocity_mps == 0.0
    assert command.brake == 1.0


def test_dynamic_obstacle_slow_advisory_caps_local_plan():
    from aris_planning.pure_pursuit import LocalPlanCommand

    advisory = parse_dynamic_obstacle_advisory(
        '{"action":"slow","closest_distance_m":2.5,"point_count":5}'
    )
    command = apply_dynamic_obstacle_advisory(
        LocalPlanCommand(0.2, 1.4, 0.0, dry_run=True),
        advisory,
        slow_speed_mps=0.35,
    )

    assert command.target_velocity_mps == 0.35
    assert command.brake == 0.2


def test_ackermann_to_brake_is_clamped():
    from aris_planning.cmd_drive import ackermann_to_brake

    assert ackermann_to_brake(0.5) == 0.0  # positive accel = no brake
    assert ackermann_to_brake(-2.0) == 1.0  # clamped to 1.0


def test_route_csv_round_trip(tmp_path):
    route_file = tmp_path / "route.csv"
    route = [
        RouteWaypoint(x=0.0, y=0.0, yaw=0.0, v_target=1.0),
        RouteWaypoint(x=0.2, y=0.1, yaw=0.05, v_target=1.2),
    ]

    write_route_csv(route_file, route)

    loaded = load_route_csv(route_file)
    assert loaded == route
    assert path_xy(loaded) == [(0.0, 0.0), (0.2, 0.1)]


def test_route_csv_requires_v1_columns(tmp_path):
    route_file = tmp_path / "bad_route.csv"
    route_file.write_text("x,y,yaw\n0.0,0.0,0.0\n")

    with pytest.raises(ValueError, match="v_target"):
        load_route_csv(route_file)


def test_route_selects_first_forward_lookahead_waypoint():
    route = [
        RouteWaypoint(x=-1.0, y=0.0, yaw=0.0, v_target=1.0),
        RouteWaypoint(x=0.5, y=0.0, yaw=0.0, v_target=1.0),
        RouteWaypoint(x=2.0, y=0.2, yaw=0.0, v_target=1.0),
        RouteWaypoint(x=3.0, y=0.0, yaw=0.0, v_target=1.0),
    ]

    waypoint = select_lookahead_waypoint(
        Pose2D(x=0.0, y=0.0, yaw=0.0), route, lookahead_m=1.5
    )

    assert waypoint == route[2]


def test_route_selects_last_forward_when_no_point_reaches_lookahead():
    route = [
        RouteWaypoint(x=0.2, y=0.0, yaw=0.0, v_target=1.0),
        RouteWaypoint(x=0.8, y=0.1, yaw=0.0, v_target=1.0),
    ]

    waypoint = select_lookahead_waypoint(
        Pose2D(x=0.0, y=0.0, yaw=0.0), route, lookahead_m=2.0
    )

    assert waypoint == route[-1]


def test_route_graph_global_planner_avoids_semantic_penalty():
    hd_map = SemanticHDMap(resolution_m=0.5)
    for node in [
        RouteNode("start", 0.0, 0.0),
        RouteNode("mid", 1.0, 0.0),
        RouteNode("goal", 2.0, 0.0),
        RouteNode("detour_a", 1.0, 1.0),
        RouteNode("detour_b", 2.0, 1.0),
    ]:
        hd_map.add_route_node(node)
    for edge in build_bidirectional_edges(
        [
            RouteEdge("start", "mid", 1.0),
            RouteEdge("mid", "goal", 1.0),
            RouteEdge("start", "detour_a", 1.5),
            RouteEdge("detour_a", "detour_b", 1.0),
            RouteEdge("detour_b", "goal", 1.5),
        ]
    ):
        hd_map.add_route_edge(edge)
    hd_map.apply_semantic_observation(
        SemanticObservation(x=1.0, y=0.0, label="debris", confidence=0.95)
    )

    plan = plan_route_graph(hd_map, "start", "goal", semantic_weight=10.0)

    assert plan.node_ids == ["start", "detour_a", "detour_b", "goal"]
    assert "mid" not in plan.node_ids


def test_nearest_route_node_selects_closest_node():
    nodes = {
        "a": RouteNode("a", 0.0, 0.0),
        "b": RouteNode("b", 5.0, 0.0),
    }

    assert nearest_route_node(nodes, 4.2, 0.2) == "b"


def test_densify_path_interpolates_long_segments():
    dense = densify_path([(0.0, 0.0), (1.0, 0.0)], spacing_m=0.25)

    assert dense[0] == (0.0, 0.0)
    assert dense[-1] == (1.0, 0.0)
    assert len(dense) == 5
