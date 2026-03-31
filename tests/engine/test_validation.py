"""Tests for action validation."""

import pytest

from server.engine.models import (
    Action,
    ActionType,
    Cell,
    CellType,
    DietType,
    Dinosaur,
    GameMap,
    GameState,
    InvalidActionError,
    Species,
)
from server.engine.validation import validate_action


def _make_plain_map(width: int, height: int) -> GameMap:
    cells = [
        [Cell(x=x, y=y, cell_type=CellType.PLAIN) for x in range(width)]
        for y in range(height)
    ]
    return GameMap(width=width, height=height, cells=cells)


def _setup_game() -> tuple[GameState, Species, Dinosaur]:
    gm = _make_plain_map(10, 10)
    state = GameState(game_map=gm)
    sp = Species(player_id="p1", name="Herbs", diet=DietType.HERBIVORE)
    d = Dinosaur(species_id=sp.id, x=5, y=5, dimension=1, energy=750, max_lifespan=30)
    sp.dinosaurs.append(d)
    state.species[sp.id] = sp
    return state, sp, d


class TestMoveValidation:
    def test_valid_move(self):
        state, sp, d = _setup_game()
        action = Action(dino_id=d.id, action_type=ActionType.MOVE, target_x=6, target_y=5)
        validate_action(state, sp, d, action)  # should not raise

    def test_move_out_of_bounds(self):
        state, sp, d = _setup_game()
        action = Action(dino_id=d.id, action_type=ActionType.MOVE, target_x=10, target_y=5)
        with pytest.raises(InvalidActionError, match="out of bounds"):
            validate_action(state, sp, d, action)

    def test_move_to_water(self):
        state, sp, d = _setup_game()
        state.game_map.cells[5][6] = Cell(x=6, y=5, cell_type=CellType.WATER)
        action = Action(dino_id=d.id, action_type=ActionType.MOVE, target_x=6, target_y=5)
        with pytest.raises(InvalidActionError, match="water"):
            validate_action(state, sp, d, action)

    def test_move_too_far(self):
        state, sp, d = _setup_game()
        action = Action(dino_id=d.id, action_type=ActionType.MOVE, target_x=8, target_y=5)
        with pytest.raises(InvalidActionError, match="not reachable"):
            validate_action(state, sp, d, action)

    def test_move_no_coords(self):
        state, sp, d = _setup_game()
        action = Action(dino_id=d.id, action_type=ActionType.MOVE)
        with pytest.raises(InvalidActionError, match="target coordinates"):
            validate_action(state, sp, d, action)

    def test_herbivore_onto_herbivore(self):
        state, sp, d = _setup_game()
        d2 = Dinosaur(species_id=sp.id, x=6, y=5, max_lifespan=30)
        sp.dinosaurs.append(d2)
        action = Action(dino_id=d.id, action_type=ActionType.MOVE, target_x=6, target_y=5)
        with pytest.raises(InvalidActionError, match="Herbivores cannot"):
            validate_action(state, sp, d, action)


class TestGrowValidation:
    def test_valid_grow(self):
        state, sp, d = _setup_game()
        d.energy = 1000  # cost to grow from dim 1->2 is 2000*0.5=1000
        action = Action(dino_id=d.id, action_type=ActionType.GROW)
        validate_action(state, sp, d, action)  # should not raise

    def test_grow_not_enough_energy(self):
        state, sp, d = _setup_game()
        d.energy = 500  # need 1000 (dim 2 max=2000, cost=1000)
        action = Action(dino_id=d.id, action_type=ActionType.GROW)
        with pytest.raises(InvalidActionError, match="Not enough energy"):
            validate_action(state, sp, d, action)

    def test_grow_at_max_dim(self):
        state, sp, d = _setup_game()
        d.dimension = 5
        d.energy = 5000
        action = Action(dino_id=d.id, action_type=ActionType.GROW)
        with pytest.raises(InvalidActionError, match="max dimension"):
            validate_action(state, sp, d, action)


class TestLayEggValidation:
    def test_valid_lay_egg(self):
        state, sp, d = _setup_game()
        d.energy = 2000
        action = Action(dino_id=d.id, action_type=ActionType.LAY_EGG)
        validate_action(state, sp, d, action)

    def test_not_enough_energy(self):
        state, sp, d = _setup_game()
        d.energy = 1000
        action = Action(dino_id=d.id, action_type=ActionType.LAY_EGG)
        with pytest.raises(InvalidActionError, match="Not enough energy"):
            validate_action(state, sp, d, action)

    def test_max_dinos(self):
        state, sp, d = _setup_game()
        d.energy = 2000
        # Add 4 more dinos to hit the limit
        for i in range(4):
            sp.dinosaurs.append(
                Dinosaur(species_id=sp.id, x=i, y=0, max_lifespan=30)
            )
        action = Action(dino_id=d.id, action_type=ActionType.LAY_EGG)
        with pytest.raises(InvalidActionError, match="max dinosaurs"):
            validate_action(state, sp, d, action)


class TestDeadDino:
    def test_dead_dino_rejected(self):
        state, sp, d = _setup_game()
        d.alive = False
        action = Action(dino_id=d.id, action_type=ActionType.REST)
        with pytest.raises(InvalidActionError, match="dead"):
            validate_action(state, sp, d, action)

    def test_hatching_dino_rejected(self):
        state, sp, d = _setup_game()
        d.hatching = True
        action = Action(dino_id=d.id, action_type=ActionType.REST)
        with pytest.raises(InvalidActionError, match="hatching"):
            validate_action(state, sp, d, action)
