"""Feeding mechanics, vegetation regeneration, and carrion decay."""

from __future__ import annotations

import random

from server.engine.constants import CARRION_DECAY_FRACTION, VEG_REGEN_FRACTION
from server.engine.models import Cell, CellType, DietType, Dinosaur, GameMap


def feed_dinosaur(dino: Dinosaur, cell: Cell, diet: DietType) -> float:
    """Auto-eat: herbivore eats vegetation, carnivore eats carrion.
    Returns energy consumed. Caps at dino's max_energy."""
    if diet == DietType.HERBIVORE and cell.cell_type == CellType.VEGETATION:
        can_eat = min(cell.energy, dino.max_energy - dino.energy)
        if can_eat > 0:
            dino.energy += can_eat
            cell.energy -= can_eat
            return can_eat
    elif diet == DietType.CARNIVORE and cell.cell_type == CellType.CARRION:
        can_eat = min(cell.energy, dino.max_energy - dino.energy)
        if can_eat > 0:
            dino.energy += can_eat
            cell.energy -= can_eat
            return can_eat
    return 0.0


def regenerate_vegetation(game_map: GameMap) -> None:
    """All vegetation cells regenerate 1/20th of max_energy per turn."""
    for row in game_map.cells:
        for cell in row:
            if cell.cell_type == CellType.VEGETATION:
                regen = cell.max_energy * VEG_REGEN_FRACTION
                cell.energy = min(cell.energy + regen, cell.max_energy)


def decay_carrion(game_map: GameMap, rng: random.Random) -> None:
    """All carrion cells lose 1/30th of max_energy per turn.
    When a carrion cell hits 0, it becomes PLAIN and a new random PLAIN cell
    becomes CARRION with fresh energy."""
    depleted: list[Cell] = []

    for row in game_map.cells:
        for cell in row:
            if cell.cell_type == CellType.CARRION:
                decay = cell.max_energy * CARRION_DECAY_FRACTION
                cell.energy = max(0.0, cell.energy - decay)
                if cell.energy <= 0:
                    depleted.append(cell)

    # Respawn depleted carrion on random plain cells
    plain_cells = [
        cell
        for row in game_map.cells
        for cell in row
        if cell.cell_type == CellType.PLAIN
    ]

    for old_cell in depleted:
        old_cell.cell_type = CellType.PLAIN
        old_cell.energy = 0.0
        old_cell.max_energy = 0.0

        if plain_cells:
            new_cell = rng.choice(plain_cells)
            plain_cells.remove(new_cell)
            max_e = rng.uniform(300, 1500)
            new_cell.cell_type = CellType.CARRION
            new_cell.energy = max_e
            new_cell.max_energy = max_e
