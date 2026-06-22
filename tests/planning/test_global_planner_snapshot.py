import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "aris_mapping"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "aris_planning"))

from aris_mapping.semantic_map import RouteEdge, RouteNode, SemanticHDMap
from aris_planning.route_graph import load_semantic_map_graph


def test_semantic_map_file_graph_loads_snapshot_route_graph(tmp_path):
    hd_map = SemanticHDMap(resolution_m=0.5)
    hd_map.add_route_node(RouteNode("start", 0.0, 0.0))
    hd_map.add_route_node(RouteNode("goal", 1.0, 0.0))
    hd_map.add_route_edge(RouteEdge("start", "goal", 1.0))
    snapshot = tmp_path / "semantic_map.json"
    snapshot.write_text(json.dumps(hd_map.to_snapshot()), encoding="utf-8")

    loaded = load_semantic_map_graph(snapshot)

    assert loaded.route_nodes["goal"].x == 1.0
    assert loaded.route_edges[0].from_node == "start"


def test_semantic_map_file_graph_rejects_snapshot_without_route_edges(tmp_path):
    hd_map = SemanticHDMap(resolution_m=0.5)
    hd_map.add_route_node(RouteNode("start", 0.0, 0.0))
    snapshot = tmp_path / "semantic_map.json"
    snapshot.write_text(json.dumps(hd_map.to_snapshot()), encoding="utf-8")

    with pytest.raises(ValueError, match="route edges"):
        load_semantic_map_graph(snapshot)
