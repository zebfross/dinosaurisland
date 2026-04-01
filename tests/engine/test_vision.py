"""Tests for fog of war and visibility."""

from server.engine.models import Cell, CellType, Dinosaur, DietType, GameMap, Species
from server.engine.vision import cells_in_vision, update_fog_of_war


def _make_plain_map(width: int, height: int) -> GameMap:
    cells = [
        [Cell(x=x, y=y, cell_type=CellType.PLAIN) for x in range(width)]
        for y in range(height)
    ]
    return GameMap(width=width, height=height, cells=cells)


class TestCellsInVision:
    def test_center_of_map(self):
        gm = _make_plain_map(10, 10)
        visible = cells_in_vision(5, 5, 2, gm)
        # Chebyshev distance 2: 5x5 square = 25 cells
        assert len(visible) == 25
        assert (5, 5) in visible
        assert (3, 3) in visible
        assert (7, 7) in visible
        assert (2, 5) not in visible  # too far

    def test_corner_clipped(self):
        gm = _make_plain_map(10, 10)
        visible = cells_in_vision(0, 0, 2, gm)
        # Only the 3x3 quadrant that's in bounds
        assert len(visible) == 9
        assert (0, 0) in visible
        assert (2, 2) in visible
        assert (-1, 0) not in visible

    def test_range_1(self):
        gm = _make_plain_map(5, 5)
        visible = cells_in_vision(2, 2, 1, gm)
        # 3x3 = 9
        assert len(visible) == 9


class TestUpdateFogOfWar:
    def test_reveals_cells(self):
        gm = _make_plain_map(10, 10)
        sp = Species(player_id="p1", name="T", diet=DietType.HERBIVORE)
        d = Dinosaur(species_id=sp.id, x=5, y=5, dimension=1, max_lifespan=30)
        sp.dinosaurs.append(d)

        update_fog_of_war(sp, gm)
        revealed = sp.revealed_set
        assert (5, 5) in revealed
        assert len(revealed) == 49  # dim 1 = vision 3, 7x7 = 49

    def test_persistence(self):
        gm = _make_plain_map(20, 20)
        sp = Species(player_id="p1", name="T", diet=DietType.HERBIVORE)
        d = Dinosaur(species_id=sp.id, x=5, y=5, dimension=1, max_lifespan=30)
        sp.dinosaurs.append(d)

        update_fog_of_war(sp, gm)
        first_reveal = len(sp.revealed_set)

        # Move dino
        d.x = 15
        d.y = 15
        update_fog_of_war(sp, gm)

        # Should have both old and new cells
        assert len(sp.revealed_set) > first_reveal
        assert (5, 5) in sp.revealed_set  # old position still revealed
        assert (15, 15) in sp.revealed_set

    def test_multiple_dinos(self):
        gm = _make_plain_map(20, 20)
        sp = Species(player_id="p1", name="T", diet=DietType.HERBIVORE)
        d1 = Dinosaur(species_id=sp.id, x=2, y=2, dimension=1, max_lifespan=30)
        d2 = Dinosaur(species_id=sp.id, x=17, y=17, dimension=1, max_lifespan=30)
        sp.dinosaurs.extend([d1, d2])

        update_fog_of_war(sp, gm)
        revealed = sp.revealed_set
        assert (2, 2) in revealed
        assert (17, 17) in revealed
