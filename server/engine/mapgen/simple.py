"""Simple map generator using cellular automata. No external dependencies."""

from __future__ import annotations

import random
from collections import deque

from server.engine.models import Cell, CellType, GameMap


class SimpleMapGenerator:
    """Generates maps using cellular automata smoothing.

    1. Random fill (~40% water)
    2. Cellular automata smoothing (4 iterations)
    3. Flood-fill to ensure connectivity (isolated land -> water)
    4. Assign vegetation and carrion to land cells
    """

    def __init__(
        self,
        water_ratio: float = 0.40,
        veg_ratio: float = 0.25,
        carrion_ratio: float = 0.05,
        smoothing_iterations: int = 4,
    ):
        self.water_ratio = water_ratio
        self.veg_ratio = veg_ratio
        self.carrion_ratio = carrion_ratio
        self.smoothing_iterations = smoothing_iterations

    def generate(self, width: int, height: int, rng: random.Random) -> GameMap:
        # Step 1: Random fill
        grid = [
            [rng.random() < self.water_ratio for _ in range(width)]
            for _ in range(height)
        ]

        # Step 2: Cellular automata smoothing
        for _ in range(self.smoothing_iterations):
            grid = self._smooth(grid, width, height)

        # Step 3: Flood-fill from center to ensure connectivity
        grid = self._enforce_connectivity(grid, width, height)

        # Step 4: Assign cell types
        land_coords = [
            (x, y) for y in range(height) for x in range(width) if not grid[y][x]
        ]
        rng.shuffle(land_coords)

        num_veg = int(len(land_coords) * self.veg_ratio)
        num_carrion = int(len(land_coords) * self.carrion_ratio)

        veg_set = set(land_coords[:num_veg])
        carrion_set = set(land_coords[num_veg : num_veg + num_carrion])

        cells: list[list[Cell]] = []
        for y in range(height):
            row: list[Cell] = []
            for x in range(width):
                if grid[y][x]:
                    row.append(Cell(x=x, y=y, cell_type=CellType.WATER))
                elif (x, y) in veg_set:
                    max_e = rng.uniform(500, 2000)
                    row.append(
                        Cell(
                            x=x,
                            y=y,
                            cell_type=CellType.VEGETATION,
                            energy=max_e,
                            max_energy=max_e,
                        )
                    )
                elif (x, y) in carrion_set:
                    max_e = rng.uniform(300, 1500)
                    row.append(
                        Cell(
                            x=x,
                            y=y,
                            cell_type=CellType.CARRION,
                            energy=max_e,
                            max_energy=max_e,
                        )
                    )
                else:
                    row.append(Cell(x=x, y=y, cell_type=CellType.PLAIN))
            cells.append(row)

        return GameMap(width=width, height=height, cells=cells)

    def _smooth(
        self, grid: list[list[bool]], width: int, height: int
    ) -> list[list[bool]]:
        """Cellular automata rule: cell becomes water if 5+ of its 9 neighbors
        (including itself) are water. Border cells always become water."""
        new_grid = [[False] * width for _ in range(height)]
        for y in range(height):
            for x in range(width):
                if x == 0 or x == width - 1 or y == 0 or y == height - 1:
                    new_grid[y][x] = True  # borders are water
                    continue
                water_count = sum(
                    1
                    for dy in (-1, 0, 1)
                    for dx in (-1, 0, 1)
                    if 0 <= y + dy < height
                    and 0 <= x + dx < width
                    and grid[y + dy][x + dx]
                )
                new_grid[y][x] = water_count >= 5
        return new_grid

    def _enforce_connectivity(
        self, grid: list[list[bool]], width: int, height: int
    ) -> list[list[bool]]:
        """BFS from center land cell. Any land not reachable becomes water."""
        # Find the first land cell near the center
        cx, cy = width // 2, height // 2
        start = None
        for radius in range(max(width, height)):
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < width and 0 <= ny < height and not grid[ny][nx]:
                        start = (nx, ny)
                        break
                if start:
                    break
            if start:
                break

        if start is None:
            return grid  # all water, nothing to connect

        visited = set()
        queue = deque([start])
        visited.add(start)
        while queue:
            x, y = queue.popleft()
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nx, ny = x + dx, y + dy
                if (
                    0 <= nx < width
                    and 0 <= ny < height
                    and (nx, ny) not in visited
                    and not grid[ny][nx]
                ):
                    visited.add((nx, ny))
                    queue.append((nx, ny))

        # Convert unreachable land to water
        for y in range(height):
            for x in range(width):
                if not grid[y][x] and (x, y) not in visited:
                    grid[y][x] = True

        return grid
