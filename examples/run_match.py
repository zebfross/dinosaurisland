#!/usr/bin/env python3
"""Run a complete match between two or more bots.

Creates a game, connects all bots, starts the game, and plays to completion.
Open the spectator UI in your browser to watch live!

Usage:
    python examples/run_match.py

    # Custom settings:
    python examples/run_match.py --bots 4 --turns 60 --size 40
"""

from __future__ import annotations

import argparse
import random
import sys
import time

sys.path.insert(0, ".")

from server.sdk import BotClient


# --- Bot strategies ---

def greedy_strategy(bot: BotClient, state: dict, dino: dict, diet: str, rng: random.Random):
    """Smart strategy: graze/hunt, grow, reproduce, explore."""
    legal = bot.get_legal_actions(dino["id"])
    if not legal:
        return

    moves = [a for a in legal if a["action_type"] == "move"]
    energy_pct = dino["energy"] / dino["max_energy"] if dino["max_energy"] > 0 else 0
    my_dinos = [d for d in state["dinosaurs"] if d["is_mine"]]

    food_type = "vegetation" if diet == "herbivore" else "carrion"
    food = [(c["x"], c["y"], c["energy"]) for c in state["visible_cells"]
            if c["cell_type"] == food_type and c["energy"] > 50]
    enemies = [d for d in state["dinosaurs"] if not d["is_mine"]]

    # Carnivore: hunt weak prey if visible
    if diet == "carnivore" and enemies and moves:
        my_power = dino["dimension"] * dino["energy"] * 2
        weak = [e for e in enemies if e["dimension"] * e["max_energy"] < my_power]
        if weak:
            target = min(weak, key=lambda e: abs(dino["x"]-e["x"]) + abs(dino["y"]-e["y"]))
            attack = next((m for m in moves if m["target_x"] == target["x"] and m["target_y"] == target["y"]), None)
            if attack:
                bot.queue_action(dino["id"], "move", target_x=attack["target_x"], target_y=attack["target_y"])
                return
            best = min(moves, key=lambda m: abs(m["target_x"]-target["x"]) + abs(m["target_y"]-target["y"]))
            bot.queue_action(dino["id"], "move", target_x=best["target_x"], target_y=best["target_y"])
            return

    # Herbivore: flee from nearby carnivores
    if diet == "herbivore" and moves:
        threats = [e for e in enemies if e["diet"] == "carnivore"
                   and abs(dino["x"]-e["x"]) + abs(dino["y"]-e["y"]) <= 4]
        if threats:
            t = threats[0]
            flee = max(moves, key=lambda m: abs(m["target_x"]-t["x"]) + abs(m["target_y"]-t["y"]))
            bot.queue_action(dino["id"], "move", target_x=flee["target_x"], target_y=flee["target_y"])
            return

    # Grow if decent energy and small
    if energy_pct > 0.6 and dino["dimension"] < (4 if diet == "carnivore" else 3):
        if any(a["action_type"] == "grow" for a in legal):
            bot.queue_action(dino["id"], "grow")
            return

    # Lay egg if high energy and few dinos
    if energy_pct > 0.75 and len(my_dinos) < 4:
        if any(a["action_type"] == "lay_egg" for a in legal):
            bot.queue_action(dino["id"], "lay_egg")
            return

    # On food? Stay and eat
    on_food = any(c["x"] == dino["x"] and c["y"] == dino["y"]
                  and c["cell_type"] == food_type and c["energy"] > 50
                  for c in state["visible_cells"])
    if on_food and energy_pct < 0.95:
        bot.queue_action(dino["id"], "rest")
        return

    # Move toward richest food
    if food and moves:
        my_pos = {(d["x"], d["y"]) for d in my_dinos}
        unoccupied = [(x, y, e) for x, y, e in food if (x, y) not in my_pos]
        targets = unoccupied if unoccupied else food
        best = max(targets, key=lambda f: f[2])
        move = min(moves, key=lambda m: abs(m["target_x"]-best[0]) + abs(m["target_y"]-best[1]))
        bot.queue_action(dino["id"], "move", target_x=move["target_x"], target_y=move["target_y"])
        return

    # Explore: only if energy is decent, and take short steps
    if moves and energy_pct > 0.4:
        short = [m for m in moves if abs(m["target_x"]-dino["x"]) + abs(m["target_y"]-dino["y"]) == 1]
        m = rng.choice(short if short else moves)
        bot.queue_action(dino["id"], "move", target_x=m["target_x"], target_y=m["target_y"])
        return

    # Low energy — rest
    bot.queue_action(dino["id"], "rest")

    bot.queue_action(dino["id"], "rest")


class BotPlayer:
    """A bot that can compute actions for a turn."""

    def __init__(self, server: str, game_id: str, name: str, diet: str, seed: int):
        self.name = name
        self.diet = diet
        self.rng = random.Random(seed)
        self.bot = BotClient(server)
        self.bot.register(name)
        self.bot.join(game_id, name, diet)
        print(f"  [{name}] joined as {diet}")

    def play_turn(self):
        """Get state, decide actions, submit. Returns state."""
        state = self.bot.get_state()
        if state["phase"] != "active":
            return state
        my_dinos = [d for d in state["dinosaurs"] if d["is_mine"]]
        for dino in my_dinos:
            greedy_strategy(self.bot, state, dino, self.diet, self.rng)
        self.bot.submit()
        return state

    def close(self):
        self.bot.close()


BOT_CONFIGS = [
    ("Raptors", "carnivore"),
    ("Triceratops", "herbivore"),
    ("T-Rex", "carnivore"),
    ("Stegosaurs", "herbivore"),
    ("Velociraptors", "carnivore"),
    ("Brontosaurs", "herbivore"),
]


def main():
    parser = argparse.ArgumentParser(description="Run a Dinosaur Island match")
    parser.add_argument("--server", default="http://localhost:8000")
    parser.add_argument("--bots", type=int, default=2, help="Number of bots (2-6)")
    parser.add_argument("--size", type=int, default=30, help="Map size")
    parser.add_argument("--turns", type=int, default=120, help="Max turns")
    parser.add_argument("--timeout", type=int, default=10, help="Turn timeout (seconds)")
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    args = parser.parse_args()

    num_bots = max(2, min(6, args.bots))
    seed = args.seed if args.seed is not None else random.randint(0, 999999)

    # Create game
    admin = BotClient(args.server)
    admin.register("match_admin")
    game = admin.create_game(
        width=args.size, height=args.size,
        max_turns=args.turns, turn_timeout=args.timeout,
        seed=seed,
    )
    game_id = game["game_id"]

    print(f"Game created: {game_id}")
    print(f"  Map: {args.size}x{args.size}, {args.turns} turns, seed={seed}")
    print(f"  Spectate: open your browser and click 'Watch' on this game")
    print(f"  Bots: {num_bots}")
    print()

    # Create bot players
    bots: list[BotPlayer] = []
    for i in range(num_bots):
        name, diet = BOT_CONFIGS[i % len(BOT_CONFIGS)]
        bots.append(BotPlayer(args.server, game_id, name, diet, seed + i))

    # Start the game
    admin.start_game(game_id)
    admin.game_id = game_id
    print("\nGame started! Watch in the browser.\n")

    # Run turns sequentially — all bots submit, then turn processes
    turn = 0
    while True:
        state = admin._get(f"/api/games/{game_id}/spectate")
        if state["phase"] != "active":
            break

        turn = state["turn"]
        alive_count = len(state["dinosaurs"])

        # Each bot submits actions for this turn
        for bot in bots:
            bot.play_turn()

        # Wait briefly for turn to process (check_all_submitted fires on last submit)
        time.sleep(0.1)

        new_state = admin._get(f"/api/games/{game_id}/spectate")
        events = []
        if new_state["turn"] > turn:
            if turn % 10 == 0 or turn < 5:
                print(f"  Turn {new_state['turn']}: {len(new_state['dinosaurs'])} dinos alive")
        else:
            # Turn didn't advance — wait for timer
            time.sleep(1)

    # Print results
    scores = admin.get_scores()
    final = admin._get(f"/api/games/{game_id}/spectate")
    print(f"\n{'='*40}")
    print(f"  GAME OVER — Turn {final['turn']}")
    print(f"{'='*40}")
    for i, s in enumerate(sorted(scores, key=lambda x: x["score"], reverse=True)):
        medal = ["1st", "2nd", "3rd"][i] if i < 3 else f"{i+1}th"
        diet_ch = "H" if s["diet"] == "herbivore" else "C"
        print(f"  {medal}: {s['name']} [{diet_ch}] — {s['score']} pts ({s['dino_count']} dinos)")

    for bot in bots:
        bot.close()
    admin.close()


if __name__ == "__main__":
    main()
