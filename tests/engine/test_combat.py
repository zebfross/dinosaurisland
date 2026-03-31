"""Tests for combat resolution."""

import pytest

from server.engine.combat import (
    IllegalCombatError,
    compute_combat_power,
    resolve_combat,
)
from server.engine.models import DietType, Dinosaur


def _make_dino(**kwargs) -> Dinosaur:
    defaults = {"species_id": "s1", "x": 0, "y": 0, "max_lifespan": 30}
    defaults.update(kwargs)
    return Dinosaur(**defaults)


class TestCombatPower:
    def test_herbivore_power(self):
        d = _make_dino(dimension=2, energy=500)
        assert compute_combat_power(d, DietType.HERBIVORE) == 1000

    def test_carnivore_double_power(self):
        d = _make_dino(dimension=2, energy=500)
        assert compute_combat_power(d, DietType.CARNIVORE) == 2000


class TestResolveCombat:
    def test_carnivore_beats_herbivore(self):
        attacker = _make_dino(dimension=1, energy=500, species_id="s1")
        defender = _make_dino(dimension=1, energy=500, species_id="s2")
        result = resolve_combat(attacker, DietType.CARNIVORE, defender, DietType.HERBIVORE)
        assert result.winner_id == attacker.id  # carnivore has 2x multiplier
        assert result.loser_id == defender.id
        assert not defender.alive
        assert result.energy_transferred > 0

    def test_big_herbivore_beats_small_carnivore(self):
        attacker = _make_dino(dimension=5, energy=5000, species_id="s1")
        defender = _make_dino(dimension=1, energy=100, species_id="s2")
        result = resolve_combat(attacker, DietType.HERBIVORE, defender, DietType.CARNIVORE)
        # herb power: 5*5000=25000, carn power: 1*100*2=200
        assert result.winner_id == attacker.id
        assert result.energy_transferred == 0  # herbivore winner doesn't absorb

    def test_carnivore_absorbs_energy(self):
        attacker = _make_dino(dimension=2, energy=500, species_id="s1")
        defender = _make_dino(dimension=1, energy=400, species_id="s2")
        result = resolve_combat(attacker, DietType.CARNIVORE, defender, DietType.HERBIVORE)
        assert result.energy_transferred == 400 * 0.75  # 75% of 400 = 300
        assert attacker.energy == 500 + 300

    def test_carnivore_absorption_capped_at_max(self):
        attacker = _make_dino(dimension=1, energy=900, species_id="s1")
        defender = _make_dino(dimension=1, energy=800, species_id="s2")
        result = resolve_combat(attacker, DietType.CARNIVORE, defender, DietType.HERBIVORE)
        # 75% of 800 = 600, but attacker max is 1000, can only absorb 100
        assert attacker.energy == 1000
        assert result.energy_transferred == 100

    def test_two_herbivores_raises(self):
        a = _make_dino(species_id="s1")
        d = _make_dino(species_id="s2")
        with pytest.raises(IllegalCombatError):
            resolve_combat(a, DietType.HERBIVORE, d, DietType.HERBIVORE)

    def test_tie_goes_to_attacker(self):
        a = _make_dino(dimension=1, energy=500, species_id="s1")
        d = _make_dino(dimension=1, energy=500, species_id="s2")
        # Both carnivore: same power
        result = resolve_combat(a, DietType.CARNIVORE, d, DietType.CARNIVORE)
        assert result.winner_id == a.id

    def test_loser_dies(self):
        a = _make_dino(dimension=3, energy=3000, species_id="s1")
        d = _make_dino(dimension=1, energy=100, species_id="s2")
        resolve_combat(a, DietType.CARNIVORE, d, DietType.HERBIVORE)
        assert not d.alive
        assert a.alive
