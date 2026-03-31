"""Bot client SDK for Dinosaur Island.

Usage:
    from server.sdk import BotClient

    bot = BotClient("http://localhost:8000")
    bot.register("my_bot")
    bot.join("GAME_ID", "MySpecies", "herbivore")

    while bot.is_active():
        state = bot.get_state()
        for dino in state["dinosaurs"]:
            if dino["is_mine"]:
                actions = bot.get_legal_actions(dino["id"])
                # Pick an action...
                bot.queue_action(dino["id"], "move", target_x=5, target_y=3)
        bot.submit()
        bot.wait_for_turn()
"""

from __future__ import annotations

import time

import httpx


class BotClient:
    """Simple synchronous client for writing Dinosaur Island bots."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.token: str | None = None
        self.player_id: str | None = None
        self.game_id: str | None = None
        self.species_id: str | None = None
        self._client = httpx.Client(base_url=self.base_url, timeout=30)
        self._queued_actions: list[dict] = []
        self._last_turn: int = -1

    # --- Auth ---

    def register(self, username: str) -> dict:
        """Register or login. Returns {player_id, token}."""
        resp = self._post("/api/auth/register", json={"username": username})
        self.token = resp["token"]
        self.player_id = resp["player_id"]
        return resp

    # --- Lobby ---

    def list_games(self) -> list[dict]:
        """List all games."""
        return self._get("/api/games")

    def create_game(self, **kwargs) -> dict:
        """Create a game. kwargs: width, height, max_turns, seed, turn_timeout."""
        return self._post("/api/games", json=kwargs)

    def join(self, game_id: str, species_name: str, diet: str) -> dict:
        """Join a game. diet: 'herbivore' or 'carnivore'. Returns {species_id, game_id}."""
        resp = self._post(
            f"/api/games/{game_id}/join",
            json={"species_name": species_name, "diet": diet},
        )
        self.game_id = resp["game_id"]
        self.species_id = resp["species_id"]
        return resp

    def start_game(self, game_id: str | None = None) -> dict:
        """Start a game (transitions from waiting to active)."""
        gid = game_id or self.game_id
        return self._post(f"/api/games/{gid}/start")

    # --- Game ---

    def get_state(self) -> dict:
        """Get the current game state (fog-of-war filtered for your species)."""
        resp = self._get(f"/api/games/{self.game_id}/state")
        self._last_turn = resp.get("turn", self._last_turn)
        return resp

    def get_scores(self) -> list[dict]:
        """Get the current scoreboard."""
        return self._get(f"/api/games/{self.game_id}/scores")

    def get_legal_actions(self, dino_id: str) -> list[dict]:
        """Get all legal actions for a dinosaur."""
        resp = self._get(f"/api/games/{self.game_id}/legal-actions/{dino_id}")
        return resp.get("actions", [])

    def is_active(self) -> bool:
        """Check if the game is still active."""
        state = self.get_state()
        return state.get("phase") == "active"

    # --- Actions ---

    def queue_action(
        self,
        dino_id: str,
        action_type: str,
        target_x: int | None = None,
        target_y: int | None = None,
    ) -> None:
        """Queue an action for a dinosaur. Call submit() to send all queued actions."""
        action: dict = {"dino_id": dino_id, "action_type": action_type}
        if target_x is not None:
            action["target_x"] = target_x
        if target_y is not None:
            action["target_y"] = target_y
        self._queued_actions.append(action)

    def submit(self) -> dict:
        """Submit all queued actions for this turn. Returns {accepted, errors}."""
        resp = self._post(
            f"/api/games/{self.game_id}/actions",
            json={"actions": self._queued_actions},
        )
        self._queued_actions.clear()
        return resp

    def wait_for_turn(self, poll_interval: float = 0.5, timeout: float = 60) -> dict:
        """Poll until the turn advances. Returns the new state."""
        start = time.time()
        while time.time() - start < timeout:
            state = self.get_state()
            current_turn = state.get("turn", 0)
            if current_turn > self._last_turn:
                self._last_turn = current_turn
                return state
            if state.get("phase") != "active":
                return state
            time.sleep(poll_interval)
        return self.get_state()

    # --- HTTP helpers ---

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _get(self, path: str) -> dict | list:
        resp = self._client.get(path, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, json: dict | None = None) -> dict:
        resp = self._client.post(path, json=json or {}, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
