#!/usr/bin/env python3
"""Analyze a Dinosaur Island game replay.

Fetches replay data from the server and prints stats about species
performance, deaths, reproduction, and resource usage.

Usage:
    python analyze_game.py                    # analyze persistent arena
    python analyze_game.py --game GAME_ID     # analyze specific game
    python analyze_game.py --server http://localhost:8000
"""

import argparse
import json
import urllib.request
from collections import defaultdict


def api_get(server, path):
    req = urllib.request.Request(f"{server}{path}")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def analyze(server, game_id):
    print(f"Fetching replay for game {game_id[:12]}...")
    replay = api_get(server, f"/api/games/{game_id}/replay")

    frames = replay["frames"]
    if not frames:
        print("No frames in replay.")
        return

    print(f"Game: {replay['map_width']}x{replay['map_height']} map, "
          f"{len(frames)} turns, max {replay['max_turns']}\n")

    # Track per-species stats
    species_stats = defaultdict(lambda: {
        "diet": "?",
        "max_dinos": 0,
        "total_dino_turns": 0,  # sum of dinos alive each turn
        "peak_score": 0,
        "final_score": 0,
        "first_seen": None,
        "last_alive": None,
        "hatches": 0,
        "deaths": 0,
        "death_causes": defaultdict(int),
        "kills": 0,
        "killed_by": defaultdict(int),
        "max_dimension": 0,
    })

    for f in frames:
        turn = f["turn"]

        # Count dinos per species this turn
        species_dinos = defaultdict(list)
        for d in f["dinosaurs"]:
            species_dinos[d["species_name"]].append(d)
            stats = species_stats[d["species_name"]]
            stats["diet"] = d["diet"]
            if stats["first_seen"] is None:
                stats["first_seen"] = turn
            stats["last_alive"] = turn
            if d["dimension"] > stats["max_dimension"]:
                stats["max_dimension"] = d["dimension"]

        for name, dinos in species_dinos.items():
            stats = species_stats[name]
            stats["total_dino_turns"] += len(dinos)
            if len(dinos) > stats["max_dinos"]:
                stats["max_dinos"] = len(dinos)

        # Track scores
        for s in f["scores"]:
            stats = species_stats[s["name"]]
            stats["final_score"] = s["score"]
            if s["score"] > stats["peak_score"]:
                stats["peak_score"] = s["score"]

        # Track events
        for ev in f.get("events", []):
            stats = species_stats[ev["species_name"]]
            if ev["kind"] == "hatch":
                stats["hatches"] += 1
            elif ev["kind"] == "death":
                stats["deaths"] += 1
                # Extract cause from detail
                detail = ev["detail"]
                if "starvation" in detail:
                    stats["death_causes"]["starvation"] += 1
                elif "old age" in detail:
                    stats["death_causes"]["old age"] += 1
                elif "failed growth" in detail:
                    stats["death_causes"]["failed growth"] += 1
                else:
                    stats["death_causes"]["other"] += 1
            elif ev["kind"] == "combat":
                stats["kills"] += 1
                # Extract victim from "X killed Y (+N energy)"
                detail = ev["detail"]
                if " killed " in detail:
                    victim = detail.split(" killed ")[1].split(" (")[0]
                    species_stats[victim]["killed_by"][ev["species_name"]] += 1

    # Print results
    sorted_species = sorted(species_stats.items(), key=lambda x: x[1]["final_score"], reverse=True)

    print(f"{'='*60}")
    print(f"  SPECIES ANALYSIS ({len(sorted_species)} species)")
    print(f"{'='*60}\n")

    for name, s in sorted_species:
        diet_ch = "H" if s["diet"] == "herbivore" else "C"
        lifespan = f"turns {s['first_seen']}-{s['last_alive']}" if s["first_seen"] is not None else "never spawned"

        print(f"  {name} [{diet_ch}]")
        print(f"    Score: {s['final_score']} (peak: {s['peak_score']})")
        print(f"    Active: {lifespan}")
        print(f"    Max dinos alive: {s['max_dinos']}, max dimension: {s['max_dimension']}")
        print(f"    Avg dinos/turn: {s['total_dino_turns'] / max(1, (s['last_alive'] or 0) - (s['first_seen'] or 0) + 1):.1f}")
        print(f"    Eggs hatched: {s['hatches']}")
        print(f"    Deaths: {s['deaths']}")
        if s["death_causes"]:
            causes = ", ".join(f"{c}: {n}" for c, n in sorted(s["death_causes"].items(), key=lambda x: -x[1]))
            print(f"      Causes: {causes}")
        if s["kills"]:
            print(f"    Kills: {s['kills']}")
        if s["killed_by"]:
            killers = ", ".join(f"{k}: {n}" for k, n in s["killed_by"].items())
            print(f"    Killed by: {killers}")
        print()

    # Summary
    total_hatches = sum(s["hatches"] for _, s in sorted_species)
    total_deaths = sum(s["deaths"] for _, s in sorted_species)
    all_causes = defaultdict(int)
    for _, s in sorted_species:
        for cause, count in s["death_causes"].items():
            all_causes[cause] += count

    print(f"{'='*60}")
    print(f"  GAME SUMMARY")
    print(f"{'='*60}")
    print(f"  Total hatches: {total_hatches}")
    print(f"  Total deaths:  {total_deaths}")
    if all_causes:
        print(f"  Death causes:  {', '.join(f'{c}: {n}' for c, n in sorted(all_causes.items(), key=lambda x: -x[1]))}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Analyze a Dinosaur Island game")
    parser.add_argument("--server", default="http://localhost:8000")
    parser.add_argument("--game", default=None, help="Game ID (default: persistent arena)")
    args = parser.parse_args()

    if args.game:
        game_id = args.game
    else:
        games = api_get(args.server, "/api/games")
        persistent = [g for g in games if g.get("persistent")]
        if persistent:
            game_id = persistent[0]["game_id"]
        elif games:
            game_id = games[0]["game_id"]
        else:
            print("No games found.")
            return

    analyze(args.server, game_id)


if __name__ == "__main__":
    main()
