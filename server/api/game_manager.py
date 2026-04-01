"""GameManager — orchestrates games, turn timers, and WebSocket broadcasting."""

from __future__ import annotations

import asyncio
import random
import secrets
from dataclasses import dataclass, field

from fastapi import WebSocket

from server.engine.game import GameEngine
from server.engine.models import (
    Action,
    ActionType,
    DietType,
    GamePhase,
    GameState,
    InvalidActionError,
    Species,
    TurnActions,
)
from server.engine.vision import cells_in_vision
from server.api.schemas import (
    ActionError,
    CellResponse,
    DinoResponse,
    EggResponse,
    GameEvent,
    GameStateResponse,
    GameSummary,
    ReplayFrame,
    ReplayResponse,
    SpeciesScore,
    WsPhaseChange,
    WsStateUpdate,
    WsTurnResult,
    WsTurnStart,
)


@dataclass
class PlayerInfo:
    player_id: str
    username: str
    token: str


@dataclass
class GameSession:
    game_id: str
    state: GameState
    engine: GameEngine
    turn_timeout: int = 30
    # species_id -> player_id mapping
    species_to_player: dict[str, str] = field(default_factory=dict)
    # player_id -> species_id
    player_to_species: dict[str, str] = field(default_factory=dict)
    # WebSocket subscribers: player_id -> list of websockets
    subscribers: dict[str, list[WebSocket]] = field(default_factory=dict)
    # Turn timer task
    _timer_task: asyncio.Task | None = field(default=None, repr=False)
    # Track which species have submitted actions this turn
    submitted: set[str] = field(default_factory=set)
    # Replay frames — one snapshot per turn
    replay_frames: list[ReplayFrame] = field(default_factory=list)
    # Persistent mode — allows mid-game joins, no max turn limit
    persistent: bool = field(default=False)
    # Guard against concurrent turn processing
    _processing_turn: bool = field(default=False)


class GameManager:
    """Manages all active games, players, and WebSocket connections."""

    def __init__(self):
        self.players: dict[str, PlayerInfo] = {}  # token -> PlayerInfo
        self.players_by_id: dict[str, PlayerInfo] = {}  # player_id -> PlayerInfo
        self.usernames: dict[str, str] = {}  # username -> player_id
        self.games: dict[str, GameSession] = {}  # game_id -> GameSession

    # --- Auth ---

    def register(self, username: str) -> PlayerInfo:
        if username in self.usernames:
            # Return existing player with new token
            pid = self.usernames[username]
            player = self.players_by_id[pid]
            # Remove old token
            old_token = player.token
            self.players.pop(old_token, None)
            # Issue new token
            player.token = secrets.token_urlsafe(32)
            self.players[player.token] = player
            return player

        player_id = secrets.token_urlsafe(16)
        token = secrets.token_urlsafe(32)
        player = PlayerInfo(player_id=player_id, username=username, token=token)
        self.players[token] = player
        self.players_by_id[player_id] = player
        self.usernames[username] = player_id
        return player

    def get_player(self, token: str) -> PlayerInfo | None:
        return self.players.get(token)

    # --- Game lifecycle ---

    def create_game(
        self,
        width: int = 30,
        height: int = 30,
        max_turns: int = 120,
        seed: int | None = None,
        turn_timeout: int = 30,
        persistent: bool = False,
    ) -> GameSession:
        actual_seed = seed if seed is not None else random.randint(0, 999999)
        rng = random.Random(actual_seed)
        engine = GameEngine(rng=rng)
        # Persistent games have a very high turn limit
        effective_max_turns = 999999 if persistent else max_turns
        state = engine.create_game(width=width, height=height, max_turns=effective_max_turns)

        session = GameSession(
            game_id=state.id,
            state=state,
            engine=engine,
            turn_timeout=turn_timeout,
            persistent=persistent,
        )
        self.games[state.id] = session
        return session

    def get_persistent_game(self) -> GameSession | None:
        """Return the persistent game if one exists."""
        for session in self.games.values():
            if session.persistent:
                return session
        return None

    def ensure_persistent_game(self) -> GameSession:
        """Create the persistent game if it doesn't exist. Starts when first bot joins."""
        existing = self.get_persistent_game()
        if existing:
            return existing
        session = self.create_game(
            width=40, height=40, turn_timeout=10, persistent=True,
        )
        # Don't start yet — starts automatically when first bot joins
        return session

    def join_game(
        self,
        game_id: str,
        player_id: str,
        species_name: str,
        diet: DietType,
    ) -> Species:
        session = self.games.get(game_id)
        if not session:
            raise ValueError("Game not found")
        if not session.persistent and session.state.phase != GamePhase.WAITING:
            raise ValueError("Game already started")
        if session.state.phase == GamePhase.FINISHED:
            raise ValueError("Game is finished")
        if player_id in session.player_to_species:
            raise ValueError("Player already in this game")

        species = session.engine.add_species(
            session.state, player_id, species_name, diet
        )
        session.species_to_player[species.id] = player_id
        session.player_to_species[player_id] = species.id

        # Auto-start persistent games on first join
        if session.persistent and session.state.phase == GamePhase.WAITING:
            session.engine.start_game(session.state)
            session.replay_frames.append(self._build_replay_frame(session, None))

        return species

    def start_game(self, game_id: str) -> None:
        session = self.games.get(game_id)
        if not session:
            raise ValueError("Game not found")
        session.engine.start_game(session.state)
        # Record initial state as frame 0
        session.replay_frames.append(self._build_replay_frame(session, None))

    async def start_turn_timer(self, game_id: str) -> None:
        """Start the async turn timer. Auto-processes turn after timeout."""
        session = self.games.get(game_id)
        if not session:
            return

        # Cancel any existing timer
        if session._timer_task and not session._timer_task.done():
            session._timer_task.cancel()

        session.submitted.clear()
        session._timer_task = asyncio.create_task(
            self._turn_timer(game_id)
        )

    async def _turn_timer(self, game_id: str) -> None:
        session = self.games.get(game_id)
        if not session:
            return

        # Skip if no living dinos (persistent games idle until a bot joins)
        has_dinos = any(sp.dino_count > 0 for sp in session.state.species.values())
        if not has_dinos:
            await asyncio.sleep(session.turn_timeout)
            # Check again — a bot may have joined while we waited
            if session.state.phase == GamePhase.ACTIVE:
                await self.start_turn_timer(game_id)
            return

        # Broadcast turn start
        await self._broadcast(
            session,
            WsTurnStart(
                turn=session.state.turn + 1,
                deadline_seconds=session.turn_timeout,
            ).model_dump(),
        )

        await asyncio.sleep(session.turn_timeout)

        # Auto-process turn if game is still active
        if session.state.phase == GamePhase.ACTIVE:
            await self.process_turn(game_id)

    def submit_actions(
        self,
        game_id: str,
        player_id: str,
        actions: list[Action],
    ) -> list[ActionError]:
        session = self.games.get(game_id)
        if not session:
            raise ValueError("Game not found")
        if session.state.phase != GamePhase.ACTIVE:
            raise ValueError("Game not active")

        species_id = session.player_to_species.get(player_id)
        if not species_id:
            raise ValueError("Player not in this game")

        turn_actions = TurnActions(species_id=species_id, actions=actions)
        errors = session.engine.submit_actions(session.state, turn_actions)
        session.submitted.add(species_id)

        return [
            ActionError(dino_id=e.dino_id, reason=e.reason)
            for e in errors
        ]

    async def process_turn(self, game_id: str) -> None:
        """Process the current turn and broadcast results."""
        session = self.games.get(game_id)
        if not session or session.state.phase != GamePhase.ACTIVE:
            return

        # Guard against concurrent calls (both bots submitting simultaneously)
        if session._processing_turn:
            return
        session._processing_turn = True

        try:
            result = session.engine.process_turn(session.state)

            # Persistent games never truly end — keep running for new joiners
            if session.persistent and session.state.phase == GamePhase.FINISHED:
                session.state.phase = GamePhase.ACTIVE

            # Build scores and events
            scores = self._build_scores(session)
            events = self._build_events(session, result)

            # Record replay frame (cap at last 500 to avoid unbounded memory)
            session.replay_frames.append(self._build_replay_frame(session, result, events))
            if len(session.replay_frames) > 500:
                session.replay_frames = session.replay_frames[-500:]

            # Broadcast turn result summary
            await self._broadcast(
                session,
                WsTurnResult(
                    turn=result.turn_number,
                    combats=len(result.combats),
                    deaths=len(result.deaths),
                    hatches=len(result.hatches),
                    events=events,
                    scores=scores,
                ).model_dump(),
            )

            # Send per-player state updates (fog-filtered)
            for player_id, ws_list in session.subscribers.items():
                if player_id == "__spectators__":
                    continue  # handled below
                species_id = session.player_to_species.get(player_id)
                if species_id:
                    state_resp = self.get_game_state(game_id, player_id)
                    if state_resp:
                        msg = WsStateUpdate(state=state_resp).model_dump()
                        for ws in ws_list:
                            try:
                                await ws.send_json(msg)
                            except Exception:
                                pass

            # Send spectator state updates (full map, no fog)
            spectator_ws_list = session.subscribers.get("__spectators__", [])
            if spectator_ws_list:
                spectator_state = self.get_spectator_state(game_id)
                if spectator_state:
                    msg = WsStateUpdate(state=spectator_state).model_dump()
                    for ws in spectator_ws_list:
                        try:
                            await ws.send_json(msg)
                        except Exception:
                            pass

            # Check if game ended
            if session.state.phase == GamePhase.FINISHED:
                await self._broadcast(
                    session,
                    WsPhaseChange(
                        phase=GamePhase.FINISHED,
                        final_scores=scores,
                    ).model_dump(),
                )
                # Cancel timer
                if session._timer_task and not session._timer_task.done():
                    session._timer_task.cancel()
            else:
                # Start next turn timer
                await self.start_turn_timer(game_id)
        finally:
            session._processing_turn = False

    async def check_all_submitted(self, game_id: str) -> None:
        """If all active species have submitted, process turn immediately."""
        session = self.games.get(game_id)
        if not session or session.state.phase != GamePhase.ACTIVE:
            return

        active_species = {
            sid for sid, sp in session.state.species.items()
            if sp.dino_count > 0
        }
        if active_species and active_species <= session.submitted:
            # Cancel timer and process now
            if session._timer_task and not session._timer_task.done():
                session._timer_task.cancel()
            await self.process_turn(game_id)

    # --- Queries ---

    def get_game_state(self, game_id: str, player_id: str) -> GameStateResponse | None:
        session = self.games.get(game_id)
        if not session:
            return None

        species_id = session.player_to_species.get(player_id)
        if not species_id:
            return None

        species = session.state.species.get(species_id)
        if not species:
            return None

        revealed = species.revealed_set

        # Live vision
        live_vision: set[tuple[int, int]] = set()
        for dino in species.alive_dinos:
            live_vision |= cells_in_vision(
                dino.x, dino.y, dino.vision_range, session.state.game_map
            )

        # Visible cells
        visible_cells = []
        gm = session.state.game_map
        for y in range(gm.height):
            for x in range(gm.width):
                if (x, y) in revealed:
                    cell = gm.get_cell(x, y)
                    visible_cells.append(CellResponse(
                        x=x, y=y,
                        cell_type=cell.cell_type.value,
                        energy=cell.energy if (x, y) in live_vision else 0,
                        max_energy=cell.max_energy,
                    ))

        # Visible dinos
        dinos = []
        for sp in session.state.species.values():
            for d in sp.alive_dinos:
                if (d.x, d.y) in live_vision:
                    dinos.append(DinoResponse(
                        id=d.id,
                        species_id=sp.id,
                        species_name=sp.name,
                        diet=sp.diet.value,
                        x=d.x, y=d.y,
                        dimension=d.dimension,
                        energy=d.energy if sp.id == species_id else 0,
                        max_energy=d.max_energy,
                        age=d.age if sp.id == species_id else 0,
                        max_lifespan=d.max_lifespan if sp.id == species_id else 0,
                        is_mine=sp.id == species_id,
                    ))

        # Eggs (only own)
        eggs = [
            EggResponse(x=e.x, y=e.y, hatch_turn=e.hatch_turn, is_mine=True)
            for e in species.eggs
        ]

        scores = self._build_scores(session)

        return GameStateResponse(
            game_id=game_id,
            turn=session.state.turn,
            max_turns=session.state.max_turns,
            phase=session.state.phase,
            visible_cells=visible_cells,
            dinosaurs=dinos,
            eggs=eggs,
            scores=scores,
        )

    def get_legal_actions(
        self, game_id: str, player_id: str, dino_id: str
    ) -> list[Action]:
        session = self.games.get(game_id)
        if not session:
            return []

        species_id = session.player_to_species.get(player_id)
        if not species_id:
            return []

        dino = session.state.get_dino(dino_id)
        if not dino or dino.species_id != species_id:
            return []

        return session.engine.get_legal_actions(session.state, dino_id)

    def list_games(self) -> list[GameSummary]:
        summaries = []
        for gid, session in self.games.items():
            summaries.append(GameSummary(
                game_id=gid,
                phase=session.state.phase,
                turn=session.state.turn,
                max_turns=session.state.max_turns,
                player_count=len(session.player_to_species),
                species_names=[
                    sp.name for sp in session.state.species.values()
                ],
                persistent=session.persistent,
            ))
        return summaries

    def get_spectator_state(self, game_id: str) -> GameStateResponse | None:
        """Full game state with no fog of war — for spectators."""
        session = self.games.get(game_id)
        if not session:
            return None

        gm = session.state.game_map
        visible_cells = []
        for y in range(gm.height):
            for x in range(gm.width):
                cell = gm.get_cell(x, y)
                visible_cells.append(CellResponse(
                    x=x, y=y,
                    cell_type=cell.cell_type.value,
                    energy=cell.energy,
                    max_energy=cell.max_energy,
                ))

        dinos = []
        for sp in session.state.species.values():
            for d in sp.alive_dinos:
                dinos.append(DinoResponse(
                    id=d.id,
                    species_id=sp.id,
                    species_name=sp.name,
                    diet=sp.diet.value,
                    x=d.x, y=d.y,
                    dimension=d.dimension,
                    energy=d.energy,
                    max_energy=d.max_energy,
                    age=d.age,
                    max_lifespan=d.max_lifespan,
                    is_mine=False,
                ))

        eggs = []
        for sp in session.state.species.values():
            for e in sp.eggs:
                eggs.append(EggResponse(
                    x=e.x, y=e.y, hatch_turn=e.hatch_turn, is_mine=False,
                ))

        return GameStateResponse(
            game_id=game_id,
            turn=session.state.turn,
            max_turns=session.state.max_turns,
            phase=session.state.phase,
            visible_cells=visible_cells,
            dinosaurs=dinos,
            eggs=eggs,
            scores=self._build_scores(session),
        )

    # --- WebSocket management ---

    def subscribe_spectator(self, game_id: str, ws: WebSocket) -> None:
        """Subscribe a spectator (not tied to a player)."""
        session = self.games.get(game_id)
        if not session:
            return
        if "__spectators__" not in session.subscribers:
            session.subscribers["__spectators__"] = []
        session.subscribers["__spectators__"].append(ws)

    def unsubscribe_spectator(self, game_id: str, ws: WebSocket) -> None:
        session = self.games.get(game_id)
        if not session:
            return
        ws_list = session.subscribers.get("__spectators__", [])
        if ws in ws_list:
            ws_list.remove(ws)

    def subscribe(self, game_id: str, player_id: str, ws: WebSocket) -> None:
        session = self.games.get(game_id)
        if not session:
            return
        if player_id not in session.subscribers:
            session.subscribers[player_id] = []
        session.subscribers[player_id].append(ws)

    def unsubscribe(self, game_id: str, player_id: str, ws: WebSocket) -> None:
        session = self.games.get(game_id)
        if not session:
            return
        ws_list = session.subscribers.get(player_id, [])
        if ws in ws_list:
            ws_list.remove(ws)

    async def _broadcast(self, session: GameSession, message: dict) -> None:
        """Send a message to all subscribers of a game."""
        for ws_list in session.subscribers.values():
            for ws in ws_list:
                try:
                    await ws.send_json(message)
                except Exception:
                    pass

    def _build_events(self, session: GameSession, result) -> list[GameEvent]:
        """Build human-readable events from a TurnResult."""
        if result is None:
            return []
        events: list[GameEvent] = []

        # Hatches
        for dino_id in result.hatches:
            sp = session.state.get_species_for_dino(dino_id)
            name = sp.name if sp else "Unknown"
            events.append(GameEvent(kind="hatch", species_name=name,
                                    detail=f"{name} egg hatched"))

        # Combats
        for c in result.combats:
            winner_sp = session.state.get_species_for_dino(c.winner_id)
            loser_sp = session.state.get_species_for_dino(c.loser_id)
            w_name = winner_sp.name if winner_sp else "Unknown"
            l_name = loser_sp.name if loser_sp else "Unknown"
            events.append(GameEvent(kind="combat", species_name=w_name,
                                    detail=f"{w_name} killed {l_name} (+{int(c.energy_transferred)} energy)"))

        # Deaths (non-combat — old age, starvation)
        combat_deaths = {c.loser_id for c in result.combats}
        for dino_id in result.deaths:
            if dino_id in combat_deaths:
                continue  # already covered by combat event
            sp = session.state.get_species_for_dino(dino_id)
            if not sp:
                # Dino might be dead already, search all species
                for s in session.state.species.values():
                    for d in s.dinosaurs:
                        if d.id == dino_id:
                            sp = s
                            break
            name = sp.name if sp else "Unknown"
            events.append(GameEvent(kind="death", species_name=name,
                                    detail=f"{name} dino died"))

        return events

    def _build_scores(self, session: GameSession) -> list[SpeciesScore]:
        return [
            SpeciesScore(
                species_id=sp.id,
                name=sp.name,
                diet=sp.diet.value,
                score=sp.score,
                dino_count=sp.dino_count,
            )
            for sp in session.state.species.values()
        ]

    def _build_replay_frame(self, session: GameSession, result, events: list[GameEvent] | None = None) -> ReplayFrame:
        """Snapshot the current state as a replay frame."""
        dinos = []
        for sp in session.state.species.values():
            for d in sp.alive_dinos:
                dinos.append(DinoResponse(
                    id=d.id, species_id=sp.id, species_name=sp.name,
                    diet=sp.diet.value, x=d.x, y=d.y,
                    dimension=d.dimension, energy=d.energy,
                    max_energy=d.max_energy, age=d.age,
                    max_lifespan=d.max_lifespan, is_mine=False,
                ))

        eggs = []
        for sp in session.state.species.values():
            for e in sp.eggs:
                eggs.append(EggResponse(
                    x=e.x, y=e.y, hatch_turn=e.hatch_turn, is_mine=False,
                ))

        return ReplayFrame(
            turn=session.state.turn,
            phase=session.state.phase,
            dinosaurs=dinos,
            eggs=eggs,
            scores=self._build_scores(session),
            combats=len(result.combats) if result else 0,
            deaths=len(result.deaths) if result else 0,
            hatches=len(result.hatches) if result else 0,
            events=events or [],
        )

    def get_replay(self, game_id: str) -> ReplayResponse | None:
        """Build the full replay for a game."""
        session = self.games.get(game_id)
        if not session:
            return None

        gm = session.state.game_map
        cells = [
            CellResponse(
                x=x, y=y,
                cell_type=gm.get_cell(x, y).cell_type.value,
                energy=gm.get_cell(x, y).max_energy,  # show max for static map
                max_energy=gm.get_cell(x, y).max_energy,
            )
            for y in range(gm.height)
            for x in range(gm.width)
        ]

        return ReplayResponse(
            game_id=game_id,
            max_turns=session.state.max_turns,
            map_width=gm.width,
            map_height=gm.height,
            cells=cells,
            frames=session.replay_frames,
        )
