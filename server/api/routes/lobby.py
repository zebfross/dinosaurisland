"""Lobby routes — create, list, join, and start games."""

from fastapi import APIRouter, Depends, HTTPException

from server.api.deps import get_current_player, get_manager
from server.api.game_manager import GameManager, PlayerInfo
from server.api.schemas import (
    CreateGameRequest,
    GameSummary,
    JoinGameRequest,
    JoinGameResponse,
)

router = APIRouter(prefix="/api/games", tags=["lobby"])


@router.post("", response_model=GameSummary)
def create_game(
    req: CreateGameRequest,
    player: PlayerInfo = Depends(get_current_player),
    manager: GameManager = Depends(get_manager),
):
    session = manager.create_game(
        width=req.width,
        height=req.height,
        max_turns=req.max_turns,
        seed=req.seed,
        turn_timeout=req.turn_timeout,
    )
    return GameSummary(
        game_id=session.game_id,
        phase=session.state.phase,
        turn=session.state.turn,
        max_turns=session.state.max_turns,
        player_count=0,
        species_names=[],
    )


@router.get("", response_model=list[GameSummary])
def list_games(
    manager: GameManager = Depends(get_manager),
):
    return manager.list_games()


@router.get("/{game_id}", response_model=GameSummary)
def get_game(
    game_id: str,
    manager: GameManager = Depends(get_manager),
):
    games = manager.list_games()
    for g in games:
        if g.game_id == game_id:
            return g
    raise HTTPException(status_code=404, detail="Game not found")


@router.post("/{game_id}/join", response_model=JoinGameResponse)
def join_game(
    game_id: str,
    req: JoinGameRequest,
    player: PlayerInfo = Depends(get_current_player),
    manager: GameManager = Depends(get_manager),
):
    try:
        species = manager.join_game(
            game_id, player.player_id, req.species_name, req.diet
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return JoinGameResponse(species_id=species.id, game_id=game_id)


@router.post("/{game_id}/start")
async def start_game(
    game_id: str,
    player: PlayerInfo = Depends(get_current_player),
    manager: GameManager = Depends(get_manager),
):
    try:
        manager.start_game(game_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Start turn timer
    await manager.start_turn_timer(game_id)

    return {"status": "started"}
