"""Score calculation."""

from __future__ import annotations

from server.engine.models import Species


def calculate_turn_score(species: Species) -> int:
    """Return sum of (dimension + 1) for each alive, non-hatching dino."""
    return sum(d.dimension + 1 for d in species.alive_dinos)
