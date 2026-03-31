#!/usr/bin/env python3
"""Example bot for Dinosaur Island.

This bot connects to the server, joins a game, and plays using a simple
greedy strategy: herbivores seek vegetation, carnivores seek carrion.

Usage:
    # First create a game via the web UI or API, then:
    python examples/example_bot.py --game GAME_ID --name MyBot --diet herbivore

    # Or create a new game and start it with a second bot:
    python examples/example_bot.py --create --name HerbBot --diet herbivore &
    python examples/example_bot.py --game GAME_ID --name CarnBot --diet carnivore --start
"""

from __future__ import annotations

import argparse
import random
import sys
import time

# Add project root to path so we can import the SDK
sys.path.insert(0, ".")

from server.sdk import BotClient


def find_nearest_food(state: dict, dino: dict, legal_actions: list[dict], diet: str) -> dict | None:
    """Find the move action that gets closest to the nearest food source."""
    target_type = "vegetation" if diet == "herbivore" else "carrion"

    # Find food cells with energy
    food_cells = [
        (c["x"], c["y"])
        for c in state["visible_cells"]
        if c["cell_type"] == target_type and c["energy"] > 0
    ]

    if not food_cells:
        return None

    # Find which legal move gets us closest to any food
    moves = [a for a in legal_actions if a["action_type"] == "move"]
    if not moves:
        return None

    def dist(x1, y1, x2, y2):
        return abs(x1 - x2) + abs(y1 - y2)

    best_move = None
    best_dist = float("inf")

    for move in moves:
        mx, my = move["target_x"], move["target_y"]
        for fx, fy in food_cells:
            d = dist(mx, my, fx, fy)
            if d < best_dist:
                best_dist = d
                best_move = move

    return best_move


def decide_action(bot: BotClient, state: dict, dino: dict, diet: str) -> None:
    """Decide and queue an action for one dinosaur."""
    legal = bot.get_legal_actions(dino["id"])
    if not legal:
        return

    energy_pct = dino["energy"] / dino["max_energy"] if dino["max_energy"] > 0 else 0

    # If we can lay an egg and have plenty of energy, do it
    if energy_pct > 0.8:
        egg_action = next((a for a in legal if a["action_type"] == "lay_egg"), None)
        if egg_action:
            bot.queue_action(dino["id"], "lay_egg")
            return

    # If we can grow and have plenty of energy, do it
    if energy_pct > 0.7:
        grow_action = next((a for a in legal if a["action_type"] == "grow"), None)
        if grow_action:
            bot.queue_action(dino["id"], "grow")
            return

    # Move toward nearest food
    food_move = find_nearest_food(state, dino, legal, diet)
    if food_move:
        bot.queue_action(
            dino["id"], "move",
            target_x=food_move["target_x"],
            target_y=food_move["target_y"],
        )
        return

    # Random move as fallback
    moves = [a for a in legal if a["action_type"] == "move"]
    if moves:
        move = random.choice(moves)
        bot.queue_action(
            dino["id"], "move",
            target_x=move["target_x"],
            target_y=move["target_y"],
        )
        return

    # Rest
    bot.queue_action(dino["id"], "rest")


def main():
    parser = argparse.ArgumentParser(description="Dinosaur Island example bot")
    parser.add_argument("--server", default="http://localhost:8000", help="Server URL")
    parser.add_argument("--game", help="Game ID to join")
    parser.add_argument("--create", action="store_true", help="Create a new game")
    parser.add_argument("--start", action="store_true", help="Start the game after joining")
    parser.add_argument("--name", default="ExampleBot", help="Species name")
    parser.add_argument("--diet", default="herbivore", choices=["herbivore", "carnivore"])
    args = parser.parse_args()

    bot = BotClient(args.server)
    bot.register(args.name)
    print(f"Registered as {args.name}")

    # Create or join game
    if args.create:
        game = bot.create_game(width=30, height=30, max_turns=120, turn_timeout=10)
        game_id = game["game_id"]
        print(f"Created game {game_id}")
    else:
        if not args.game:
            # List games and pick the first waiting one
            games = bot.list_games()
            waiting = [g for g in games if g["phase"] == "waiting"]
            if not waiting:
                print("No waiting games found. Use --create to make one.")
                return
            game_id = waiting[0]["game_id"]
            print(f"Found waiting game {game_id}")
        else:
            game_id = args.game

    resp = bot.join(game_id, args.name, args.diet)
    print(f"Joined as {args.diet} species '{args.name}'")

    if args.start:
        bot.start_game()
        print("Game started!")

    # Wait for game to start
    print("Waiting for game to start...")
    while True:
        state = bot.get_state()
        if state["phase"] == "active":
            break
        if state["phase"] == "finished":
            print("Game already finished.")
            return
        time.sleep(1)

    print(f"Game is active! Playing...")

    # Main game loop
    while True:
        state = bot.get_state()

        if state["phase"] != "active":
            print(f"Game ended at turn {state['turn']}!")
            break

        my_dinos = [d for d in state["dinosaurs"] if d["is_mine"]]
        print(f"  Turn {state['turn']}: {len(my_dinos)} dinos alive")

        for dino in my_dinos:
            decide_action(bot, state, dino, args.diet)

        result = bot.submit()
        print(f"    Submitted {result['accepted']} actions")

        if result.get("errors"):
            for err in result["errors"]:
                print(f"    Error: {err['reason']}")

        # Wait for next turn
        state = bot.wait_for_turn(poll_interval=0.5)

    # Final scores
    scores = bot.get_scores()
    print("\nFinal scores:")
    for s in sorted(scores, key=lambda x: x["score"], reverse=True):
        print(f"  {s['name']}: {s['score']} pts ({s['dino_count']} dinos)")

    bot.close()


if __name__ == "__main__":
    main()
