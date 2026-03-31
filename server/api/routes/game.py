"""Game routes — state, actions, scores, legal actions."""

from fastapi import APIRouter, Depends, HTTPException

from server.api.deps import get_current_player, get_manager
from server.api.game_manager import GameManager, PlayerInfo
from server.api.schemas import (
    ActionRequest,
    GameStateResponse,
    LegalActionsResponse,
    ReplayResponse,
    SpeciesScore,
    SubmitActionsRequest,
    SubmitActionsResponse,
)
from server.engine.models import Action, ActionType

router = APIRouter(prefix="/api/games/{game_id}", tags=["game"])


@router.get("/state", response_model=GameStateResponse)
def get_state(
    game_id: str,
    player: PlayerInfo = Depends(get_current_player),
    manager: GameManager = Depends(get_manager),
):
    state = manager.get_game_state(game_id, player.player_id)
    if not state:
        raise HTTPException(status_code=404, detail="Game not found or not a member")
    return state


@router.post("/actions", response_model=SubmitActionsResponse)
async def submit_actions(
    game_id: str,
    req: SubmitActionsRequest,
    player: PlayerInfo = Depends(get_current_player),
    manager: GameManager = Depends(get_manager),
):
    actions = [
        Action(
            dino_id=a.dino_id,
            action_type=a.action_type,
            target_x=a.target_x,
            target_y=a.target_y,
        )
        for a in req.actions
    ]

    try:
        errors = manager.submit_actions(game_id, player.player_id, actions)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Check if all players submitted
    await manager.check_all_submitted(game_id)

    return SubmitActionsResponse(
        accepted=len(actions) - len(errors),
        errors=errors,
    )


@router.get("/spectate", response_model=GameStateResponse)
def spectate(
    game_id: str,
    manager: GameManager = Depends(get_manager),
):
    """Full game state with no fog of war — no auth required."""
    state = manager.get_spectator_state(game_id)
    if not state:
        raise HTTPException(status_code=404, detail="Game not found")
    return state


@router.get("/scores", response_model=list[SpeciesScore])
def get_scores(
    game_id: str,
    manager: GameManager = Depends(get_manager),
):
    session = manager.games.get(game_id)
    if not session:
        raise HTTPException(status_code=404, detail="Game not found")
    return manager._build_scores(session)


@router.get("/legal-actions/{dino_id}", response_model=LegalActionsResponse)
def get_legal_actions(
    game_id: str,
    dino_id: str,
    player: PlayerInfo = Depends(get_current_player),
    manager: GameManager = Depends(get_manager),
):
    actions = manager.get_legal_actions(game_id, player.player_id, dino_id)
    return LegalActionsResponse(
        dino_id=dino_id,
        actions=[
            ActionRequest(
                dino_id=a.dino_id,
                action_type=a.action_type,
                target_x=a.target_x,
                target_y=a.target_y,
            )
            for a in actions
        ],
    )


@router.get("/replay", response_model=ReplayResponse)
def get_replay(
    game_id: str,
    manager: GameManager = Depends(get_manager),
):
    """Full game replay — map + per-turn snapshots. No auth required."""
    replay = manager.get_replay(game_id)
    if not replay:
        raise HTTPException(status_code=404, detail="Game not found")
    return replay
