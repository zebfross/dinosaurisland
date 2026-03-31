"""Shared fixtures for engine tests."""

import random

import pytest

from server.engine.game import GameEngine
from server.engine.mapgen.simple import SimpleMapGenerator
from server.engine.models import DietType, GameState, Species


@pytest.fixture
def rng():
    return random.Random(42)


@pytest.fixture
def engine(rng):
    return GameEngine(rng=rng)


@pytest.fixture
def small_map(rng):
    gen = SimpleMapGenerator(water_ratio=0.2, smoothing_iterations=2)
    return gen.generate(10, 10, rng)


@pytest.fixture
def game_state(engine) -> GameState:
    """A fresh game with a 15x15 map, not yet started."""
    return engine.create_game(width=15, height=15)


@pytest.fixture
def two_player_game(engine, game_state) -> tuple[GameState, Species, Species]:
    """Game with 1 herbivore and 1 carnivore species, started."""
    sp1 = engine.add_species(game_state, "p1", "Herbs", DietType.HERBIVORE)
    sp2 = engine.add_species(game_state, "p2", "Carns", DietType.CARNIVORE)
    engine.start_game(game_state)
    return game_state, sp1, sp2
