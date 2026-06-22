import pytest

from aris_mapping.semantic_map import (
    RouteEdge,
    RouteNode,
    SemanticHDMap,
    SemanticObservation,
    load_route_csv_as_graph,
    traversability_for_label,
)


def test_semantic_observation_updates_layers():
    hd_map = SemanticHDMap(resolution_m=0.5)

    hd_map.mark_occupied(1.0, 1.0, 0.8)
    decision = hd_map.apply_semantic_observation(
        SemanticObservation(x=1.1, y=1.2, label="road", confidence=0.9)
    )
    cell = hd_map.cell_for_point(1.1, 1.2)
    state = hd_map.cells[cell]

    assert decision.applied
    assert not decision.change_detected
    assert state.occupancy == pytest.approx(0.8)
    assert state.top_label == "road"
    assert state.traversability < 0.2
    assert cell in hd_map.metric_cells


def test_low_confidence_observation_requires_review_without_applying():
    hd_map = SemanticHDMap(change_threshold=0.65)

    decision = hd_map.apply_semantic_observation(
        SemanticObservation(x=0.0, y=0.0, label="debris", confidence=0.4)
    )

    assert not decision.applied
    assert decision.review_required
    assert hd_map.cells[decision.cell].labels == {}


def test_repeat_pass_change_detection_marks_review():
    hd_map = SemanticHDMap(change_threshold=0.6, confirmation_threshold=0.75)
    first = hd_map.apply_semantic_observation(
        SemanticObservation(x=2.0, y=0.0, label="road", confidence=0.9)
    )
    second = hd_map.apply_semantic_observation(
        SemanticObservation(x=2.1, y=0.1, label="debris", confidence=0.85)
    )

    assert first.applied
    assert second.applied
    assert second.change_detected
    assert second.review_required
    assert second.reason == "change_detected"


def test_route_graph_tracks_traversable_edges():
    hd_map = SemanticHDMap()
    hd_map.add_route_node(RouteNode("start", 0.0, 0.0))
    hd_map.add_route_node(RouteNode("goal", 1.0, 0.0))
    hd_map.add_route_node(RouteNode("blocked", 0.5, 1.0))
    hd_map.add_route_edge(RouteEdge("start", "goal", cost=1.0))
    hd_map.add_route_edge(RouteEdge("start", "blocked", cost=2.0, blocked=True))

    edges = list(hd_map.traversable_edges("start"))

    assert [edge.to_node for edge in edges] == ["goal"]
    with pytest.raises(ValueError, match="endpoints"):
        hd_map.add_route_edge(RouteEdge("missing", "goal", cost=1.0))


def test_traversability_cost_reflects_semantic_risk():
    assert traversability_for_label("road", 1.0) < traversability_for_label("mud", 1.0)
    assert traversability_for_label("mud", 1.0) < traversability_for_label("debris", 1.0)


def test_semantic_map_snapshot_round_trips(tmp_path):
    hd_map = SemanticHDMap(resolution_m=0.25, change_threshold=0.6, confirmation_threshold=0.8)
    hd_map.mark_occupied(1.0, 2.0, 0.7)
    hd_map.apply_semantic_observation(
        SemanticObservation(x=1.0, y=2.0, label="road", confidence=0.95)
    )
    hd_map.apply_semantic_observation(
        SemanticObservation(x=1.0, y=2.0, label="debris", confidence=0.9)
    )
    hd_map.add_route_node(RouteNode("a", 0.0, 0.0))
    hd_map.add_route_node(RouteNode("b", 1.0, 0.0))
    hd_map.add_route_edge(RouteEdge("a", "b", cost=1.5, blocked=True))

    snapshot_file = tmp_path / "semantic_map.json"
    hd_map.save_snapshot(snapshot_file, map_id="unit-test-map")

    loaded = SemanticHDMap.load_snapshot(snapshot_file)
    cell = loaded.cell_for_point(1.0, 2.0)

    assert loaded.resolution_m == pytest.approx(0.25)
    assert loaded.cells[cell].top_label == "road"
    assert loaded.cells[cell].labels["debris"] == pytest.approx(0.9)
    assert loaded.route_edges[0].blocked
    assert loaded.review_queue[0].reason == "change_detected"
    assert loaded.to_snapshot(map_id="unit-test-map") == hd_map.to_snapshot(map_id="unit-test-map")


def test_route_csv_loads_into_snapshot_route_graph(tmp_path):
    route_file = tmp_path / "route.csv"
    route_file.write_text(
        "x,y,yaw,v_target\n"
        "0.0,0.0,0.0,1.0\n"
        "1.0,0.0,0.0,1.0\n"
        "1.0,1.0,1.57,1.0\n",
        encoding="utf-8",
    )
    hd_map = SemanticHDMap()

    nodes, edges = load_route_csv_as_graph(hd_map, route_file)

    assert nodes == 3
    assert edges == 2
    assert list(hd_map.traversable_edges("route_0000"))[0].to_node == "route_0001"
    snapshot = hd_map.to_snapshot(map_id="route-test")
    assert len(snapshot["route_nodes"]) == 3
    assert len(snapshot["route_edges"]) == 2
