"""WebSocket endpoint for real-time game updates."""

from __future__ import annotations

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from server.api.deps import get_manager
from server.api.schemas import WsError
from server.engine.models import Action, ActionType

router = APIRouter()


@router.websocket("/ws/games/{game_id}")
async def game_websocket(websocket: WebSocket, game_id: str, token: str = ""):
    manager = get_manager()
    player = manager.get_player(token)

    if not player:
        await websocket.close(code=4001, reason="Invalid token")
        return

    session = manager.games.get(game_id)
    if not session:
        await websocket.close(code=4004, reason="Game not found")
        return

    if player.player_id not in session.player_to_species:
        await websocket.close(code=4003, reason="Not a member of this game")
        return

    await websocket.accept()
    manager.subscribe(game_id, player.player_id, websocket)

    # Send initial state
    state = manager.get_game_state(game_id, player.player_id)
    if state:
        await websocket.send_json({
            "type": "state_update",
            "state": state.model_dump(),
        })

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json(
                    WsError(message="Invalid JSON").model_dump()
                )
                continue

            msg_type = data.get("type", "")

            if msg_type == "submit_actions":
                raw_actions = data.get("actions", [])
                actions = []
                for a in raw_actions:
                    actions.append(Action(
                        dino_id=a["dino_id"],
                        action_type=ActionType(a["action_type"]),
                        target_x=a.get("target_x"),
                        target_y=a.get("target_y"),
                    ))

                try:
                    errors = manager.submit_actions(
                        game_id, player.player_id, actions
                    )
                    await websocket.send_json({
                        "type": "actions_accepted",
                        "accepted": len(actions) - len(errors),
                        "errors": [e.model_dump() for e in errors],
                    })
                    # Check if all submitted
                    await manager.check_all_submitted(game_id)
                except ValueError as e:
                    await websocket.send_json(
                        WsError(message=str(e)).model_dump()
                    )

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            else:
                await websocket.send_json(
                    WsError(message=f"Unknown message type: {msg_type}").model_dump()
                )

    except WebSocketDisconnect:
        pass
    finally:
        manager.unsubscribe(game_id, player.player_id, websocket)


@router.websocket("/ws/spectate/{game_id}")
async def spectator_websocket(websocket: WebSocket, game_id: str):
    """Spectator WebSocket — no auth, full map view, read-only."""
    manager = get_manager()

    session = manager.games.get(game_id)
    if not session:
        await websocket.close(code=4004, reason="Game not found")
        return

    await websocket.accept()
    manager.subscribe_spectator(game_id, websocket)

    # Send initial full state
    state = manager.get_spectator_state(game_id)
    if state:
        await websocket.send_json({
            "type": "state_update",
            "state": state.model_dump(),
        })

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type", "")
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
            # Spectators can't submit actions — ignore everything else

    except WebSocketDisconnect:
        pass
    finally:
        manager.unsubscribe_spectator(game_id, websocket)
