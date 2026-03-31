"""Tests for map generation."""

import random
from collections import deque

from server.engine.mapgen.simple import SimpleMapGenerator
from server.engine.models import CellType


class TestSimpleMapGenerator:
    def test_correct_dimensions(self):
        gen = SimpleMapGenerator()
        gm = gen.generate(20, 15, random.Random(42))
        assert gm.width == 20
        assert gm.height == 15
        assert len(gm.cells) == 15
        assert len(gm.cells[0]) == 20

    def test_has_all_cell_types(self):
        gen = SimpleMapGenerator()
        gm = gen.generate(30, 30, random.Random(42))
        types = set()
        for row in gm.cells:
            for cell in row:
                types.add(cell.cell_type)
        assert CellType.WATER in types
        assert CellType.PLAIN in types
        assert CellType.VEGETATION in types
        assert CellType.CARRION in types

    def test_deterministic_with_same_seed(self):
        gen = SimpleMapGenerator()
        gm1 = gen.generate(20, 20, random.Random(99))
        gm2 = gen.generate(20, 20, random.Random(99))
        for y in range(20):
            for x in range(20):
                assert gm1.get_cell(x, y).cell_type == gm2.get_cell(x, y).cell_type

    def test_land_is_connected(self):
        gen = SimpleMapGenerator()
        gm = gen.generate(30, 30, random.Random(42))

        # Find a land cell
        land_cells = set()
        start = None
        for y in range(gm.height):
            for x in range(gm.width):
                if gm.get_cell(x, y).cell_type != CellType.WATER:
                    land_cells.add((x, y))
                    if start is None:
                        start = (x, y)

        if not land_cells:
            return  # all water, trivially connected

        # BFS from start
        visited = {start}
        queue = deque([start])
        while queue:
            x, y = queue.popleft()
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nx, ny = x + dx, y + dy
                if (nx, ny) in land_cells and (nx, ny) not in visited:
                    visited.add((nx, ny))
                    queue.append((nx, ny))

        assert visited == land_cells, "Not all land cells are connected"

    def test_vegetation_has_energy(self):
        gen = SimpleMapGenerator()
        gm = gen.generate(20, 20, random.Random(42))
        for row in gm.cells:
            for cell in row:
                if cell.cell_type == CellType.VEGETATION:
                    assert cell.energy > 0
                    assert cell.max_energy > 0
                    assert cell.energy == cell.max_energy  # starts full

    def test_carrion_has_energy(self):
        gen = SimpleMapGenerator()
        gm = gen.generate(20, 20, random.Random(42))
        for row in gm.cells:
            for cell in row:
                if cell.cell_type == CellType.CARRION:
                    assert cell.energy > 0
                    assert cell.max_energy > 0
