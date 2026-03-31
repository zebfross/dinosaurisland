"""Fog of war and visibility calculations."""

from __future__ import annotations

from server.engine.models import GameMap, Species


def cells_in_vision(
    x: int,
    y: int,
    vision_range: int,
    game_map: GameMap,
) -> set[tuple[int, int]]:
    """Return set of (x, y) cells visible from position within vision_range.
    Uses Chebyshev distance (square vision area)."""
    result = set()
    for dy in range(-vision_range, vision_range + 1):
        for dx in range(-vision_range, vision_range + 1):
            nx, ny = x + dx, y + dy
            if game_map.in_bounds(nx, ny):
                result.add((nx, ny))
    return result


def update_fog_of_war(species: Species, game_map: GameMap) -> None:
    """Update species' revealed cells based on current alive dino positions."""
    new_cells: set[tuple[int, int]] = set()
    for dino in species.alive_dinos:
        new_cells |= cells_in_vision(dino.x, dino.y, dino.vision_range, game_map)
    species.reveal(new_cells)
