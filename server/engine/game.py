"""GameEngine — the core orchestrator for Dinosaur Island."""

from __future__ import annotations

import random

from server.engine.combat import IllegalCombatError, resolve_combat
from server.engine.constants import (
    CARNIVORE_MAX_STEPS,
    DEFAULT_GRID_HEIGHT,
    DEFAULT_GRID_WIDTH,
    DINO_MAX_LIFESPAN,
    DINO_MIN_LIFESPAN,
    EGG_ENERGY_THRESHOLD,
    ENERGY_PER_DIMENSION,
    GROW_ENERGY_FRACTION,
    HERBIVORE_MAX_STEPS,
    MAX_DINOS_PER_SPECIES,
    MAX_SPECIES_TURNS,
    STARTING_DIMENSION,
    STARTING_ENERGY,
)
from server.engine.feeding import decay_carrion, feed_dinosaur, regenerate_vegetation
from server.engine.mapgen.base import MapGenerator
from server.engine.mapgen.simple import SimpleMapGenerator
from server.engine.models import (
    Action,
    ActionType,
    CellType,
    CombatResult,
    DietType,
    Dinosaur,
    Egg,
    GamePhase,
    GameState,
    InvalidActionError,
    Species,
    TurnActions,
    TurnResult,
)
from server.engine.movement import movement_cost, reachable_cells
from server.engine.scoring import calculate_turn_score
from server.engine.validation import validate_action
from server.engine.vision import update_fog_of_war


class GameEngine:
    """Pure game logic. No I/O. All randomness via injected RNG."""

    def __init__(self, rng: random.Random | None = None):
        self.rng = rng or random.Random()

    # --- Game lifecycle ---

    def create_game(
        self,
        width: int = DEFAULT_GRID_WIDTH,
        height: int = DEFAULT_GRID_HEIGHT,
        map_generator: MapGenerator | None = None,
        max_turns: int = MAX_SPECIES_TURNS,
    ) -> GameState:
        gen = map_generator or SimpleMapGenerator()
        game_map = gen.generate(width, height, self.rng)
        return GameState(game_map=game_map, max_turns=max_turns)

    def add_species(
        self,
        state: GameState,
        player_id: str,
        name: str,
        diet: DietType,
    ) -> Species:
        """Add a species and spawn its first dinosaur at a random passable cell."""
        spawn = self._find_spawn_point(state)
        species = Species(
            player_id=player_id,
            name=name,
            diet=diet,
            birth_turn=state.turn,
        )
        dino = Dinosaur(
            species_id=species.id,
            x=spawn[0],
            y=spawn[1],
            dimension=STARTING_DIMENSION,
            energy=STARTING_ENERGY,
            max_lifespan=self.rng.randint(DINO_MIN_LIFESPAN, DINO_MAX_LIFESPAN),
        )
        species.dinosaurs.append(dino)
        state.species[species.id] = species

        # Initial fog of war reveal
        update_fog_of_war(species, state.game_map)

        return species

    def start_game(self, state: GameState) -> None:
        """Transition from WAITING to ACTIVE."""
        if not state.species:
            raise ValueError("Cannot start game with no species")
        state.phase = GamePhase.ACTIVE

    # --- Action submission ---

    def submit_actions(
        self,
        state: GameState,
        turn_actions: TurnActions,
    ) -> list[InvalidActionError]:
        """Buffer actions for a species. Returns list of validation errors (empty if all valid)."""
        species = state.species.get(turn_actions.species_id)
        if not species:
            raise ValueError(f"Unknown species {turn_actions.species_id}")

        errors: list[InvalidActionError] = []
        valid_actions: list[Action] = []

        for action in turn_actions.actions:
            dino = state.get_dino(action.dino_id)
            if not dino:
                errors.append(
                    InvalidActionError(action.dino_id, action, "Dinosaur not found")
                )
                continue
            try:
                validate_action(state, species, dino, action)
                valid_actions.append(action)
            except InvalidActionError as e:
                errors.append(e)

        state.pending_actions[species.id] = TurnActions(
            species_id=species.id, actions=valid_actions
        )
        return errors

    # --- Turn processing ---

    def process_turn(self, state: GameState) -> TurnResult:
        """Advance the game by one turn.

        Order:
        1. Hatch pending eggs
        2. Execute actions (move, grow, lay_egg, rest)
        3. Resolve combats from movement
        4. Auto-feed all dinos
        5. Age dinos, kill expired ones
        6. Regenerate vegetation, decay carrion
        7. Update fog of war
        8. Calculate scores
        9. Check end-game conditions
        """
        state.turn += 1
        result = TurnResult(turn_number=state.turn)

        # 1. Hatch pending eggs
        self._hatch_eggs(state, result)

        # 2 & 3. Execute actions and resolve combats
        self._execute_actions(state, result)

        # 4. Auto-feed all dinos
        self._auto_feed(state)

        # 5. Age dinos, kill expired
        self._age_dinos(state, result)

        # 6. Map regeneration
        regenerate_vegetation(state.game_map)
        decay_carrion(state.game_map, self.rng)

        # 7. Update fog of war
        for species in state.species.values():
            update_fog_of_war(species, state.game_map)

        # 8. Calculate scores
        for species in state.species.values():
            delta = calculate_turn_score(species)
            species.score += delta
            result.score_deltas[species.id] = delta

        # 9. Check end-game
        self._check_end_game(state)

        # Clear pending actions
        state.pending_actions.clear()

        # Record history
        state.turn_results.append(result)

        return result

    # --- Queries ---

    def get_visible_state(
        self,
        state: GameState,
        species_id: str,
    ) -> dict:
        """Return game state filtered through this species' fog of war."""
        species = state.species.get(species_id)
        if not species:
            raise ValueError(f"Unknown species {species_id}")

        revealed = species.revealed_set

        # Build visible cells
        visible_cells = []
        for y in range(state.game_map.height):
            for x in range(state.game_map.width):
                if (x, y) in revealed:
                    cell = state.game_map.get_cell(x, y)
                    visible_cells.append(cell.model_dump())

        # Visible dinos (own + enemies in revealed cells)
        visible_dinos = []
        for sp in state.species.values():
            for d in sp.alive_dinos:
                if (d.x, d.y) in revealed:
                    visible_dinos.append(
                        {**d.model_dump(), "diet": sp.diet.value, "species_name": sp.name}
                    )

        return {
            "turn": state.turn,
            "phase": state.phase.value,
            "visible_cells": visible_cells,
            "visible_dinos": visible_dinos,
            "my_species": species.model_dump(),
            "scores": {sid: s.score for sid, s in state.species.items()},
        }

    def get_legal_actions(self, state: GameState, dino_id: str) -> list[Action]:
        """Return all legal actions for a dinosaur."""
        dino = state.get_dino(dino_id)
        if not dino or not dino.alive or dino.hatching:
            return []

        species = state.get_species_for_dino(dino_id)
        if not species:
            return []

        actions: list[Action] = []

        # REST is always legal
        actions.append(Action(dino_id=dino_id, action_type=ActionType.REST))

        # MOVE: all reachable cells
        max_steps = (
            CARNIVORE_MAX_STEPS
            if species.diet == DietType.CARNIVORE
            else HERBIVORE_MAX_STEPS
        )
        reachable = reachable_cells(state.game_map, dino.x, dino.y, max_steps)
        for (rx, ry), _steps in reachable.items():
            action = Action(
                dino_id=dino_id, action_type=ActionType.MOVE, target_x=rx, target_y=ry
            )
            try:
                validate_action(state, species, dino, action)
                actions.append(action)
            except InvalidActionError:
                pass

        # GROW
        grow_action = Action(dino_id=dino_id, action_type=ActionType.GROW)
        try:
            validate_action(state, species, dino, grow_action)
            actions.append(grow_action)
        except InvalidActionError:
            pass

        # LAY_EGG
        egg_action = Action(dino_id=dino_id, action_type=ActionType.LAY_EGG)
        try:
            validate_action(state, species, dino, egg_action)
            actions.append(egg_action)
        except InvalidActionError:
            pass

        return actions

    # --- Private helpers ---

    def _find_spawn_point(self, state: GameState) -> tuple[int, int]:
        """Find a random passable cell not occupied by another dino."""
        gm = state.game_map
        candidates = [
            (x, y)
            for y in range(gm.height)
            for x in range(gm.width)
            if gm.is_passable(x, y) and state.get_dino_at(x, y) is None
        ]
        if not candidates:
            raise ValueError("No available spawn points on map")
        return self.rng.choice(candidates)

    def _hatch_eggs(self, state: GameState, result: TurnResult) -> None:
        """Hatch eggs that are ready this turn."""
        for species in state.species.values():
            hatched = [e for e in species.eggs if e.hatch_turn <= state.turn]
            for egg in hatched:
                species.eggs.remove(egg)
                dino = Dinosaur(
                    species_id=species.id,
                    x=egg.x,
                    y=egg.y,
                    dimension=STARTING_DIMENSION,
                    energy=STARTING_ENERGY,
                    max_lifespan=self.rng.randint(DINO_MIN_LIFESPAN, DINO_MAX_LIFESPAN),
                )
                species.dinosaurs.append(dino)
                result.hatches.append(dino.id)

    def _execute_actions(self, state: GameState, result: TurnResult) -> None:
        """Execute all buffered actions. Movements that collide trigger combat."""
        combats_to_resolve: list[tuple[Dinosaur, Species, Dinosaur, Species]] = []

        for species_id, turn_actions in state.pending_actions.items():
            species = state.species[species_id]
            for action in turn_actions.actions:
                dino = state.get_dino(action.dino_id)
                if not dino or not dino.alive:
                    continue

                if action.action_type == ActionType.MOVE:
                    self._execute_move(state, species, dino, action, combats_to_resolve, result)
                elif action.action_type == ActionType.GROW:
                    self._execute_grow(dino, state, result)
                elif action.action_type == ActionType.LAY_EGG:
                    self._execute_lay_egg(state, species, dino)
                # REST: do nothing

        # Resolve all combats
        for attacker, att_species, defender, def_species in combats_to_resolve:
            if not attacker.alive or not defender.alive:
                continue  # already died in an earlier combat this turn
            try:
                combat_result = resolve_combat(
                    attacker, att_species.diet, defender, def_species.diet
                )
                result.combats.append(combat_result)
                result.deaths.append(combat_result.loser_id)
                result.death_causes[combat_result.loser_id] = "combat"
                # Loser leaves carrion (unless winner already ate most of it)
                loser = attacker if combat_result.loser_id == attacker.id else defender
                leftover = loser.dimension * 200 - combat_result.energy_transferred
                if leftover > 50:
                    self._spawn_carrion(state, loser.x, loser.y, leftover)
            except IllegalCombatError:
                pass  # shouldn't happen if validation is correct

    def _execute_move(
        self,
        state: GameState,
        species: Species,
        dino: Dinosaur,
        action: Action,
        combats: list[tuple[Dinosaur, Species, Dinosaur, Species]],
        result: TurnResult | None = None,
    ) -> None:
        tx, ty = action.target_x, action.target_y
        assert tx is not None and ty is not None

        # Calculate step count for cost
        max_steps = (
            CARNIVORE_MAX_STEPS
            if species.diet == DietType.CARNIVORE
            else HERBIVORE_MAX_STEPS
        )
        reachable = reachable_cells(state.game_map, dino.x, dino.y, max_steps)
        steps = reachable.get((tx, ty))
        if steps is None:
            return  # unreachable, skip

        cost = movement_cost(steps)
        if dino.energy < cost:
            dino.alive = False
            self._spawn_carrion(state, dino.x, dino.y, dino.dimension * 200)
            if result:
                result.deaths.append(dino.id)
                result.death_causes[dino.id] = "starvation"
            return

        dino.energy -= cost

        # Check for occupant at target
        occupant = state.get_dino_at(tx, ty)
        if occupant and occupant.id != dino.id and occupant.alive:
            occ_species = state.get_species_for_dino(occupant.id)
            if occ_species:
                # Move to the cell (combat will resolve after all moves)
                dino.x = tx
                dino.y = ty
                combats.append((dino, species, occupant, occ_species))
                return

        dino.x = tx
        dino.y = ty

    def _execute_grow(self, dino: Dinosaur, state: GameState | None = None, result: TurnResult | None = None) -> None:
        new_dim = dino.dimension + 1
        new_max = new_dim * ENERGY_PER_DIMENSION
        cost = new_max * GROW_ENERGY_FRACTION
        if dino.energy < cost:
            dino.alive = False
            if state:
                self._spawn_carrion(state, dino.x, dino.y, dino.dimension * 200)
            if result:
                result.deaths.append(dino.id)
                result.death_causes[dino.id] = "failed growth"
            return
        dino.energy -= cost
        dino.dimension = new_dim

    def _execute_lay_egg(
        self, state: GameState, species: Species, dino: Dinosaur
    ) -> None:
        if dino.energy < EGG_ENERGY_THRESHOLD:
            return
        if species.dino_count + len(species.eggs) >= MAX_DINOS_PER_SPECIES:
            return

        dino.energy -= EGG_ENERGY_THRESHOLD
        egg = Egg(
            species_id=species.id,
            x=dino.x,
            y=dino.y,
            hatch_turn=state.turn + 1,
        )
        species.eggs.append(egg)

    def _spawn_carrion(self, state: GameState, x: int, y: int, energy: float) -> None:
        """Convert a cell to carrion at a dino's death location."""
        cell = state.game_map.get_cell(x, y)
        if cell.cell_type == CellType.WATER:
            return  # can't place carrion on water
        cell.cell_type = CellType.CARRION
        cell.energy = min(cell.energy + energy, max(cell.max_energy, energy))
        cell.max_energy = max(cell.max_energy, energy)

    def _auto_feed(self, state: GameState) -> None:
        """All alive dinos auto-eat from their current cell."""
        for species in state.species.values():
            for dino in species.alive_dinos:
                cell = state.game_map.get_cell(dino.x, dino.y)
                feed_dinosaur(dino, cell, species.diet)

    def _age_dinos(self, state: GameState, result: TurnResult) -> None:
        """Age all dinos by 1 turn. Kill those past their lifespan."""
        for species in state.species.values():
            for dino in species.alive_dinos:
                dino.age += 1
                if dino.age >= dino.max_lifespan:
                    dino.alive = False
                    result.deaths.append(dino.id)
                    result.death_causes[dino.id] = "old age"
                    self._spawn_carrion(state, dino.x, dino.y, dino.dimension * 200)

    def _check_end_game(self, state: GameState) -> None:
        """End game if max turns reached or all species have no living dinos/eggs."""
        if state.turn >= state.max_turns:
            state.phase = GamePhase.FINISHED
            return

        all_dead = all(
            sp.dino_count == 0 and len(sp.eggs) == 0
            for sp in state.species.values()
        )
        if all_dead:
            state.phase = GamePhase.FINISHED
