"""Action validation logic."""

from __future__ import annotations

from server.engine.constants import (
    CARNIVORE_MAX_STEPS,
    EGG_ENERGY_THRESHOLD,
    GROW_ENERGY_FRACTION,
    HERBIVORE_MAX_STEPS,
    MAX_DIMENSION,
    MAX_DINOS_PER_SPECIES,
)
from server.engine.models import (
    Action,
    ActionType,
    DietType,
    Dinosaur,
    GameState,
    InvalidActionError,
    Species,
)
from server.engine.movement import reachable_cells


def validate_action(
    state: GameState,
    species: Species,
    dino: Dinosaur,
    action: Action,
) -> None:
    """Validate an action. Raises InvalidActionError if illegal."""
    if not dino.alive:
        raise InvalidActionError(dino.id, action, "Dinosaur is dead")
    if dino.hatching:
        raise InvalidActionError(dino.id, action, "Dinosaur is still hatching")
    if dino.species_id != species.id:
        raise InvalidActionError(dino.id, action, "Dinosaur does not belong to species")

    if action.action_type == ActionType.MOVE:
        _validate_move(state, species, dino, action)
    elif action.action_type == ActionType.GROW:
        _validate_grow(dino, action)
    elif action.action_type == ActionType.LAY_EGG:
        _validate_lay_egg(species, dino, action)
    # REST is always valid


def _validate_move(
    state: GameState,
    species: Species,
    dino: Dinosaur,
    action: Action,
) -> None:
    if action.target_x is None or action.target_y is None:
        raise InvalidActionError(dino.id, action, "Move requires target coordinates")

    tx, ty = action.target_x, action.target_y

    if not state.game_map.in_bounds(tx, ty):
        raise InvalidActionError(dino.id, action, "Target out of bounds")

    if not state.game_map.is_passable(tx, ty):
        raise InvalidActionError(dino.id, action, "Target cell is water")

    max_steps = (
        CARNIVORE_MAX_STEPS
        if species.diet == DietType.CARNIVORE
        else HERBIVORE_MAX_STEPS
    )
    reachable = reachable_cells(state.game_map, dino.x, dino.y, max_steps)
    if (tx, ty) not in reachable:
        raise InvalidActionError(
            dino.id, action, f"Target not reachable within {max_steps} steps"
        )

    # Check for invalid collisions
    occupant = state.get_dino_at(tx, ty)
    if occupant and occupant.id != dino.id:
        occupant_species = state.get_species_for_dino(occupant.id)
        if occupant_species:
            # Can't attack your own species
            if occupant_species.id == species.id:
                raise InvalidActionError(
                    dino.id, action, "Cannot move onto your own species"
                )
            # Herbivores can't attack other herbivores
            if species.diet == DietType.HERBIVORE and occupant_species.diet == DietType.HERBIVORE:
                raise InvalidActionError(
                    dino.id, action, "Herbivores cannot move onto another herbivore"
                )


def _validate_grow(dino: Dinosaur, action: Action) -> None:
    if dino.dimension >= MAX_DIMENSION:
        raise InvalidActionError(dino.id, action, "Already at max dimension")

    new_max_energy = (dino.dimension + 1) * 1000
    cost = new_max_energy * GROW_ENERGY_FRACTION
    if dino.energy < cost:
        raise InvalidActionError(
            dino.id, action, f"Not enough energy to grow (need {cost}, have {dino.energy})"
        )


def _validate_lay_egg(species: Species, dino: Dinosaur, action: Action) -> None:
    if dino.energy < EGG_ENERGY_THRESHOLD:
        raise InvalidActionError(
            dino.id,
            action,
            f"Not enough energy to lay egg (need {EGG_ENERGY_THRESHOLD}, have {dino.energy})",
        )
    total = species.dino_count + len(species.eggs)
    if total >= MAX_DINOS_PER_SPECIES:
        raise InvalidActionError(
            dino.id,
            action,
            f"Species already at max dinosaurs ({MAX_DINOS_PER_SPECIES})",
        )
