"""Interactive CLI game loop — human vs bot(s)."""

from __future__ import annotations

import os
import random
import sys

from server.bots.random_bot import RandomBot
from server.engine.game import GameEngine
from server.engine.models import (
    Action,
    ActionType,
    DietType,
    GamePhase,
    TurnActions,
)
from server.cli.display import (
    C,
    render_dino_actions_prompt,
    render_map,
    render_species_status,
    render_turn_header,
    render_turn_result_summary,
)


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def prompt_species_setup() -> tuple[str, DietType]:
    """Ask the player for their species name and diet."""
    print(f"\n{C.BOLD}=== DINOSAUR ISLAND ==={C.RESET}")
    print(f"{C.DIM}A turn-based survival game{C.RESET}\n")

    name = input(f"  Species name: ").strip()
    if not name:
        name = "PlayerDinos"

    print(f"\n  Diet type:")
    print(f"    {C.GREEN}[h]{C.RESET} Herbivore — eats vegetation, 2-step movement")
    print(f"    {C.RED}[c]{C.RESET} Carnivore — eats carrion & hunts, 3-step movement")
    choice = input(f"  Choose (h/c): ").strip().lower()
    diet = DietType.CARNIVORE if choice == "c" else DietType.HERBIVORE

    return name, diet


def prompt_game_settings() -> tuple[int, int, int, int]:
    """Ask for game settings."""
    print(f"\n{C.BOLD}Game Settings{C.RESET}")

    size_input = input(f"  Map size (default 30): ").strip()
    size = int(size_input) if size_input.isdigit() else 30
    size = max(10, min(60, size))

    turns_input = input(f"  Max turns (default 120): ").strip()
    max_turns = int(turns_input) if turns_input.isdigit() else 120

    bots_input = input(f"  Number of bot opponents (default 1, max 3): ").strip()
    num_bots = int(bots_input) if bots_input.isdigit() else 1
    num_bots = max(1, min(3, num_bots))

    seed_input = input(f"  Map seed (default random): ").strip()
    seed = int(seed_input) if seed_input.isdigit() else random.randint(0, 999999)

    return size, max_turns, num_bots, seed


def get_player_actions(engine: GameEngine, state, player_species) -> list[Action]:
    """Prompt the player for actions for each dinosaur."""
    actions: list[Action] = []

    for dino in player_species.alive_dinos:
        legal = engine.get_legal_actions(state, dino.id)
        if not legal:
            continue

        # Separate moves from other actions
        non_move = [a for a in legal if a.action_type != ActionType.MOVE]
        moves = [a for a in legal if a.action_type == ActionType.MOVE]

        print(render_dino_actions_prompt(dino, player_species, legal))

        while True:
            raw = input(f"  > ").strip().lower()

            if not raw:
                # Default: rest
                rest = next((a for a in legal if a.action_type == ActionType.REST), None)
                if rest:
                    actions.append(rest)
                    print(f"    {C.DIM}Resting.{C.RESET}")
                break

            # Handle "m X Y" for move
            if raw.startswith("m "):
                parts = raw.split()
                if len(parts) == 3:
                    try:
                        tx, ty = int(parts[1]), int(parts[2])
                        move = next(
                            (a for a in moves if a.target_x == tx and a.target_y == ty),
                            None,
                        )
                        if move:
                            actions.append(move)
                            print(f"    {C.DIM}Moving to ({tx},{ty}).{C.RESET}")
                            break
                        else:
                            print(f"    {C.RED}Can't reach ({tx},{ty}).{C.RESET}")
                            continue
                    except ValueError:
                        pass
                print(f"    {C.RED}Usage: m X Y{C.RESET}")
                continue

            # Handle numeric index for non-move actions
            if raw.isdigit():
                idx = int(raw)
                if 0 <= idx < len(non_move):
                    chosen = non_move[idx]
                    actions.append(chosen)
                    print(f"    {C.DIM}{chosen.action_type.value}.{C.RESET}")
                    break
                else:
                    print(f"    {C.RED}Invalid choice.{C.RESET}")
                    continue

            # Shorthand commands
            if raw in ("r", "rest"):
                rest = next((a for a in legal if a.action_type == ActionType.REST), None)
                if rest:
                    actions.append(rest)
                    print(f"    {C.DIM}Resting.{C.RESET}")
                break
            elif raw in ("g", "grow"):
                grow = next((a for a in legal if a.action_type == ActionType.GROW), None)
                if grow:
                    actions.append(grow)
                    print(f"    {C.DIM}Growing!{C.RESET}")
                    break
                else:
                    print(f"    {C.RED}Can't grow right now.{C.RESET}")
            elif raw in ("e", "egg", "lay"):
                egg = next((a for a in legal if a.action_type == ActionType.LAY_EGG), None)
                if egg:
                    actions.append(egg)
                    print(f"    {C.DIM}Laying egg!{C.RESET}")
                    break
                else:
                    print(f"    {C.RED}Can't lay egg right now.{C.RESET}")
            elif raw in ("?", "help"):
                print(f"    Commands: m X Y, r/rest, g/grow, e/egg, NUMBER, ? for help")
                print(f"    Press Enter to rest.")
            elif raw in ("q", "quit"):
                print(f"\n{C.BOLD}Quitting...{C.RESET}")
                sys.exit(0)
            else:
                print(f"    {C.RED}Unknown command. Type ? for help.{C.RESET}")

    return actions


BOT_NAMES = ["Raptors", "TerrorBirds", "Megalodons", "Stegosaurs"]
BOT_DIETS = [DietType.CARNIVORE, DietType.HERBIVORE, DietType.CARNIVORE, DietType.HERBIVORE]


def run():
    """Main CLI entry point."""
    try:
        player_name, player_diet = prompt_species_setup()
        size, max_turns, num_bots, seed = prompt_game_settings()
    except (KeyboardInterrupt, EOFError):
        print(f"\n{C.DIM}Bye!{C.RESET}")
        return

    print(f"\n{C.DIM}Generating map (seed={seed})...{C.RESET}")

    rng = random.Random(seed)
    engine = GameEngine(rng=rng)
    state = engine.create_game(width=size, height=size, max_turns=max_turns)

    # Add player species
    player_sp = engine.add_species(state, "human", player_name, player_diet)

    # Add bot species
    bot_rng = random.Random(seed + 1)
    bots: list[tuple[str, RandomBot]] = []
    for i in range(num_bots):
        bot_name = BOT_NAMES[i % len(BOT_NAMES)]
        bot_diet = BOT_DIETS[i % len(BOT_DIETS)]
        sp = engine.add_species(state, f"bot{i}", bot_name, bot_diet)
        bot = RandomBot(rng=random.Random(seed + i + 100))
        bots.append((sp.id, bot))

    engine.start_game(state)

    # Main game loop
    try:
        while state.phase == GamePhase.ACTIVE:
            clear_screen()

            # Display
            print(render_turn_header(state))
            print()
            print(render_map(state, player_sp))
            print()

            # Status for all species
            for sp in state.species.values():
                is_player = sp.id == player_sp.id
                print(render_species_status(sp, is_player=is_player))
            print()

            # Show last turn result if available
            if state.turn_results:
                last = state.turn_results[-1]
                print(render_turn_result_summary(last))
                print()

            # Get player actions
            if player_sp.dino_count > 0:
                player_actions = get_player_actions(engine, state, player_sp)
                if player_actions:
                    errors = engine.submit_actions(
                        state,
                        TurnActions(species_id=player_sp.id, actions=player_actions),
                    )
                    for err in errors:
                        print(f"  {C.RED}Error: {err.reason}{C.RESET}")
            else:
                print(f"  {C.DIM}No living dinosaurs. Watching...{C.RESET}")
                input(f"  Press Enter to continue...")

            # Bot actions
            for sp_id, bot in bots:
                sp = state.species[sp_id]
                if sp.dino_count > 0:
                    bot_actions = bot.decide_actions(engine, state, sp)
                    if bot_actions:
                        engine.submit_actions(
                            state,
                            TurnActions(species_id=sp_id, actions=bot_actions),
                        )

            # Process turn
            result = engine.process_turn(state)

    except (KeyboardInterrupt, EOFError):
        print(f"\n\n{C.BOLD}Game interrupted!{C.RESET}")

    # Game over screen
    clear_screen()
    print(f"\n{C.BOLD}{'=' * 50}")
    print(f"  GAME OVER — Turn {state.turn}")
    print(f"{'=' * 50}{C.RESET}\n")

    print(render_map(state, player_sp, show_fog=False))
    print()

    # Final scoreboard
    sorted_species = sorted(state.species.values(), key=lambda s: s.score, reverse=True)
    print(f"{C.BOLD}  Final Scores:{C.RESET}")
    for i, sp in enumerate(sorted_species):
        medal = ["🥇", "🥈", "🥉"][i] if i < 3 else "  "
        is_you = " (YOU)" if sp.id == player_sp.id else ""
        diet_ch = "H" if sp.diet == DietType.HERBIVORE else "C"
        print(f"    {medal} {sp.name} [{diet_ch}]{is_you}: {sp.score} points")

    print()


if __name__ == "__main__":
    run()
