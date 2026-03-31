"""Auth routes — simple token-based registration."""

from fastapi import APIRouter, Depends

from server.api.deps import get_manager
from server.api.game_manager import GameManager
from server.api.schemas import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse)
def register(
    req: RegisterRequest,
    manager: GameManager = Depends(get_manager),
):
    if not req.username.strip():
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Username cannot be empty")

    player = manager.register(req.username.strip())
    return RegisterResponse(player_id=player.player_id, token=player.token)


@router.post("/login", response_model=LoginResponse)
def login(
    req: LoginRequest,
    manager: GameManager = Depends(get_manager),
):
    # Login is same as register for this simple auth
    player = manager.register(req.username.strip())
    return LoginResponse(token=player.token, player_id=player.player_id)
