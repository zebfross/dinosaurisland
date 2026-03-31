"""FastAPI dependency injection."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException

from server.api.game_manager import GameManager, PlayerInfo

# Singleton game manager — set during app creation
_manager: GameManager | None = None


def set_game_manager(manager: GameManager) -> None:
    global _manager
    _manager = manager


def get_manager() -> GameManager:
    if _manager is None:
        raise RuntimeError("GameManager not initialized")
    return _manager


def get_current_player(
    authorization: str = Header(..., description="Bearer token"),
    manager: GameManager = Depends(get_manager),
) -> PlayerInfo:
    token = authorization.removeprefix("Bearer ").strip()
    player = manager.get_player(token)
    if not player:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return player
