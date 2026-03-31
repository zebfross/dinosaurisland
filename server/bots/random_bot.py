"""Random bot — picks random legal actions each turn."""

from __future__ import annotations

import random

from server.bots.base import BotStrategy
from server.engine.game import GameEngine
from server.engine.models import Action, GameState, Species


class RandomBot(BotStrategy):
    """Picks a random legal action for each dinosaur each turn."""

    def __init__(self, rng: random.Random | None = None):
        self.rng = rng or random.Random()

    def decide_actions(
        self,
        engine: GameEngine,
        state: GameState,
        species: Species,
    ) -> list[Action]:
        actions: list[Action] = []
        for dino in species.alive_dinos:
            legal = engine.get_legal_actions(state, dino.id)
            if legal:
                actions.append(self.rng.choice(legal))
        return actions
