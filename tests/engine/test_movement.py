"""Tests for movement and pathfinding."""

from server.engine.models import Cell, CellType, GameMap
from server.engine.movement import find_path, movement_cost, reachable_cells


def _make_grid(layout: list[str]) -> GameMap:
    """Create a GameMap from a string layout.
    '.' = plain, '#' = water, 'V' = vegetation, 'C' = carrion
    """
    height = len(layout)
    width = len(layout[0])
    cells = []
    for y, row_str in enumerate(layout):
        row = []
        for x, ch in enumerate(row_str):
            if ch == "#":
                row.append(Cell(x=x, y=y, cell_type=CellType.WATER))
            elif ch == "V":
                row.append(
                    Cell(
                        x=x, y=y, cell_type=CellType.VEGETATION,
                        energy=500, max_energy=1000,
                    )
                )
            elif ch == "C":
                row.append(
                    Cell(
                        x=x, y=y, cell_type=CellType.CARRION,
                        energy=300, max_energy=600,
                    )
                )
            else:
                row.append(Cell(x=x, y=y, cell_type=CellType.PLAIN))
        cells.append(row)
    return GameMap(width=width, height=height, cells=cells)


class TestMovementCost:
    def test_one_step(self):
        assert movement_cost(1) == 20

    def test_two_steps(self):
        assert movement_cost(2) == 40

    def test_three_steps(self):
        assert movement_cost(3) == 80


class TestReachableCells:
    def test_open_field_one_step(self):
        gm = _make_grid([
            ".....",
            ".....",
            ".....",
            ".....",
            ".....",
        ])
        result = reachable_cells(gm, 2, 2, 1)
        assert (1, 2) in result
        assert (3, 2) in result
        assert (2, 1) in result
        assert (2, 3) in result
        assert (2, 2) not in result  # start cell excluded
        assert len(result) == 4

    def test_open_field_two_steps(self):
        gm = _make_grid([
            ".....",
            ".....",
            ".....",
            ".....",
            ".....",
        ])
        result = reachable_cells(gm, 2, 2, 2)
        # 2 steps: 4 direct neighbors + 8 two-step cells = 12
        assert len(result) == 12

    def test_blocked_by_water(self):
        gm = _make_grid([
            "...",
            ".#.",
            "...",
        ])
        result = reachable_cells(gm, 0, 0, 2)
        assert (1, 1) not in result  # water cell

    def test_path_around_water(self):
        gm = _make_grid([
            "...",
            "#..",
            "...",
        ])
        result = reachable_cells(gm, 0, 0, 3)
        # (0,0)->(1,0)->(1,1)->(0,2) is 3 steps but (0,2) needs going (1,0)->(1,1)->(1,2)->(0,2) = 4 steps
        # Actually (1,0)->(1,1)->(0,2) is NOT valid since movement is cardinal only
        # The path is (0,0)->(1,0)->(1,1)->(1,2) then (1,2)->(0,2) = 4 steps
        # With 3 steps we can reach (1,2) but not (0,2)
        assert (1, 2) in result  # can go right, down, down
        assert (0, 0) not in result  # start excluded

    def test_corner_start(self):
        gm = _make_grid([
            "...",
            "...",
            "...",
        ])
        result = reachable_cells(gm, 0, 0, 1)
        assert len(result) == 2  # right and down only


class TestFindPath:
    def test_same_cell(self):
        gm = _make_grid(["..."])
        path = find_path(gm, 0, 0, 0, 0)
        assert path == []

    def test_adjacent(self):
        gm = _make_grid(["..."])
        path = find_path(gm, 0, 0, 1, 0)
        assert path == [(1, 0)]

    def test_around_water(self):
        gm = _make_grid([
            "...",
            ".#.",
            "...",
        ])
        path = find_path(gm, 0, 0, 2, 2)
        assert path is not None
        assert (1, 1) not in path  # doesn't go through water
        assert path[-1] == (2, 2)

    def test_unreachable(self):
        gm = _make_grid([
            ".#.",
            "###",
            ".#.",
        ])
        path = find_path(gm, 0, 0, 2, 0)
        assert path is None

    def test_target_is_water(self):
        gm = _make_grid([".#."])
        path = find_path(gm, 0, 0, 1, 0)
        assert path is None
