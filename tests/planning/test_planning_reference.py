from aris_planning.astar import GridPlanner


def test_reference_route_graph_path():
    planner = GridPlanner(3, 3, blocked={(1, 1)})
    path = planner.plan((0, 0), (2, 2))
    assert path[0] == (0, 0)
    assert path[-1] == (2, 2)
    assert (1, 1) not in path
