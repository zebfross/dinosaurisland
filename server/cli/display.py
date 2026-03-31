"""ASCII map renderer with ANSI colors for terminal display."""

from __future__ import annotations

from server.engine.constants import VISION_RANGE
from server.engine.models import (
    CellType,
    DietType,
    Dinosaur,
    GameMap,
    GameState,
    Species,
)
from server.engine.vision import cells_in_vision


# ANSI color codes
class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Foreground
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Background
    BG_BLUE = "\033[44m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_RED = "\033[41m"
    BG_WHITE = "\033[47m"
    BG_BLACK = "\033[40m"
    BG_DARK = "\033[100m"

    # Bright foreground
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"


# Player colors for different species
SPECIES_COLORS = [
    C.BRIGHT_CYAN,
    C.BRIGHT_RED,
    C.BRIGHT_YELLOW,
    C.MAGENTA,
]


def render_map(
    state: GameState,
    viewer_species: Species,
    show_fog: bool = True,
) -> str:
    """Render the game map as a colored ASCII string.

    Legend:
      ~  water (blue)
      .  plain (dark)
      "  vegetation (green, brighter = more energy)
      %  carrion (red, brighter = more energy)
      1-5  dinosaur (colored by species, number = dimension)
      o  egg
      #  unexplored (fog)
    """
    gm = state.game_map
    revealed = viewer_species.revealed_set

    # Compute current live vision
    live_vision: set[tuple[int, int]] = set()
    for dino in viewer_species.alive_dinos:
        live_vision |= cells_in_vision(
            dino.x, dino.y, dino.vision_range, gm
        )

    # Build species color map
    species_color_map: dict[str, str] = {}
    for i, sid in enumerate(state.species):
        species_color_map[sid] = SPECIES_COLORS[i % len(SPECIES_COLORS)]

    # Build dino position lookup
    dino_at: dict[tuple[int, int], tuple[Dinosaur, Species]] = {}
    for sp in state.species.values():
        for d in sp.alive_dinos:
            dino_at[(d.x, d.y)] = (d, sp)

    # Build egg position lookup
    egg_at: set[tuple[int, int]] = set()
    for sp in state.species.values():
        for egg in sp.eggs:
            egg_at.add((egg.x, egg.y))

    # Column headers
    lines: list[str] = []
    col_header = "    " + "".join(f"{x % 10}" for x in range(gm.width))
    lines.append(C.DIM + col_header + C.RESET)

    for y in range(gm.height):
        row_label = f"{y:3d} "
        row_chars: list[str] = []
        for x in range(gm.width):
            pos = (x, y)
            in_live = pos in live_vision
            in_revealed = pos in revealed

            if show_fog and not in_revealed:
                row_chars.append(C.DIM + "#" + C.RESET)
                continue

            cell = gm.get_cell(x, y)
            dim_prefix = C.DIM if (show_fog and not in_live) else ""

            # Check for dino/egg at this position
            if pos in dino_at and in_live:
                dino, dino_sp = dino_at[pos]
                color = species_color_map.get(dino_sp.id, C.WHITE)
                ch = str(dino.dimension)
                row_chars.append(C.BOLD + color + ch + C.RESET)
                continue

            if pos in egg_at and in_live:
                row_chars.append(C.BOLD + C.WHITE + "o" + C.RESET)
                continue

            # Render terrain
            if cell.cell_type == CellType.WATER:
                row_chars.append(dim_prefix + C.BLUE + "~" + C.RESET)
            elif cell.cell_type == CellType.VEGETATION:
                if cell.energy > cell.max_energy * 0.6:
                    row_chars.append(dim_prefix + C.BRIGHT_GREEN + '"' + C.RESET)
                elif cell.energy > cell.max_energy * 0.2:
                    row_chars.append(dim_prefix + C.GREEN + '"' + C.RESET)
                else:
                    row_chars.append(dim_prefix + C.DIM + C.GREEN + '"' + C.RESET)
            elif cell.cell_type == CellType.CARRION:
                if cell.energy > cell.max_energy * 0.5:
                    row_chars.append(dim_prefix + C.BRIGHT_RED + "%" + C.RESET)
                else:
                    row_chars.append(dim_prefix + C.RED + "%" + C.RESET)
            else:  # PLAIN
                row_chars.append(dim_prefix + C.YELLOW + "." + C.RESET)

        lines.append(C.DIM + row_label + C.RESET + "".join(row_chars))

    return "\n".join(lines)


def render_species_status(species: Species, is_player: bool = False) -> str:
    """Render species info panel."""
    color = C.BRIGHT_CYAN if is_player else C.BRIGHT_RED
    marker = " (YOU)" if is_player else ""
    diet_ch = "H" if species.diet == DietType.HERBIVORE else "C"

    lines = [
        f"{color}{C.BOLD}{species.name}{C.RESET}{marker} [{diet_ch}] "
        f"Score: {species.score}  Dinos: {species.dino_count}  Eggs: {len(species.eggs)}"
    ]

    for d in species.alive_dinos:
        energy_bar = _energy_bar(d.energy, d.max_energy, 15)
        lines.append(
            f"  {color}D{d.id[:4]}{C.RESET} "
            f"dim={d.dimension} age={d.age}/{d.max_lifespan} "
            f"energy={energy_bar} {int(d.energy)}/{int(d.max_energy)} "
            f"pos=({d.x},{d.y})"
        )

    return "\n".join(lines)


def render_turn_header(state: GameState) -> str:
    """Render turn info."""
    return (
        f"\n{C.BOLD}{'=' * 50}{C.RESET}\n"
        f"{C.BOLD}  TURN {state.turn}/{state.max_turns}  "
        f"Phase: {state.phase.value}{C.RESET}\n"
        f"{C.BOLD}{'=' * 50}{C.RESET}"
    )


def render_turn_result_summary(result) -> str:
    """Render a summary of what happened this turn."""
    parts: list[str] = []
    if result.combats:
        parts.append(f"{C.RED}{len(result.combats)} combat(s){C.RESET}")
    if result.deaths:
        parts.append(f"{C.RED}{len(result.deaths)} death(s){C.RESET}")
    if result.hatches:
        parts.append(f"{C.GREEN}{len(result.hatches)} hatched{C.RESET}")
    if not parts:
        return f"  {C.DIM}Nothing eventful happened.{C.RESET}"
    return "  Events: " + ", ".join(parts)


def render_dino_actions_prompt(dino: Dinosaur, species: Species, legal_actions) -> str:
    """Render the action selection prompt for a dinosaur."""
    lines = [
        f"\n{C.BOLD}Actions for dino {dino.id[:6]}...{C.RESET} "
        f"(dim={dino.dimension}, energy={int(dino.energy)}, pos=({dino.x},{dino.y})):"
    ]

    # Group actions by type
    moves = [a for a in legal_actions if a.action_type.value == "move"]
    others = [a for a in legal_actions if a.action_type.value != "move"]

    for i, action in enumerate(others):
        lines.append(f"  {C.BRIGHT_WHITE}[{i}]{C.RESET} {action.action_type.value}")

    if moves:
        lines.append(
            f"  {C.BRIGHT_WHITE}[m X Y]{C.RESET} move to (X,Y) — "
            f"{len(moves)} reachable cells"
        )

    return "\n".join(lines)


def _energy_bar(current: float, maximum: float, width: int) -> str:
    """Render a colored energy bar."""
    if maximum <= 0:
        return C.DIM + "[" + " " * width + "]" + C.RESET
    ratio = current / maximum
    filled = int(ratio * width)
    if ratio > 0.6:
        color = C.GREEN
    elif ratio > 0.3:
        color = C.YELLOW
    else:
        color = C.RED
    bar = color + "█" * filled + C.DIM + "░" * (width - filled) + C.RESET
    return "[" + bar + "]"
