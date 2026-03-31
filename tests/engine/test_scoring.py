"""Tests for scoring."""

from server.engine.models import DietType, Dinosaur, Species
from server.engine.scoring import calculate_turn_score


class TestScoring:
    def test_single_dim1(self):
        sp = Species(player_id="p1", name="T", diet=DietType.HERBIVORE)
        sp.dinosaurs.append(
            Dinosaur(species_id=sp.id, x=0, y=0, dimension=1, max_lifespan=30)
        )
        assert calculate_turn_score(sp) == 2  # 1 + 1

    def test_multiple_dinos(self):
        sp = Species(player_id="p1", name="T", diet=DietType.HERBIVORE)
        sp.dinosaurs.append(
            Dinosaur(species_id=sp.id, x=0, y=0, dimension=1, max_lifespan=30)
        )
        sp.dinosaurs.append(
            Dinosaur(species_id=sp.id, x=1, y=1, dimension=3, max_lifespan=30)
        )
        assert calculate_turn_score(sp) == 2 + 4  # (1+1) + (3+1)

    def test_dead_dinos_excluded(self):
        sp = Species(player_id="p1", name="T", diet=DietType.HERBIVORE)
        sp.dinosaurs.append(
            Dinosaur(species_id=sp.id, x=0, y=0, dimension=5, max_lifespan=30, alive=False)
        )
        assert calculate_turn_score(sp) == 0

    def test_hatching_excluded(self):
        sp = Species(player_id="p1", name="T", diet=DietType.HERBIVORE)
        sp.dinosaurs.append(
            Dinosaur(species_id=sp.id, x=0, y=0, dimension=2, max_lifespan=30, hatching=True)
        )
        assert calculate_turn_score(sp) == 0

    def test_empty_species(self):
        sp = Species(player_id="p1", name="T", diet=DietType.HERBIVORE)
        assert calculate_turn_score(sp) == 0
