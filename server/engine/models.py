"""Core data models for the Dinosaur Island game engine."""

from __future__ import annotations

import enum
import uuid
from typing import Any

from pydantic import BaseModel, Field

from server.engine.constants import ENERGY_PER_DIMENSION, VISION_RANGE


class CellType(str, enum.Enum):
    WATER = "water"
    PLAIN = "plain"
    VEGETATION = "vegetation"
    CARRION = "carrion"


class DietType(str, enum.Enum):
    HERBIVORE = "herbivore"
    CARNIVORE = "carnivore"


class ActionType(str, enum.Enum):
    MOVE = "move"
    GROW = "grow"
    LAY_EGG = "lay_egg"
    REST = "rest"


class Cell(BaseModel):
    x: int
    y: int
    cell_type: CellType
    energy: float = 0.0
    max_energy: float = 0.0


class GameMap(BaseModel):
    width: int
    height: int
    cells: list[list[Cell]]  # cells[y][x] — row-major

    def get_cell(self, x: int, y: int) -> Cell:
        return self.cells[y][x]

    def set_cell(self, x: int, y: int, cell: Cell) -> None:
        self.cells[y][x] = cell

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def is_passable(self, x: int, y: int) -> bool:
        return self.in_bounds(x, y) and self.cells[y][x].cell_type != CellType.WATER


class Dinosaur(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    species_id: str
    x: int
    y: int
    dimension: int = 1
    energy: float = 750.0
    max_lifespan: int = 30
    age: int = 0
    alive: bool = True
    hatching: bool = False  # True during the turn the egg was laid

    @property
    def max_energy(self) -> float:
        return self.dimension * ENERGY_PER_DIMENSION

    @property
    def vision_range(self) -> int:
        return VISION_RANGE[self.dimension]


class Egg(BaseModel):
    species_id: str
    x: int
    y: int
    hatch_turn: int  # the turn number when this egg hatches


class Species(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    player_id: str
    name: str
    diet: DietType
    dinosaurs: list[Dinosaur] = Field(default_factory=list)
    eggs: list[Egg] = Field(default_factory=list)
    score: int = 0
    birth_turn: int = 0
    # Fog of war: stored as list of [x, y] pairs, converted to set for lookups
    revealed_cells: list[list[int]] = Field(default_factory=list)

    @property
    def revealed_set(self) -> set[tuple[int, int]]:
        return {(c[0], c[1]) for c in self.revealed_cells}

    def reveal(self, cells: set[tuple[int, int]]) -> None:
        existing = self.revealed_set
        for c in cells:
            if c not in existing:
                self.revealed_cells.append([c[0], c[1]])

    @property
    def alive_dinos(self) -> list[Dinosaur]:
        return [d for d in self.dinosaurs if d.alive and not d.hatching]

    @property
    def dino_count(self) -> int:
        return len(self.alive_dinos)


class Action(BaseModel):
    dino_id: str
    action_type: ActionType
    target_x: int | None = None
    target_y: int | None = None


class TurnActions(BaseModel):
    species_id: str
    actions: list[Action]


class CombatResult(BaseModel):
    attacker_id: str
    defender_id: str
    attacker_power: float
    defender_power: float
    winner_id: str
    loser_id: str
    energy_transferred: float


class TurnResult(BaseModel):
    turn_number: int
    combats: list[CombatResult] = Field(default_factory=list)
    deaths: list[str] = Field(default_factory=list)
    death_causes: dict[str, str] = Field(default_factory=dict)  # dino_id -> cause
    hatches: list[str] = Field(default_factory=list)
    score_deltas: dict[str, int] = Field(default_factory=dict)


class GamePhase(str, enum.Enum):
    WAITING = "waiting"
    ACTIVE = "active"
    FINISHED = "finished"


class GameState(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    game_map: GameMap
    species: dict[str, Species] = Field(default_factory=dict)
    turn: int = 0
    phase: GamePhase = GamePhase.WAITING
    max_turns: int = 120
    turn_results: list[TurnResult] = Field(default_factory=list)
    pending_actions: dict[str, TurnActions] = Field(default_factory=dict)

    def get_dino(self, dino_id: str) -> Dinosaur | None:
        for sp in self.species.values():
            for d in sp.dinosaurs:
                if d.id == dino_id:
                    return d
        return None

    def get_species_for_dino(self, dino_id: str) -> Species | None:
        for sp in self.species.values():
            for d in sp.dinosaurs:
                if d.id == dino_id:
                    return sp
        return None

    def get_dino_at(self, x: int, y: int) -> Dinosaur | None:
        for sp in self.species.values():
            for d in sp.alive_dinos:
                if d.x == x and d.y == y:
                    return d
        return None


class InvalidActionError(Exception):
    def __init__(self, dino_id: str, action: Action, reason: str):
        self.dino_id = dino_id
        self.action = action
        self.reason = reason
        super().__init__(f"Invalid action for dino {dino_id}: {reason}")
