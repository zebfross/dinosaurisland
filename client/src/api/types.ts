// TypeScript types mirroring server schemas

export type GamePhase = 'waiting' | 'active' | 'finished';
export type DietType = 'herbivore' | 'carnivore';
export type ActionType = 'move' | 'grow' | 'lay_egg' | 'rest';
export type CellTypeStr = 'water' | 'plain' | 'vegetation' | 'carrion';

export interface RegisterResponse {
  player_id: string;
  token: string;
}

export interface GameSummary {
  game_id: string;
  phase: GamePhase;
  turn: number;
  max_turns: number;
  player_count: number;
  species_names: string[];
  persistent?: boolean;
}

export interface JoinGameResponse {
  species_id: string;
  game_id: string;
}

export interface CellResponse {
  x: number;
  y: number;
  cell_type: CellTypeStr;
  energy: number;
  max_energy: number;
}

export interface DinoResponse {
  id: string;
  species_id: string;
  species_name: string;
  diet: string;
  x: number;
  y: number;
  dimension: number;
  energy: number;
  max_energy: number;
  age: number;
  max_lifespan: number;
  is_mine: boolean;
}

export interface EggResponse {
  x: number;
  y: number;
  hatch_turn: number;
  is_mine: boolean;
}

export interface SpeciesScore {
  species_id: string;
  name: string;
  diet: string;
  score: number;
  dino_count: number;
}

export interface GameStateResponse {
  game_id: string;
  turn: number;
  max_turns: number;
  phase: GamePhase;
  visible_cells: CellResponse[];
  dinosaurs: DinoResponse[];
  eggs: EggResponse[];
  scores: SpeciesScore[];
}

export interface GameEvent {
  kind: string; // "hatch", "death", "combat"
  species_name: string;
  detail: string;
}

// Replay
export interface ReplayFrame {
  turn: number;
  phase: GamePhase;
  dinosaurs: DinoResponse[];
  eggs: EggResponse[];
  scores: SpeciesScore[];
  combats: number;
  deaths: number;
  hatches: number;
  events: GameEvent[];
}

export interface ReplayResponse {
  game_id: string;
  max_turns: number;
  map_width: number;
  map_height: number;
  cells: CellResponse[];
  frames: ReplayFrame[];
}

export interface ActionRequest {
  dino_id: string;
  action_type: ActionType;
  target_x?: number | null;
  target_y?: number | null;
}

export interface SubmitActionsResponse {
  accepted: number;
  errors: { dino_id: string; reason: string }[];
}

export interface LegalActionsResponse {
  dino_id: string;
  actions: ActionRequest[];
}

// WebSocket message types
export interface WsTurnStart {
  type: 'turn_start';
  turn: number;
  deadline_seconds: number;
}

export interface WsStateUpdate {
  type: 'state_update';
  state: GameStateResponse;
}

export interface WsTurnResult {
  type: 'turn_result';
  turn: number;
  combats: number;
  deaths: number;
  hatches: number;
  events: GameEvent[];
  scores: SpeciesScore[];
}

export interface WsPhaseChange {
  type: 'phase_change';
  phase: GamePhase;
  final_scores: SpeciesScore[];
}

export interface WsActionsAccepted {
  type: 'actions_accepted';
  accepted: number;
  errors: { dino_id: string; reason: string }[];
}

export interface WsError {
  type: 'error';
  message: string;
}

export type WsMessage =
  | WsTurnStart
  | WsStateUpdate
  | WsTurnResult
  | WsPhaseChange
  | WsActionsAccepted
  | WsError
  | { type: 'pong' };
