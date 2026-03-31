"""Movement and BFS pathfinding."""

from __future__ import annotations

from collections import deque

from server.engine.constants import MOVE_BASE_COST
from server.engine.models import GameMap


def movement_cost(steps: int) -> float:
    """Energy cost for moving a given number of steps: 10 * 2^steps."""
    return MOVE_BASE_COST * (2**steps)


def reachable_cells(
    game_map: GameMap,
    start_x: int,
    start_y: int,
    max_steps: int,
) -> dict[tuple[int, int], int]:
    """BFS from start position. Returns {(x, y): step_count} for all reachable
    cells within max_steps, excluding the start cell itself."""
    result: dict[tuple[int, int], int] = {}
    visited = {(start_x, start_y)}
    queue: deque[tuple[int, int, int]] = deque([(start_x, start_y, 0)])

    while queue:
        x, y, steps = queue.popleft()
        if steps >= max_steps:
            continue
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nx, ny = x + dx, y + dy
            if (nx, ny) not in visited and game_map.is_passable(nx, ny):
                visited.add((nx, ny))
                new_steps = steps + 1
                result[(nx, ny)] = new_steps
                queue.append((nx, ny, new_steps))

    return result


def find_path(
    game_map: GameMap,
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
) -> list[tuple[int, int]] | None:
    """BFS shortest path from start to end, avoiding water.
    Returns list of (x, y) positions from start (exclusive) to end (inclusive),
    or None if unreachable."""
    if start_x == end_x and start_y == end_y:
        return []

    if not game_map.is_passable(end_x, end_y):
        return None

    visited = {(start_x, start_y)}
    parent: dict[tuple[int, int], tuple[int, int]] = {}
    queue: deque[tuple[int, int]] = deque([(start_x, start_y)])

    while queue:
        x, y = queue.popleft()
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nx, ny = x + dx, y + dy
            if (nx, ny) not in visited and game_map.is_passable(nx, ny):
                visited.add((nx, ny))
                parent[(nx, ny)] = (x, y)
                if nx == end_x and ny == end_y:
                    # Reconstruct path
                    path = []
                    cx, cy = end_x, end_y
                    while (cx, cy) != (start_x, start_y):
                        path.append((cx, cy))
                        cx, cy = parent[(cx, cy)]
                    path.reverse()
                    return path
                queue.append((nx, ny))

    return None
