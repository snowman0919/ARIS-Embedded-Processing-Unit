from __future__ import annotations

import heapq
from dataclasses import dataclass
from math import hypot
from typing import Iterable

GridPoint = tuple[int, int]


@dataclass(frozen=True)
class CellCost:
    distance: float = 1.0
    risk: float = 0.0
    narrowness: float = 0.0
    curvature: float = 0.0
    semantic_penalty: float = 0.0

    @property
    def total(self) -> float:
        return self.distance + self.risk + self.narrowness + self.curvature + self.semantic_penalty


class GridPlanner:
    def __init__(
        self,
        width: int,
        height: int,
        blocked: Iterable[GridPoint] | None = None,
        costs: dict[GridPoint, CellCost] | None = None,
    ) -> None:
        self.width = width
        self.height = height
        self.blocked = set(blocked or set())
        self.costs = costs or {}

    def in_bounds(self, point: GridPoint) -> bool:
        x, y = point
        return 0 <= x < self.width and 0 <= y < self.height

    def passable(self, point: GridPoint) -> bool:
        return point not in self.blocked

    def neighbors(self, point: GridPoint) -> list[GridPoint]:
        x, y = point
        candidates = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
        return [p for p in candidates if self.in_bounds(p) and self.passable(p)]

    def cost(self, point: GridPoint) -> float:
        return self.costs.get(point, CellCost()).total

    @staticmethod
    def heuristic(a: GridPoint, b: GridPoint) -> float:
        return hypot(a[0] - b[0], a[1] - b[1])

    def plan(self, start: GridPoint, goal: GridPoint) -> list[GridPoint]:
        if not self.in_bounds(start) or not self.in_bounds(goal):
            raise ValueError("start and goal must be inside grid")
        if not self.passable(start) or not self.passable(goal):
            raise ValueError("start and goal must be passable")

        frontier: list[tuple[float, GridPoint]] = [(0.0, start)]
        came_from: dict[GridPoint, GridPoint | None] = {start: None}
        cost_so_far: dict[GridPoint, float] = {start: 0.0}

        while frontier:
            _, current = heapq.heappop(frontier)
            if current == goal:
                break
            for nxt in self.neighbors(current):
                new_cost = cost_so_far[current] + self.cost(nxt)
                if nxt not in cost_so_far or new_cost < cost_so_far[nxt]:
                    cost_so_far[nxt] = new_cost
                    priority = new_cost + self.heuristic(nxt, goal)
                    heapq.heappush(frontier, (priority, nxt))
                    came_from[nxt] = current

        if goal not in came_from:
            raise ValueError("no path found")

        path = [goal]
        while path[-1] != start:
            previous = came_from[path[-1]]
            if previous is None:
                break
            path.append(previous)
        path.reverse()
        return path
