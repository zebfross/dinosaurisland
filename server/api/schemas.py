"""Pydantic request/response schemas for the API layer."""

from __future__ import annotations

from pydantic import BaseModel, Field

from server.engine.models import ActionType, DietType, GamePhase


# --- Auth ---

class RegisterRequest(BaseModel):
    username: str


class RegisterResponse(BaseModel):
    player_id: str
    token: str


class LoginRequest(BaseModel):
    username: str


class LoginResponse(BaseModel):
    token: str
    player_id: str


# --- Lobby ---

class CreateGameRequest(BaseModel):
    width: int = 30
    height: int = 30
    max_turns: int = 120
    seed: int | None = None
    turn_timeout: int = 30  # seconds per turn


class GameSummary(BaseModel):
    game_id: str
    phase: GamePhase
    turn: int
    max_turns: int
    player_count: int
    species_names: list[str]


class JoinGameRequest(BaseModel):
    species_name: str
    diet: DietType


class JoinGameResponse(BaseModel):
    species_id: str
    game_id: str


# --- Game actions ---

class ActionRequest(BaseModel):
    dino_id: str
    action_type: ActionType
    target_x: int | None = None
    target_y: int | None = None


class SubmitActionsRequest(BaseModel):
    actions: list[ActionRequest]


class ActionError(BaseModel):
    dino_id: str
    reason: str


class SubmitActionsResponse(BaseModel):
    accepted: int
    errors: list[ActionError]


# --- Game state ---

class CellResponse(BaseModel):
    x: int
    y: int
    cell_type: str
    energy: float
    max_energy: float


class DinoResponse(BaseModel):
    id: str
    species_id: str
    species_name: str
    diet: str
    x: int
    y: int
    dimension: int
    energy: float
    max_energy: float
    age: int
    max_lifespan: int
    is_mine: bool


class EggResponse(BaseModel):
    x: int
    y: int
    hatch_turn: int
    is_mine: bool


class SpeciesScore(BaseModel):
    species_id: str
    name: str
    diet: str
    score: int
    dino_count: int


class GameStateResponse(BaseModel):
    game_id: str
    turn: int
    max_turns: int
    phase: GamePhase
    visible_cells: list[CellResponse]
    dinosaurs: list[DinoResponse]
    eggs: list[EggResponse]
    scores: list[SpeciesScore]


class LegalActionsResponse(BaseModel):
    dino_id: str
    actions: list[ActionRequest]


# --- Replay ---

class ReplayFrame(BaseModel):
    turn: int
    phase: GamePhase
    dinosaurs: list[DinoResponse]
    eggs: list[EggResponse]
    scores: list[SpeciesScore]
    combats: int = 0
    deaths: int = 0
    hatches: int = 0


class ReplayResponse(BaseModel):
    game_id: str
    max_turns: int
    map_width: int
    map_height: int
    cells: list[CellResponse]  # full map (static terrain — sent once)
    frames: list[ReplayFrame]  # one per turn


# --- WebSocket messages ---

class WsTurnStart(BaseModel):
    type: str = "turn_start"
    turn: int
    deadline_seconds: int


class WsStateUpdate(BaseModel):
    type: str = "state_update"
    state: GameStateResponse


class WsTurnResult(BaseModel):
    type: str = "turn_result"
    turn: int
    combats: int
    deaths: int
    hatches: int
    scores: list[SpeciesScore]


class WsPhaseChange(BaseModel):
    type: str = "phase_change"
    phase: GamePhase
    final_scores: list[SpeciesScore]


class WsError(BaseModel):
    type: str = "error"
    message: str
