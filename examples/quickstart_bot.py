#!/usr/bin/env python3
"""Dinosaur Island — Quickstart Bot

A self-contained bot that connects to the persistent arena and plays.
No dependencies beyond Python 3. Supports both herbivore and carnivore.

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


# --- Helpers ---

def dist(x1, y1, x2, y2):
    return abs(x1 - x2) + abs(y1 - y2)


def best_move_toward(moves, tx, ty):
    """Pick the move that gets closest to target (tx, ty)."""
    if not moves:
        return None
    return min(moves, key=lambda m: dist(m["target_x"], m["target_y"], tx, ty))


def find_food_cells(state, food_type):
    """Find cells with food energy."""
    return [(c["x"], c["y"], c["energy"]) for c in state["visible_cells"]
            if c["cell_type"] == food_type and c["energy"] > 50]


def find_enemy_dinos(state):
    """Find enemy dinos we can see."""
    return [d for d in state["dinosaurs"] if not d["is_mine"]]


# --- Herbivore strategy ---
#
# Philosophy: graze sustainably. Spread out, find rich vegetation,
# stay put on it to eat while it regrows. Grow big, lay eggs to
# build a herd. Avoid carnivores.

def herbivore_action(api, game_id, state, dino, legal, rng):
    moves = [a for a in legal if a["action_type"] == "move"]
    energy_pct = dino["energy"] / dino["max_energy"] if dino["max_energy"] > 0 else 0

    # Am I on vegetation? Check current cell
    on_food = any(c["x"] == dino["x"] and c["y"] == dino["y"]
                  and c["cell_type"] == "vegetation" and c["energy"] > 100
                  for c in state["visible_cells"])

    # Are there carnivores nearby? Flee!
    enemies = find_enemy_dinos(state)
    carnivores = [e for e in enemies if e["diet"] == "carnivore"]
    nearby_threats = [e for e in carnivores if dist(dino["x"], dino["y"], e["x"], e["y"]) <= 4]

    if nearby_threats and moves:
        # Move away from the nearest threat
        threat = min(nearby_threats, key=lambda e: dist(dino["x"], dino["y"], e["x"], e["y"]))
        flee = max(moves, key=lambda m: dist(m["target_x"], m["target_y"], threat["x"], threat["y"]))
        return flee

    # Lay egg if we have plenty of energy and few dinos
    my_dinos = [d for d in state["dinosaurs"] if d["is_mine"]]
    if energy_pct > 0.75 and len(my_dinos) < 4:
        if any(a["action_type"] == "lay_egg" for a in legal):
            return {"dino_id": dino["id"], "action_type": "lay_egg"}

    # Grow if we have energy and are small
    if energy_pct > 0.65 and dino["dimension"] < 3:
        if any(a["action_type"] == "grow" for a in legal):
            return {"dino_id": dino["id"], "action_type": "grow"}

    # If sitting on good food, stay and eat
    if on_food and energy_pct < 0.95:
        return {"dino_id": dino["id"], "action_type": "rest"}

    # Move toward richest visible vegetation
    food = find_food_cells(state, "vegetation")
    if food and moves:
        # Prefer food that other dinos aren't already heading toward
        my_positions = {(d["x"], d["y"]) for d in my_dinos}
        unoccupied_food = [(x, y, e) for x, y, e in food if (x, y) not in my_positions]
        target_food = unoccupied_food if unoccupied_food else food

        # Pick richest food source
        best = max(target_food, key=lambda f: f[2])
        move = best_move_toward(moves, best[0], best[1])
        if move:
            return move

    # Explore: move in a consistent direction to discover new areas
    if moves:
        # Prefer moves that go away from map center (explore edges)
        return max(moves, key=lambda m: dist(m["target_x"], m["target_y"], 20, 20) + rng.random())

    return {"dino_id": dino["id"], "action_type": "rest"}


# --- Carnivore strategy ---
#
# Philosophy: hunt aggressively. Find prey (enemy herbivores), close in,
# and attack. Eat carrion when no prey is available. Stay lean and fast
# (carnivores move 3 steps vs 2 for herbivores). Grow big for combat power.

def carnivore_action(api, game_id, state, dino, legal, rng):
    moves = [a for a in legal if a["action_type"] == "move"]
    energy_pct = dino["energy"] / dino["max_energy"] if dino["max_energy"] > 0 else 0

    enemies = find_enemy_dinos(state)
    my_dinos = [d for d in state["dinosaurs"] if d["is_mine"]]

    # PRIORITY: if energy is low, find food or rest — don't waste energy exploring
    if energy_pct < 0.3:
        # On carrion? Stay and eat
        on_carrion = any(c["x"] == dino["x"] and c["y"] == dino["y"]
                         and c["cell_type"] == "carrion" and c["energy"] > 0
                         for c in state["visible_cells"])
        if on_carrion:
            return {"dino_id": dino["id"], "action_type": "rest"}

        # Nearby carrion? Move toward it (1 step only to conserve energy)
        carrion = find_food_cells(state, "carrion")
        if carrion and moves:
            nearby = [f for f in carrion if dist(dino["x"], dino["y"], f[0], f[1]) <= 3]
            if nearby:
                best = max(nearby, key=lambda f: f[2])
                short_moves = [m for m in moves
                               if dist(dino["x"], dino["y"], m["target_x"], m["target_y"]) == 1]
                move = best_move_toward(short_moves or moves, best[0], best[1])
                if move:
                    return move

        # Nothing nearby — rest to avoid starvation from movement
        return {"dino_id": dino["id"], "action_type": "rest"}

    # On carrion? Stay and eat until full
    on_carrion = any(c["x"] == dino["x"] and c["y"] == dino["y"]
                     and c["cell_type"] == "carrion" and c["energy"] > 0
                     for c in state["visible_cells"])
    if on_carrion and energy_pct < 0.9:
        return {"dino_id": dino["id"], "action_type": "rest"}

    # Grow — bigger = stronger in combat
    if energy_pct > 0.6 and dino["dimension"] < 4:
        if any(a["action_type"] == "grow" for a in legal):
            return {"dino_id": dino["id"], "action_type": "grow"}

    # Lay egg if strong and few dinos
    if energy_pct > 0.8 and len(my_dinos) < 3:
        if any(a["action_type"] == "lay_egg" for a in legal):
            return {"dino_id": dino["id"], "action_type": "lay_egg"}

    # Hunt: move toward weakest visible enemy (only if we have energy to spare)
    if enemies and moves and energy_pct > 0.4:
        my_power = dino["dimension"] * dino["energy"] * 2  # carnivore 2x
        weak_prey = [e for e in enemies if e["dimension"] * e["max_energy"] < my_power]
        if weak_prey:
            target = min(weak_prey,
                         key=lambda e: dist(dino["x"], dino["y"], e["x"], e["y"]))

            # Attack if adjacent
            attack = next((m for m in moves
                           if m["target_x"] == target["x"] and m["target_y"] == target["y"]), None)
            if attack:
                return attack

            # Close distance
            move = best_move_toward(moves, target["x"], target["y"])
            if move:
                return move

    # Move toward carrion
    carrion = find_food_cells(state, "carrion")
    if carrion and moves:
        best = max(carrion, key=lambda f: f[2])
        move = best_move_toward(moves, best[0], best[1])
        if move:
            return move

    # Explore cautiously — only move 1 step to conserve energy
    if moves and energy_pct > 0.4:
        short_moves = [m for m in moves
                       if dist(dino["x"], dino["y"], m["target_x"], m["target_y"]) == 1]
        if short_moves:
            return rng.choice(short_moves)

    # Low energy, nothing to do — rest and hope for carrion to spawn nearby
    return {"dino_id": dino["id"], "action_type": "rest"}


# --- Main loop ---

def play_turn(api, game_id, state, diet, rng):
    my_dinos = [d for d in state["dinosaurs"] if d["is_mine"]]
    actions = []

    for dino in my_dinos:
        legal = api.get(f"/api/games/{game_id}/legal-actions/{dino['id']}")["actions"]
        if not legal:
            continue

        if diet == "herbivore":
            action = herbivore_action(api, game_id, state, dino, legal, rng)
        else:
            action = carnivore_action(api, game_id, state, dino, legal, rng)

        actions.append(action)

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
    print(f"Playing as {args.diet}! Press Ctrl+C to disconnect.\n")
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
                    if turn % 20 == 0:
                        print(f"  Turn {turn}: All dinos dead. Waiting...")
                last_turn = turn

            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\nDisconnected. Your species persists in the arena!")


if __name__ == "__main__":
    main()
