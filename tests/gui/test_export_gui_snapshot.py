import csv
import json
import subprocess
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "export_gui_snapshot.py"
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from serve_gui_snapshot import SnapshotHandler


def test_export_gui_snapshot_from_route_csv(tmp_path):
    route_path = tmp_path / "route.csv"
    with route_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["x", "y", "yaw", "v_target"])
        writer.writeheader()
        writer.writerows(
            [
                {"x": 0.0, "y": 0.0, "yaw": 0.0, "v_target": 0.5},
                {"x": 1.0, "y": 0.0, "yaw": 0.0, "v_target": 0.5},
                {"x": 2.0, "y": 0.2, "yaw": 0.0, "v_target": 0.5},
                {"x": 3.0, "y": 0.4, "yaw": 0.0, "v_target": 0.5},
            ]
        )
    out_path = tmp_path / "gui_snapshot.json"

    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--route",
            str(route_path),
            "--out",
            str(out_path),
            "--map-id",
            "route-gui",
        ],
        check=True,
    )

    snapshot = json.loads(out_path.read_text(encoding="utf-8"))
    assert snapshot["schema_version"] == 1
    assert snapshot["map_id"] == "route-gui"
    assert snapshot["frame"] == "map"
    assert snapshot["goal"] == {"x": 3.0, "y": 0.4}
    assert len(snapshot["global_path"]) == 4
    assert len(snapshot["local_path"]) == 4
    assert snapshot["semantic_cells"]
    assert snapshot["lidar_returns"]
    assert set(snapshot["bounds"]) == {"min_x", "max_x", "min_y", "max_y"}


def test_export_gui_snapshot_from_semantic_map_snapshot(tmp_path):
    semantic_map_path = tmp_path / "semantic_map.json"
    semantic_map_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "map_id": "semantic-gui",
                "resolution_m": 0.5,
                "route_nodes": [
                    {"node_id": "node_0", "x": 0.0, "y": 0.0},
                    {"node_id": "node_1", "x": 1.0, "y": 0.0},
                    {"node_id": "node_2", "x": 2.0, "y": 0.0},
                ],
                "route_edges": [
                    {"from": "node_0", "to": "node_1"},
                    {"from": "node_1", "to": "node_2"},
                ],
                "cells": [
                    {
                        "cell": [4, 2],
                        "labels": {"debris": 0.91, "road": 0.3},
                        "traversability": 0.86,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    out_path = tmp_path / "gui_snapshot.json"

    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--semantic-map-snapshot",
            str(semantic_map_path),
            "--out",
            str(out_path),
        ],
        check=True,
    )

    snapshot = json.loads(out_path.read_text(encoding="utf-8"))
    assert snapshot["map_id"] == "semantic-gui"
    assert snapshot["global_path"] == [
        {"x": 0.0, "y": 0.0},
        {"x": 1.0, "y": 0.0},
        {"x": 2.0, "y": 0.0},
    ]
    assert snapshot["semantic_cells"] == [
        {
            "x": 2.0,
            "y": 1.0,
            "label": "debris",
            "confidence": 0.91,
            "traversability": 0.86,
        }
    ]
    assert snapshot["local_path"][2]["y"] < snapshot["global_path"][2]["y"]


def test_serve_gui_snapshot_returns_compact_json_with_cors(tmp_path):
    snapshot_path = tmp_path / "gui_snapshot.json"
    snapshot_path.write_text(
        json.dumps({"schema_version": 1, "map_id": "served-map", "global_path": []}),
        encoding="utf-8",
    )

    TestHandler = type("TestHandler", (SnapshotHandler,), {"snapshot_path": snapshot_path})
    server = ThreadingHTTPServer(("127.0.0.1", 0), TestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urlopen(f"http://127.0.0.1:{server.server_port}/snapshot", timeout=2) as response:
            body = response.read().decode("utf-8")
            assert response.status == 200
            assert response.headers["Content-Type"] == "application/json; charset=utf-8"
            assert response.headers["Access-Control-Allow-Origin"] == "*"
            assert response.headers["Cache-Control"] == "no-store"
        assert json.loads(body) == {"schema_version": 1, "map_id": "served-map", "global_path": []}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
