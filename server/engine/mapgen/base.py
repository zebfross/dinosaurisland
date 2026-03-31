"""Map generator protocol."""

from __future__ import annotations

import random
from typing import Protocol

from server.engine.models import GameMap


class MapGenerator(Protocol):
    def generate(self, width: int, height: int, rng: random.Random) -> GameMap: ...
