"""Tests for core data models."""

from server.engine.models import (
    Cell,
    CellType,
    Dinosaur,
    GameMap,
    Species,
    DietType,
)


class TestCell:
    def test_create_plain(self):
        c = Cell(x=0, y=0, cell_type=CellType.PLAIN)
        assert c.energy == 0.0
        assert c.max_energy == 0.0

    def test_create_vegetation(self):
        c = Cell(x=1, y=2, cell_type=CellType.VEGETATION, energy=500, max_energy=1000)
        assert c.energy == 500
        assert c.max_energy == 1000


class TestGameMap:
    def test_get_cell(self, small_map):
        cell = small_map.get_cell(0, 0)
        assert cell.x == 0
        assert cell.y == 0

    def test_in_bounds(self, small_map):
        assert small_map.in_bounds(0, 0)
        assert small_map.in_bounds(9, 9)
        assert not small_map.in_bounds(-1, 0)
        assert not small_map.in_bounds(10, 0)
        assert not small_map.in_bounds(0, 10)

    def test_is_passable(self, small_map):
        # Out of bounds is not passable
        assert not small_map.is_passable(-1, 0)
        # Water is not passable
        for row in small_map.cells:
            for cell in row:
                if cell.cell_type == CellType.WATER:
                    assert not small_map.is_passable(cell.x, cell.y)
                else:
                    assert small_map.is_passable(cell.x, cell.y)


class TestDinosaur:
    def test_max_energy(self):
        d = Dinosaur(species_id="s1", x=0, y=0, dimension=3, max_lifespan=30)
        assert d.max_energy == 3000

    def test_vision_range(self):
        d1 = Dinosaur(species_id="s1", x=0, y=0, dimension=1, max_lifespan=30)
        assert d1.vision_range == 2

        d3 = Dinosaur(species_id="s1", x=0, y=0, dimension=3, max_lifespan=30)
        assert d3.vision_range == 3

        d5 = Dinosaur(species_id="s1", x=0, y=0, dimension=5, max_lifespan=30)
        assert d5.vision_range == 4

    def test_default_values(self):
        d = Dinosaur(species_id="s1", x=5, y=5, max_lifespan=30)
        assert d.dimension == 1
        assert d.energy == 750
        assert d.age == 0
        assert d.alive is True
        assert d.hatching is False


class TestSpecies:
    def test_alive_dinos(self):
        s = Species(player_id="p1", name="T", diet=DietType.HERBIVORE)
        d1 = Dinosaur(species_id=s.id, x=0, y=0, max_lifespan=30)
        d2 = Dinosaur(species_id=s.id, x=1, y=1, max_lifespan=30, alive=False)
        d3 = Dinosaur(species_id=s.id, x=2, y=2, max_lifespan=30, hatching=True)
        s.dinosaurs = [d1, d2, d3]
        assert s.dino_count == 1
        assert s.alive_dinos == [d1]

    def test_reveal(self):
        s = Species(player_id="p1", name="T", diet=DietType.HERBIVORE)
        s.reveal({(0, 0), (1, 1)})
        assert (0, 0) in s.revealed_set
        assert (1, 1) in s.revealed_set
        # Revealing again shouldn't duplicate
        s.reveal({(0, 0), (2, 2)})
        assert len(s.revealed_cells) == 3

    def test_serialization_roundtrip(self):
        s = Species(player_id="p1", name="T", diet=DietType.HERBIVORE)
        s.reveal({(1, 2), (3, 4)})
        data = s.model_dump()
        s2 = Species.model_validate(data)
        assert s2.revealed_set == s.revealed_set
