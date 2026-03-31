// Zustand store — spectator-focused

import { create } from 'zustand';
import type {
  GamePhase,
  GameStateResponse,
  DinoResponse,
  CellResponse,
  EggResponse,
  SpeciesScore,
  GameSummary,
} from '../api/types';

interface GameStore {
  // Auth (still needed to create/manage games via API)
  token: string | null;
  playerId: string | null;
  username: string | null;
  setAuth: (token: string, playerId: string, username: string) => void;
  clearAuth: () => void;

  // Lobby
  games: GameSummary[];
  setGames: (games: GameSummary[]) => void;

  // Current game (spectator view)
  gameId: string | null;
  turn: number;
  maxTurns: number;
  phase: GamePhase;
  visibleCells: CellResponse[];
  dinosaurs: DinoResponse[];
  eggs: EggResponse[];
  scores: SpeciesScore[];
  deadline: number | null;
  turnStartTime: number | null;

  // UI state
  selectedDinoId: string | null;
  eventLog: string[];

  // Actions
  setGameId: (gameId: string) => void;
  applyState: (state: GameStateResponse) => void;
  selectDino: (id: string | null) => void;
  addEvent: (msg: string) => void;
  setDeadline: (seconds: number) => void;
  updateScores: (scores: SpeciesScore[]) => void;
  setPhase: (phase: GamePhase) => void;
  leaveGame: () => void;
}

export const useGameStore = create<GameStore>((set, get) => ({
  // Auth
  token: localStorage.getItem('dino_token'),
  playerId: localStorage.getItem('dino_player_id'),
  username: localStorage.getItem('dino_username'),
  setAuth: (token, playerId, username) => {
    localStorage.setItem('dino_token', token);
    localStorage.setItem('dino_player_id', playerId);
    localStorage.setItem('dino_username', username);
    set({ token, playerId, username });
  },
  clearAuth: () => {
    localStorage.removeItem('dino_token');
    localStorage.removeItem('dino_player_id');
    localStorage.removeItem('dino_username');
    set({ token: null, playerId: null, username: null });
  },

  // Lobby
  games: [],
  setGames: (games) => set({ games }),

  // Current game
  gameId: null,
  turn: 0,
  maxTurns: 120,
  phase: 'waiting',
  visibleCells: [],
  dinosaurs: [],
  eggs: [],
  scores: [],
  deadline: null,
  turnStartTime: null,

  // UI
  selectedDinoId: null,
  eventLog: [],

  setGameId: (gameId) => set({
    gameId,
    turn: 0,
    phase: 'waiting',
    visibleCells: [],
    dinosaurs: [],
    eggs: [],
    scores: [],
    selectedDinoId: null,
    eventLog: [],
  }),

  applyState: (state) => {
    set({
      turn: state.turn,
      maxTurns: state.max_turns,
      phase: state.phase,
      visibleCells: state.visible_cells,
      dinosaurs: state.dinosaurs,
      eggs: state.eggs,
      scores: state.scores,
    });
  },

  selectDino: (id) => set({ selectedDinoId: id }),

  addEvent: (msg) => {
    const log = [msg, ...get().eventLog].slice(0, 100);
    set({ eventLog: log });
  },

  setDeadline: (seconds) => set({ deadline: seconds, turnStartTime: Date.now() }),

  updateScores: (scores) => set({ scores }),

  setPhase: (phase) => set({ phase }),

  leaveGame: () => set({
    gameId: null,
    turn: 0,
    phase: 'waiting',
    visibleCells: [],
    dinosaurs: [],
    eggs: [],
    scores: [],
    selectedDinoId: null,
    eventLog: [],
    deadline: null,
    turnStartTime: null,
  }),
}));
