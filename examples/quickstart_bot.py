#!/usr/bin/env python3
"""Dinosaur Island — Quickstart Bot

A self-contained bot that connects to the persistent arena and plays
using a simple greedy strategy. No dependencies beyond Python 3.

Usage:
    python quickstart_bot.py
    python quickstart_bot.py --server https://inceptify.com/dinosaurisland
    python quickstart_bot.py --name MyBot --diet carnivore
"""

import argparse
import json
import random
import time
import urllib.request
import urllib.error

# --- HTTP helpers (no external deps) ---

class API:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")
        self.token = None

    def _req(self, method, path, data=None):
        url = f"{self.base_url}{path}"
        body = json.dumps(data).encode() if data else None
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = json.loads(e.read()) if e.headers.get("content-type", "").startswith("application/json") else {}
            raise RuntimeError(f"HTTP {e.code}: {body.get('detail', e.reason)}")

    def get(self, path): return self._req("GET", path)
    def post(self, path, data=None): return self._req("POST", path, data)


# --- Bot logic ---

def find_food_move(state, dino, legal_actions, diet):
    """Pick the move that gets closest to food."""
    food_type = "vegetation" if diet == "herbivore" else "carrion"
    food = [(c["x"], c["y"]) for c in state["visible_cells"]
            if c["cell_type"] == food_type and c["energy"] > 0]
    moves = [a for a in legal_actions if a["action_type"] == "move"]
    if not food or not moves:
        return None
    return min(moves, key=lambda m: min(
        abs(m["target_x"] - fx) + abs(m["target_y"] - fy) for fx, fy in food
    ))


def play_turn(api, game_id, state, diet, rng):
    """Decide actions for all dinos and submit."""
    my_dinos = [d for d in state["dinosaurs"] if d["is_mine"]]
    actions = []

    for dino in my_dinos:
        legal = api.get(f"/api/games/{game_id}/legal-actions/{dino['id']}")["actions"]
        if not legal:
            continue

        energy_pct = dino["energy"] / dino["max_energy"] if dino["max_energy"] > 0 else 0

        # Lay egg if energy is high
        if energy_pct > 0.8 and any(a["action_type"] == "lay_egg" for a in legal):
            actions.append({"dino_id": dino["id"], "action_type": "lay_egg"})
            continue

        # Grow if energy is high
        if energy_pct > 0.7 and any(a["action_type"] == "grow" for a in legal):
            actions.append({"dino_id": dino["id"], "action_type": "grow"})
            continue

        # Move toward food
        food_move = find_food_move(state, dino, legal, diet)
        if food_move:
            actions.append(food_move)
            continue

        # Random move
        moves = [a for a in legal if a["action_type"] == "move"]
        if moves:
            actions.append(rng.choice(moves))
            continue

        actions.append({"dino_id": dino["id"], "action_type": "rest"})

    if actions:
        api.post(f"/api/games/{game_id}/actions", {"actions": actions})


def main():
    parser = argparse.ArgumentParser(description="Dinosaur Island Quickstart Bot")
    parser.add_argument("--server", default="https://inceptify.com/dinosaurisland",
                        help="Server URL")
    parser.add_argument("--name", default=f"Bot_{random.randint(1000,9999)}",
                        help="Species name")
    parser.add_argument("--diet", default="herbivore", choices=["herbivore", "carnivore"],
                        help="Diet type")
    parser.add_argument("--game", default=None,
                        help="Game ID (default: join persistent arena)")
    args = parser.parse_args()

    api = API(args.server)
    rng = random.Random()

    # Register
    resp = api.post("/api/auth/register", {"username": args.name})
    api.token = resp["token"]
    print(f"Registered as {args.name}")

    # Find game
    if args.game:
        game_id = args.game
    else:
        games = api.get("/api/games")
        # Prefer persistent arena, fall back to any joinable game
        persistent = [g for g in games if g.get("persistent")]
        active = [g for g in games if g["phase"] in ("waiting", "active")]
        pick = persistent[0] if persistent else (active[0] if active else None)
        if pick:
            game_id = pick["game_id"]
            label = "persistent arena" if pick.get("persistent") else f"game {game_id[:8]}"
            print(f"Found {label} (turn {pick['turn']})")
        else:
            print("No games found. Create one at the web UI first.")
            return

    # Join
    try:
        resp = api.post(f"/api/games/{game_id}/join",
                        {"species_name": args.name, "diet": args.diet})
        print(f"Joined as {args.diet} '{args.name}'")
    except RuntimeError as e:
        if "already in" in str(e).lower():
            print(f"Already in game, resuming...")
        else:
            raise

    # Play loop
    print(f"Playing! Press Ctrl+C to disconnect.\n")
    last_turn = -1
    try:
        while True:
            state = api.get(f"/api/games/{game_id}/state")
            turn = state["turn"]

            if turn > last_turn:
                my_dinos = [d for d in state["dinosaurs"] if d["is_mine"]]
                if my_dinos:
                    play_turn(api, game_id, state, args.diet, rng)
                    if turn % 5 == 0 or turn <= 3:
                        scores = api.get(f"/api/games/{game_id}/scores")
                        my_score = next((s for s in scores if s["name"] == args.name), None)
                        pts = my_score["score"] if my_score else 0
                        print(f"  Turn {turn}: {len(my_dinos)} dinos, {pts} pts")
                else:
                    print(f"  Turn {turn}: All dinos dead. Waiting for respawn...")
                last_turn = turn

            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\nDisconnected. Your species persists in the arena!")


if __name__ == "__main__":
    main()
