"""Passenger WSGI entry point for A2 Hosting (LiteSpeed + Passenger).

Uses Flask as a native WSGI wrapper around the game engine.
The a2wsgi ASGI adapter hangs on LiteSpeed, so we use Flask directly.
"""

import os
import sys
import json

project_root = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, project_root)

from flask import Flask, send_from_directory, jsonify, request
from pathlib import Path

from server.engine.game import GameEngine
from server.engine.models import DietType, GamePhase, Action, ActionType
from server.api.game_manager import GameManager

CLIENT_DIST = Path(project_root) / "client" / "dist"

app = Flask(__name__, static_folder=str(CLIENT_DIST / "assets"), static_url_path="/assets")

manager = GameManager()


# --- API ---

@app.route("/api/health")
def health():
    return jsonify(status="ok")


@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json()
    username = (data or {}).get("username", "").strip()
    if not username:
        return jsonify(detail="Username cannot be empty"), 400
    player = manager.register(username)
    return jsonify(player_id=player.player_id, token=player.token)


@app.route("/api/games", methods=["GET"])
def list_games():
    return jsonify([g.model_dump() for g in manager.list_games()])


@app.route("/api/games", methods=["POST"])
def create_game():
    data = request.get_json() or {}
    player = _get_player()
    if not player:
        return jsonify(detail="Unauthorized"), 401
    session = manager.create_game(
        width=data.get("width", 30), height=data.get("height", 30),
        max_turns=data.get("max_turns", 120), seed=data.get("seed"),
        turn_timeout=data.get("turn_timeout", 30),
    )
    for g in manager.list_games():
        if g.game_id == session.game_id:
            return jsonify(g.model_dump())
    return jsonify(game_id=session.game_id)


@app.route("/api/games/<game_id>", methods=["GET"])
def get_game(game_id):
    for g in manager.list_games():
        if g.game_id == game_id:
            return jsonify(g.model_dump())
    return jsonify(detail="Game not found"), 404


@app.route("/api/games/<game_id>/join", methods=["POST"])
def join_game(game_id):
    player = _get_player()
    if not player:
        return jsonify(detail="Unauthorized"), 401
    data = request.get_json() or {}
    try:
        species = manager.join_game(
            game_id, player.player_id,
            data.get("species_name", "Bot"), DietType(data.get("diet", "herbivore")),
        )
    except ValueError as e:
        return jsonify(detail=str(e)), 400
    return jsonify(species_id=species.id, game_id=game_id)


@app.route("/api/games/<game_id>/start", methods=["POST"])
def start_game(game_id):
    try:
        manager.start_game(game_id)
    except ValueError as e:
        return jsonify(detail=str(e)), 400
    return jsonify(status="started")


@app.route("/api/games/<game_id>/state", methods=["GET"])
def get_state(game_id):
    player = _get_player()
    if not player:
        return jsonify(detail="Unauthorized"), 401
    state = manager.get_game_state(game_id, player.player_id)
    if not state:
        return jsonify(detail="Not found"), 404
    return jsonify(state.model_dump())


@app.route("/api/games/<game_id>/spectate", methods=["GET"])
def spectate(game_id):
    state = manager.get_spectator_state(game_id)
    if not state:
        return jsonify(detail="Not found"), 404
    return jsonify(state.model_dump())


@app.route("/api/games/<game_id>/actions", methods=["POST"])
def submit_actions(game_id):
    player = _get_player()
    if not player:
        return jsonify(detail="Unauthorized"), 401
    data = request.get_json() or {}
    actions = [
        Action(dino_id=a["dino_id"], action_type=ActionType(a["action_type"]),
               target_x=a.get("target_x"), target_y=a.get("target_y"))
        for a in data.get("actions", [])
    ]
    try:
        errors = manager.submit_actions(game_id, player.player_id, actions)
    except ValueError as e:
        return jsonify(detail=str(e)), 400
    _check_and_process(game_id)
    return jsonify(accepted=len(actions) - len(errors),
                   errors=[e.model_dump() for e in errors])


@app.route("/api/games/<game_id>/scores", methods=["GET"])
def get_scores(game_id):
    session = manager.games.get(game_id)
    if not session:
        return jsonify(detail="Not found"), 404
    return jsonify([s.model_dump() for s in manager._build_scores(session)])


@app.route("/api/games/<game_id>/legal-actions/<dino_id>", methods=["GET"])
def get_legal_actions(game_id, dino_id):
    player = _get_player()
    if not player:
        return jsonify(detail="Unauthorized"), 401
    actions = manager.get_legal_actions(game_id, player.player_id, dino_id)
    return jsonify(dino_id=dino_id, actions=[
        dict(dino_id=a.dino_id, action_type=a.action_type.value,
             target_x=a.target_x, target_y=a.target_y)
        for a in actions
    ])


@app.route("/api/games/<game_id>/replay", methods=["GET"])
def get_replay(game_id):
    replay = manager.get_replay(game_id)
    if not replay:
        return jsonify(detail="Not found"), 404
    return jsonify(replay.model_dump())


# --- Frontend ---

@app.route("/")
@app.route("/<path:path>")
def serve_frontend(path=""):
    if path and (CLIENT_DIST / path).is_file():
        return send_from_directory(str(CLIENT_DIST), path)
    return send_from_directory(str(CLIENT_DIST), "index.html")


# --- Helpers ---

def _get_player():
    auth = request.headers.get("Authorization", "")
    token = auth.removeprefix("Bearer ").strip()
    return manager.get_player(token) if token else None


def _check_and_process(game_id):
    session = manager.games.get(game_id)
    if not session or session.state.phase != GamePhase.ACTIVE:
        return
    active = {sid for sid, sp in session.state.species.items() if sp.dino_count > 0}
    if active and active <= session.submitted:
        _do_process_turn(session)


def _do_process_turn(session):
    if session._processing_turn:
        return
    session._processing_turn = True
    try:
        result = session.engine.process_turn(session.state)
        # Persistent games never end
        if session.persistent and session.state.phase == GamePhase.FINISHED:
            session.state.phase = GamePhase.ACTIVE
        session.replay_frames.append(manager._build_replay_frame(session, result))
        if len(session.replay_frames) > 500:
            session.replay_frames = session.replay_frames[-500:]
        if session.state.phase != GamePhase.FINISHED:
            session.submitted.clear()
    finally:
        session._processing_turn = False


# --- Persistent game timer (background thread) ---

import threading
import time

def _persistent_timer():
    """Process turns on a timer for the persistent game."""
    while True:
        time.sleep(10)  # 10 second turns
        session = manager.get_persistent_game()
        if session and session.state.phase == GamePhase.ACTIVE:
            # Only process if there are living dinos
            has_dinos = any(sp.dino_count > 0 for sp in session.state.species.values())
            if has_dinos:
                _do_process_turn(session)


# Create persistent game on startup
persistent = manager.ensure_persistent_game()

# Start timer thread
_timer_thread = threading.Thread(target=_persistent_timer, daemon=True)
_timer_thread.start()

application = app
