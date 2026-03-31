"""Tests for the GameEngine orchestrator."""

import random

import pytest

from server.engine.game import GameEngine
from server.engine.models import (
    Action,
    ActionType,
    DietType,
    GamePhase,
    TurnActions,
)


class TestGameLifecycle:
    def test_create_game(self, engine):
        state = engine.create_game(width=15, height=15)
        assert state.game_map.width == 15
        assert state.turn == 0
        assert state.phase == GamePhase.WAITING

    def test_add_species(self, engine, game_state):
        sp = engine.add_species(game_state, "p1", "Rex", DietType.CARNIVORE)
        assert sp.name == "Rex"
        assert sp.diet == DietType.CARNIVORE
        assert sp.dino_count == 1
        assert sp.id in game_state.species

    def test_species_initial_fog(self, engine, game_state):
        sp = engine.add_species(game_state, "p1", "T", DietType.HERBIVORE)
        assert len(sp.revealed_set) > 0

    def test_start_game(self, engine, game_state):
        engine.add_species(game_state, "p1", "T", DietType.HERBIVORE)
        engine.start_game(game_state)
        assert game_state.phase == GamePhase.ACTIVE

    def test_start_empty_game_fails(self, engine, game_state):
        with pytest.raises(ValueError, match="no species"):
            engine.start_game(game_state)


class TestTurnProcessing:
    def test_turn_increments(self, engine, two_player_game):
        state, sp1, sp2 = two_player_game
        assert state.turn == 0
        engine.process_turn(state)
        assert state.turn == 1

    def test_scores_increase(self, engine, two_player_game):
        state, sp1, sp2 = two_player_game
        result = engine.process_turn(state)
        assert result.score_deltas[sp1.id] == 2  # dim 1 + 1
        assert result.score_deltas[sp2.id] == 2
        assert sp1.score == 2
        assert sp2.score == 2

    def test_dino_ages(self, engine, two_player_game):
        state, sp1, _ = two_player_game
        dino = sp1.alive_dinos[0]
        assert dino.age == 0
        engine.process_turn(state)
        assert dino.age == 1

    def test_dino_dies_of_old_age(self, engine, two_player_game):
        state, sp1, _ = two_player_game
        dino = sp1.alive_dinos[0]
        dino.max_lifespan = 1  # dies after 1 turn
        result = engine.process_turn(state)
        assert not dino.alive
        assert dino.id in result.deaths

    def test_game_ends_at_max_turns(self, engine):
        state = engine.create_game(width=10, height=10, max_turns=3)
        engine.add_species(state, "p1", "T", DietType.HERBIVORE)
        engine.start_game(state)
        for _ in range(3):
            engine.process_turn(state)
        assert state.phase == GamePhase.FINISHED

    def test_game_ends_when_all_dead(self, engine):
        state = engine.create_game(width=10, height=10, max_turns=120)
        sp = engine.add_species(state, "p1", "T", DietType.HERBIVORE)
        engine.start_game(state)
        # Kill all dinos
        for d in sp.dinosaurs:
            d.max_lifespan = 1
        engine.process_turn(state)
        assert state.phase == GamePhase.FINISHED


class TestActions:
    def test_move_action(self, engine, two_player_game):
        state, sp1, _ = two_player_game
        dino = sp1.alive_dinos[0]
        original_energy = dino.energy

        # Find a valid adjacent cell
        legal = engine.get_legal_actions(state, dino.id)
        moves = [a for a in legal if a.action_type == ActionType.MOVE]
        assert len(moves) > 0

        move = moves[0]
        errors = engine.submit_actions(
            state, TurnActions(species_id=sp1.id, actions=[move])
        )
        assert len(errors) == 0

        engine.process_turn(state)
        assert dino.x == move.target_x
        assert dino.y == move.target_y
        assert dino.energy < original_energy  # movement costs energy

    def test_grow_action(self, engine, two_player_game):
        state, sp1, _ = two_player_game
        dino = sp1.alive_dinos[0]
        dino.energy = 1000  # enough to grow (cost = 2000 * 0.5 = 1000)

        action = Action(dino_id=dino.id, action_type=ActionType.GROW)
        engine.submit_actions(
            state, TurnActions(species_id=sp1.id, actions=[action])
        )
        engine.process_turn(state)
        assert dino.dimension == 2

    def test_lay_egg_and_hatch(self, engine, two_player_game):
        state, sp1, _ = two_player_game
        dino = sp1.alive_dinos[0]
        dino.energy = 2000

        action = Action(dino_id=dino.id, action_type=ActionType.LAY_EGG)
        engine.submit_actions(
            state, TurnActions(species_id=sp1.id, actions=[action])
        )
        result1 = engine.process_turn(state)
        assert len(sp1.eggs) == 1
        assert dino.energy == 2000 - 1500

        # Next turn, egg hatches
        result2 = engine.process_turn(state)
        assert len(sp1.eggs) == 0
        assert len(result2.hatches) == 1
        assert sp1.dino_count == 2  # original + hatched

    def test_rest_action(self, engine, two_player_game):
        state, sp1, _ = two_player_game
        dino = sp1.alive_dinos[0]
        energy_before = dino.energy
        x_before, y_before = dino.x, dino.y

        action = Action(dino_id=dino.id, action_type=ActionType.REST)
        engine.submit_actions(
            state, TurnActions(species_id=sp1.id, actions=[action])
        )
        engine.process_turn(state)
        assert dino.x == x_before
        assert dino.y == y_before

    def test_invalid_action_returned(self, engine, two_player_game):
        state, sp1, _ = two_player_game
        dino = sp1.alive_dinos[0]
        # Move to out-of-bounds
        bad = Action(dino_id=dino.id, action_type=ActionType.MOVE, target_x=999, target_y=999)
        errors = engine.submit_actions(
            state, TurnActions(species_id=sp1.id, actions=[bad])
        )
        assert len(errors) == 1


class TestVisibleState:
    def test_visible_state_structure(self, engine, two_player_game):
        state, sp1, _ = two_player_game
        vis = engine.get_visible_state(state, sp1.id)
        assert "turn" in vis
        assert "visible_cells" in vis
        assert "visible_dinos" in vis
        assert "my_species" in vis
        assert "scores" in vis

    def test_fog_of_war_limits_cells(self, engine, two_player_game):
        state, sp1, _ = two_player_game
        vis = engine.get_visible_state(state, sp1.id)
        total_cells = state.game_map.width * state.game_map.height
        assert len(vis["visible_cells"]) < total_cells


class TestLegalActions:
    def test_always_includes_rest(self, engine, two_player_game):
        state, sp1, _ = two_player_game
        dino = sp1.alive_dinos[0]
        legal = engine.get_legal_actions(state, dino.id)
        rest_actions = [a for a in legal if a.action_type == ActionType.REST]
        assert len(rest_actions) == 1

    def test_dead_dino_no_actions(self, engine, two_player_game):
        state, sp1, _ = two_player_game
        dino = sp1.alive_dinos[0]
        dino.alive = False
        legal = engine.get_legal_actions(state, dino.id)
        assert len(legal) == 0
