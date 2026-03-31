"""Integration test: full 120-turn game with random actions."""

import random

from server.engine.game import GameEngine
from server.engine.models import (
    ActionType,
    DietType,
    GamePhase,
    TurnActions,
)


def test_full_game_120_turns():
    """Run a complete 120-turn game with 2 species making random legal moves.
    Assert no crashes, positive scores, consistent state."""
    rng = random.Random(42)
    engine = GameEngine(rng=rng)
    state = engine.create_game(width=30, height=30, max_turns=120)

    sp1 = engine.add_species(state, "p1", "GreenTeam", DietType.HERBIVORE)
    sp2 = engine.add_species(state, "p2", "RedTeam", DietType.CARNIVORE)
    engine.start_game(state)

    action_rng = random.Random(123)

    while state.phase == GamePhase.ACTIVE:
        # Each species picks random legal actions for each dino
        for species in state.species.values():
            actions = []
            for dino in species.alive_dinos:
                legal = engine.get_legal_actions(state, dino.id)
                if legal:
                    chosen = action_rng.choice(legal)
                    actions.append(chosen)
            if actions:
                engine.submit_actions(
                    state, TurnActions(species_id=species.id, actions=actions)
                )

        engine.process_turn(state)

    assert state.phase == GamePhase.FINISHED
    assert state.turn <= 120

    # At least one species should have scored
    total_score = sum(s.score for s in state.species.values())
    assert total_score > 0

    # All dino energy should be non-negative
    for species in state.species.values():
        for dino in species.dinosaurs:
            if dino.alive:
                assert dino.energy >= 0

    # Turn results should be recorded
    assert len(state.turn_results) == state.turn


def test_full_game_with_four_species():
    """Bigger game: 4 species, mix of diets."""
    rng = random.Random(99)
    engine = GameEngine(rng=rng)
    state = engine.create_game(width=40, height=40, max_turns=60)

    engine.add_species(state, "p1", "Alpha", DietType.HERBIVORE)
    engine.add_species(state, "p2", "Beta", DietType.CARNIVORE)
    engine.add_species(state, "p3", "Gamma", DietType.HERBIVORE)
    engine.add_species(state, "p4", "Delta", DietType.CARNIVORE)
    engine.start_game(state)

    action_rng = random.Random(456)

    while state.phase == GamePhase.ACTIVE:
        for species in state.species.values():
            actions = []
            for dino in species.alive_dinos:
                legal = engine.get_legal_actions(state, dino.id)
                if legal:
                    actions.append(action_rng.choice(legal))
            if actions:
                engine.submit_actions(
                    state, TurnActions(species_id=species.id, actions=actions)
                )
        engine.process_turn(state)

    assert state.phase == GamePhase.FINISHED
    assert len(state.turn_results) == state.turn
