"""Tests for feeding mechanics."""

import random

from server.engine.feeding import decay_carrion, feed_dinosaur, regenerate_vegetation
from server.engine.models import Cell, CellType, DietType, Dinosaur, GameMap


def _make_dino(**kwargs) -> Dinosaur:
    defaults = {"species_id": "s1", "x": 0, "y": 0, "max_lifespan": 30}
    defaults.update(kwargs)
    return Dinosaur(**defaults)


class TestFeedDinosaur:
    def test_herbivore_eats_vegetation(self):
        dino = _make_dino(energy=500, dimension=1)
        cell = Cell(x=0, y=0, cell_type=CellType.VEGETATION, energy=300, max_energy=1000)
        eaten = feed_dinosaur(dino, cell, DietType.HERBIVORE)
        assert eaten == 300
        assert dino.energy == 800
        assert cell.energy == 0

    def test_herbivore_capped_at_max(self):
        dino = _make_dino(energy=900, dimension=1)  # max 1000
        cell = Cell(x=0, y=0, cell_type=CellType.VEGETATION, energy=500, max_energy=1000)
        eaten = feed_dinosaur(dino, cell, DietType.HERBIVORE)
        assert eaten == 100
        assert dino.energy == 1000
        assert cell.energy == 400

    def test_herbivore_ignores_carrion(self):
        dino = _make_dino(energy=500)
        cell = Cell(x=0, y=0, cell_type=CellType.CARRION, energy=300, max_energy=600)
        eaten = feed_dinosaur(dino, cell, DietType.HERBIVORE)
        assert eaten == 0
        assert dino.energy == 500

    def test_carnivore_eats_carrion(self):
        dino = _make_dino(energy=500, dimension=1)
        cell = Cell(x=0, y=0, cell_type=CellType.CARRION, energy=200, max_energy=600)
        eaten = feed_dinosaur(dino, cell, DietType.CARNIVORE)
        assert eaten == 200
        assert dino.energy == 700

    def test_carnivore_ignores_vegetation(self):
        dino = _make_dino(energy=500)
        cell = Cell(x=0, y=0, cell_type=CellType.VEGETATION, energy=300, max_energy=1000)
        eaten = feed_dinosaur(dino, cell, DietType.CARNIVORE)
        assert eaten == 0

    def test_no_food_on_plain(self):
        dino = _make_dino(energy=500)
        cell = Cell(x=0, y=0, cell_type=CellType.PLAIN)
        eaten = feed_dinosaur(dino, cell, DietType.HERBIVORE)
        assert eaten == 0


class TestRegenerateVegetation:
    def test_regen(self):
        cells = [[
            Cell(x=0, y=0, cell_type=CellType.VEGETATION, energy=0, max_energy=1000),
            Cell(x=1, y=0, cell_type=CellType.PLAIN),
        ]]
        gm = GameMap(width=2, height=1, cells=cells)
        regenerate_vegetation(gm)
        assert gm.get_cell(0, 0).energy == 50  # 1000 / 20

    def test_regen_capped(self):
        cells = [[
            Cell(x=0, y=0, cell_type=CellType.VEGETATION, energy=990, max_energy=1000),
        ]]
        gm = GameMap(width=1, height=1, cells=cells)
        regenerate_vegetation(gm)
        assert gm.get_cell(0, 0).energy == 1000


class TestDecayCarrion:
    def test_decay(self):
        cells = [[
            Cell(x=0, y=0, cell_type=CellType.CARRION, energy=300, max_energy=300),
            Cell(x=1, y=0, cell_type=CellType.PLAIN),
        ]]
        gm = GameMap(width=2, height=1, cells=cells)
        decay_carrion(gm, random.Random(1))
        assert gm.get_cell(0, 0).energy == 300 - 300 / 30

    def test_respawn_when_depleted(self):
        cells = [[
            Cell(x=0, y=0, cell_type=CellType.CARRION, energy=0, max_energy=300),
            Cell(x=1, y=0, cell_type=CellType.PLAIN),
        ]]
        gm = GameMap(width=2, height=1, cells=cells)
        decay_carrion(gm, random.Random(1))
        # Old carrion cell should be plain, new one should exist somewhere
        types = [gm.get_cell(0, 0).cell_type, gm.get_cell(1, 0).cell_type]
        assert CellType.CARRION in types
        assert gm.get_cell(0, 0).cell_type == CellType.PLAIN
