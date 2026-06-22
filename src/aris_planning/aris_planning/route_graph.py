"""ROS-free V4 route-graph global planning with semantic costs."""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass
from typing import Iterable

from aris_mapping.semantic_map import RouteEdge, RouteNode, SemanticHDMap


@dataclass(frozen=True)
class RouteGraphPlan:
    node_ids: list[str]
    points: list[tuple[float, float]]
    cost: float


def nearest_route_node(nodes: dict[str, RouteNode], x: float, y: float) -> str:
    if not nodes:
        raise ValueError("route graph has no nodes")
    return min(
        nodes,
        key=lambda node_id: math.hypot(nodes[node_id].x - x, nodes[node_id].y - y),
    )


def plan_route_graph(
    hd_map: SemanticHDMap,
    start_node: str,
    goal_node: str,
    semantic_weight: float = 8.0,
) -> RouteGraphPlan:
    if start_node not in hd_map.route_nodes or goal_node not in hd_map.route_nodes:
        raise ValueError("start and goal nodes must exist")

    frontier: list[tuple[float, str]] = [(0.0, start_node)]
    came_from: dict[str, str | None] = {start_node: None}
    cost_so_far: dict[str, float] = {start_node: 0.0}

    while frontier:
        _, current = heapq.heappop(frontier)
        if current == goal_node:
            break
        for edge in hd_map.traversable_edges(current):
            step_cost = semantic_edge_cost(hd_map, edge, semantic_weight)
            new_cost = cost_so_far[current] + step_cost
            if edge.to_node not in cost_so_far or new_cost < cost_so_far[edge.to_node]:
                cost_so_far[edge.to_node] = new_cost
                priority = new_cost + _node_distance(hd_map, edge.to_node, goal_node)
                heapq.heappush(frontier, (priority, edge.to_node))
                came_from[edge.to_node] = current

    if goal_node not in came_from:
        raise ValueError("no route graph path found")

    node_ids = [goal_node]
    while node_ids[-1] != start_node:
        previous = came_from[node_ids[-1]]
        if previous is None:
            break
        node_ids.append(previous)
    node_ids.reverse()
    points = [(hd_map.route_nodes[node_id].x, hd_map.route_nodes[node_id].y) for node_id in node_ids]
    return RouteGraphPlan(node_ids=node_ids, points=points, cost=cost_so_far[goal_node])


def semantic_edge_cost(
    hd_map: SemanticHDMap,
    edge: RouteEdge,
    semantic_weight: float = 8.0,
    samples: int = 8,
) -> float:
    if edge.blocked:
        return math.inf
    start = hd_map.route_nodes[edge.from_node]
    goal = hd_map.route_nodes[edge.to_node]
    semantic_penalty = 0.0
    for x, y in _sample_segment(start.x, start.y, goal.x, goal.y, samples):
        state = hd_map.cells.get(hd_map.cell_for_point(x, y))
        if state is not None:
            semantic_penalty = max(semantic_penalty, state.traversability * semantic_weight)
    return edge.cost + semantic_penalty


def build_bidirectional_edges(edges: Iterable[RouteEdge]) -> list[RouteEdge]:
    graph_edges: list[RouteEdge] = []
    for edge in edges:
        graph_edges.append(edge)
        graph_edges.append(
            RouteEdge(
                from_node=edge.to_node,
                to_node=edge.from_node,
                cost=edge.cost,
                blocked=edge.blocked,
            )
        )
    return graph_edges


def densify_path(points: list[tuple[float, float]], spacing_m: float = 0.3) -> list[tuple[float, float]]:
    if not points:
        return []
    if spacing_m <= 0.0:
        raise ValueError("spacing_m must be positive")
    dense = [points[0]]
    for start, goal in zip(points, points[1:]):
        dx = goal[0] - start[0]
        dy = goal[1] - start[1]
        distance = math.hypot(dx, dy)
        steps = max(1, int(math.ceil(distance / spacing_m)))
        for index in range(1, steps + 1):
            t = index / steps
            dense.append((start[0] + dx * t, start[1] + dy * t))
    return dense


def _sample_segment(
    ax: float, ay: float, bx: float, by: float, samples: int
) -> Iterable[tuple[float, float]]:
    count = max(samples, 1)
    for index in range(count + 1):
        t = index / count
        yield (ax + (bx - ax) * t, ay + (by - ay) * t)


def _node_distance(hd_map: SemanticHDMap, a: str, b: str) -> float:
    node_a = hd_map.route_nodes[a]
    node_b = hd_map.route_nodes[b]
    return math.hypot(node_a.x - node_b.x, node_a.y - node_b.y)
