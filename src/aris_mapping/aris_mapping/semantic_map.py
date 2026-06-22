"""ROS-free five-layer semantic HD map scaffold.

The V3 production milestone needs camera segmentation and real sensor streams.
This module intentionally owns only deterministic map state/update policy so it
can be tested before those external assets exist.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


Cell = tuple[int, int]


@dataclass(frozen=True)
class SemanticObservation:
    x: float
    y: float
    label: str
    confidence: float
    source: str = "simulation"


@dataclass(frozen=True)
class MapUpdateDecision:
    cell: Cell
    label: str
    applied: bool
    change_detected: bool
    review_required: bool
    reason: str


@dataclass(frozen=True)
class RouteNode:
    node_id: str
    x: float
    y: float


@dataclass(frozen=True)
class RouteEdge:
    from_node: str
    to_node: str
    cost: float
    blocked: bool = False


@dataclass
class SemanticCellState:
    occupancy: float = 0.5
    labels: dict[str, float] = field(default_factory=dict)
    traversability: float = 0.5
    observations: int = 0

    @property
    def top_label(self) -> str | None:
        if not self.labels:
            return None
        return max(self.labels.items(), key=lambda item: item[1])[0]

    @property
    def top_confidence(self) -> float:
        if not self.labels:
            return 0.0
        return max(self.labels.values())


class SemanticHDMap:
    """Five V3 layers: metric, occupancy, semantic, traversability, route graph."""

    def __init__(
        self,
        resolution_m: float = 0.5,
        change_threshold: float = 0.65,
        confirmation_threshold: float = 0.75,
    ) -> None:
        if resolution_m <= 0.0:
            raise ValueError("resolution_m must be positive")
        self.resolution_m = resolution_m
        self.change_threshold = change_threshold
        self.confirmation_threshold = confirmation_threshold
        self.metric_cells: set[Cell] = set()
        self.cells: dict[Cell, SemanticCellState] = {}
        self.route_nodes: dict[str, RouteNode] = {}
        self.route_edges: list[RouteEdge] = []
        self.review_queue: list[MapUpdateDecision] = []

    def cell_for_point(self, x: float, y: float) -> Cell:
        return (math.floor(x / self.resolution_m), math.floor(y / self.resolution_m))

    def mark_occupied(self, x: float, y: float, probability: float) -> None:
        cell = self.cell_for_point(x, y)
        state = self._state(cell)
        state.occupancy = _clamp01(probability)
        self.metric_cells.add(cell)

    def apply_semantic_observation(self, observation: SemanticObservation) -> MapUpdateDecision:
        if not 0.0 <= observation.confidence <= 1.0:
            raise ValueError("observation confidence must be in [0, 1]")
        cell = self.cell_for_point(observation.x, observation.y)
        state = self._state(cell)
        prior_label = state.top_label
        prior_confidence = state.top_confidence
        confidence = observation.confidence

        if confidence < self.change_threshold:
            decision = MapUpdateDecision(
                cell=cell,
                label=observation.label,
                applied=False,
                change_detected=False,
                review_required=True,
                reason="low_confidence",
            )
            self.review_queue.append(decision)
            return decision

        change_detected = (
            prior_label is not None
            and prior_label != observation.label
            and prior_confidence >= self.confirmation_threshold
        )
        state.labels[observation.label] = max(state.labels.get(observation.label, 0.0), confidence)
        state.traversability = traversability_for_label(observation.label, confidence)
        state.observations += 1
        self.metric_cells.add(cell)

        decision = MapUpdateDecision(
            cell=cell,
            label=observation.label,
            applied=True,
            change_detected=change_detected,
            review_required=change_detected or confidence < self.confirmation_threshold,
            reason="change_detected" if change_detected else "applied",
        )
        if decision.review_required:
            self.review_queue.append(decision)
        return decision

    def add_route_node(self, node: RouteNode) -> None:
        self.route_nodes[node.node_id] = node

    def add_route_edge(self, edge: RouteEdge) -> None:
        if edge.from_node not in self.route_nodes or edge.to_node not in self.route_nodes:
            raise ValueError("route edge endpoints must exist before adding an edge")
        self.route_edges.append(edge)

    def traversable_edges(self, from_node: str) -> Iterable[RouteEdge]:
        return (
            edge
            for edge in self.route_edges
            if edge.from_node == from_node and not edge.blocked
        )

    def _state(self, cell: Cell) -> SemanticCellState:
        if cell not in self.cells:
            self.cells[cell] = SemanticCellState()
        return self.cells[cell]

    def to_snapshot(self, *, map_id: str = "aris-semantic-map") -> dict:
        """Return a deterministic JSON-serializable map snapshot."""
        return {
            "schema_version": 1,
            "map_id": map_id,
            "resolution_m": self.resolution_m,
            "change_threshold": self.change_threshold,
            "confirmation_threshold": self.confirmation_threshold,
            "metric_cells": [list(cell) for cell in sorted(self.metric_cells)],
            "cells": [
                {
                    "cell": list(cell),
                    "occupancy": state.occupancy,
                    "labels": dict(sorted(state.labels.items())),
                    "traversability": state.traversability,
                    "observations": state.observations,
                }
                for cell, state in sorted(self.cells.items())
            ],
            "route_nodes": [
                {
                    "node_id": node.node_id,
                    "x": node.x,
                    "y": node.y,
                }
                for node in sorted(self.route_nodes.values(), key=lambda item: item.node_id)
            ],
            "route_edges": [
                {
                    "from_node": edge.from_node,
                    "to_node": edge.to_node,
                    "cost": edge.cost,
                    "blocked": edge.blocked,
                }
                for edge in self.route_edges
            ],
            "review_queue": [
                {
                    "cell": list(decision.cell),
                    "label": decision.label,
                    "applied": decision.applied,
                    "change_detected": decision.change_detected,
                    "review_required": decision.review_required,
                    "reason": decision.reason,
                }
                for decision in self.review_queue
            ],
        }

    def save_snapshot(self, path: str | Path, *, map_id: str = "aris-semantic-map") -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(self.to_snapshot(map_id=map_id), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    @classmethod
    def from_snapshot(cls, snapshot: dict) -> "SemanticHDMap":
        if snapshot.get("schema_version") != 1:
            raise ValueError("unsupported semantic map snapshot schema_version")
        hd_map = cls(
            resolution_m=float(snapshot["resolution_m"]),
            change_threshold=float(snapshot["change_threshold"]),
            confirmation_threshold=float(snapshot["confirmation_threshold"]),
        )
        hd_map.metric_cells = {_cell_from_json(cell) for cell in snapshot.get("metric_cells", [])}
        for item in snapshot.get("cells", []):
            cell = _cell_from_json(item["cell"])
            hd_map.cells[cell] = SemanticCellState(
                occupancy=_clamp01(float(item["occupancy"])),
                labels={str(k): _clamp01(float(v)) for k, v in item.get("labels", {}).items()},
                traversability=_clamp01(float(item["traversability"])),
                observations=int(item.get("observations", 0)),
            )
        for item in snapshot.get("route_nodes", []):
            node = RouteNode(
                node_id=str(item["node_id"]),
                x=float(item["x"]),
                y=float(item["y"]),
            )
            hd_map.route_nodes[node.node_id] = node
        for item in snapshot.get("route_edges", []):
            hd_map.route_edges.append(
                RouteEdge(
                    from_node=str(item["from_node"]),
                    to_node=str(item["to_node"]),
                    cost=float(item["cost"]),
                    blocked=bool(item.get("blocked", False)),
                )
            )
        for item in snapshot.get("review_queue", []):
            hd_map.review_queue.append(
                MapUpdateDecision(
                    cell=_cell_from_json(item["cell"]),
                    label=str(item["label"]),
                    applied=bool(item["applied"]),
                    change_detected=bool(item["change_detected"]),
                    review_required=bool(item["review_required"]),
                    reason=str(item["reason"]),
                )
            )
        return hd_map

    @classmethod
    def load_snapshot(cls, path: str | Path) -> "SemanticHDMap":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("semantic map snapshot must be a JSON object")
        return cls.from_snapshot(data)


def traversability_for_label(label: str, confidence: float) -> float:
    normalized = label.lower()
    if normalized in {"road", "lane", "free_space"}:
        base = 0.1
    elif normalized in {"curb", "shoulder"}:
        base = 0.4
    elif normalized in {"mud", "water", "soft_ground"}:
        base = 0.7
    elif normalized in {"obstacle", "debris", "blocked", "vehicle", "person"}:
        base = 1.0
    else:
        base = 0.5
    return _clamp01(0.5 * (1.0 - confidence) + base * confidence)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _cell_from_json(value: object) -> Cell:
    if not isinstance(value, list | tuple) or len(value) != 2:
        raise ValueError("cell must be a two-item list")
    return (int(value[0]), int(value[1]))
