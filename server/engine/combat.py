"""Combat resolution logic."""

from __future__ import annotations

from server.engine.constants import CARNIVORE_COMBAT_MULTIPLIER, COMBAT_ENERGY_ABSORPTION
from server.engine.models import CombatResult, DietType, Dinosaur


class IllegalCombatError(Exception):
    pass


def compute_combat_power(dino: Dinosaur, diet: DietType) -> float:
    """Power = dimension * energy, doubled for carnivores."""
    power = dino.dimension * dino.energy
    if diet == DietType.CARNIVORE:
        power *= CARNIVORE_COMBAT_MULTIPLIER
    return power


def resolve_combat(
    attacker: Dinosaur,
    attacker_diet: DietType,
    defender: Dinosaur,
    defender_diet: DietType,
) -> CombatResult:
    """Resolve combat between two dinosaurs.

    Rules:
    - Two herbivores cannot fight (raises IllegalCombatError)
    - Power = dimension * energy (* 2 for carnivores)
    - Higher power wins. On tie, attacker wins.
    - If winner is carnivore, absorbs 75% of loser's energy (capped at max).
    - Loser dies.
    """
    if attacker_diet == DietType.HERBIVORE and defender_diet == DietType.HERBIVORE:
        raise IllegalCombatError("Two herbivores cannot fight each other")

    attacker_power = compute_combat_power(attacker, attacker_diet)
    defender_power = compute_combat_power(defender, defender_diet)

    if attacker_power >= defender_power:
        winner, loser = attacker, defender
        winner_diet = attacker_diet
    else:
        winner, loser = defender, attacker
        winner_diet = defender_diet

    energy_transferred = 0.0
    if winner_diet == DietType.CARNIVORE:
        available = loser.energy * COMBAT_ENERGY_ABSORPTION
        can_absorb = min(available, winner.max_energy - winner.energy)
        winner.energy += can_absorb
        energy_transferred = can_absorb

    loser.alive = False

    return CombatResult(
        attacker_id=attacker.id,
        defender_id=defender.id,
        attacker_power=attacker_power,
        defender_power=defender_power,
        winner_id=winner.id,
        loser_id=loser.id,
        energy_transferred=energy_transferred,
    )
