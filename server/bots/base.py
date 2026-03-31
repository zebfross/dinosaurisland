"""Bot strategy interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from server.engine.game import GameEngine
from server.engine.models import Action, GameState, Species


class BotStrategy(ABC):
    """Base class for AI bot strategies."""

    @abstractmethod
    def decide_actions(
        self,
        engine: GameEngine,
        state: GameState,
        species: Species,
    ) -> list[Action]:
        """Given the current game state, return a list of actions for this species.
        One action per alive dinosaur."""
        ...
