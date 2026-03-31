// REST API client

// Set via VITE_API_URL in .env (defaults to backend at localhost:8000)
const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

let authToken: string | null = null;

export function setToken(token: string | null) {
  authToken = token;
  if (token) {
    localStorage.setItem('dino_token', token);
  } else {
    localStorage.removeItem('dino_token');
  }
}

export function getToken(): string | null {
  if (!authToken) {
    authToken = localStorage.getItem('dino_token');
  }
  return authToken;
}

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };

  const token = getToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `API error: ${res.status}`);
  }

  return res.json();
}

// Auth
export const register = (username: string) =>
  apiFetch<{ player_id: string; token: string }>('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify({ username }),
  });

// Lobby
export const createGame = (opts: { width?: number; height?: number; max_turns?: number; seed?: number; turn_timeout?: number } = {}) =>
  apiFetch<import('./types').GameSummary>('/api/games', {
    method: 'POST',
    body: JSON.stringify(opts),
  });

export const listGames = () =>
  apiFetch<import('./types').GameSummary[]>('/api/games');

export const getGame = (gameId: string) =>
  apiFetch<import('./types').GameSummary>(`/api/games/${gameId}`);

export const joinGame = (gameId: string, speciesName: string, diet: import('./types').DietType) =>
  apiFetch<import('./types').JoinGameResponse>(`/api/games/${gameId}/join`, {
    method: 'POST',
    body: JSON.stringify({ species_name: speciesName, diet }),
  });

export const startGame = (gameId: string) =>
  apiFetch<{ status: string }>(`/api/games/${gameId}/start`, { method: 'POST' });

// Game
export const getGameState = (gameId: string) =>
  apiFetch<import('./types').GameStateResponse>(`/api/games/${gameId}/state`);

export const submitActions = (gameId: string, actions: import('./types').ActionRequest[]) =>
  apiFetch<import('./types').SubmitActionsResponse>(`/api/games/${gameId}/actions`, {
    method: 'POST',
    body: JSON.stringify({ actions }),
  });

export const getScores = (gameId: string) =>
  apiFetch<import('./types').SpeciesScore[]>(`/api/games/${gameId}/scores`);

export const getLegalActions = (gameId: string, dinoId: string) =>
  apiFetch<import('./types').LegalActionsResponse>(`/api/games/${gameId}/legal-actions/${dinoId}`);

// Spectator (no auth required)
export const getSpectatorState = (gameId: string) =>
  apiFetch<import('./types').GameStateResponse>(`/api/games/${gameId}/spectate`);

export const getReplay = (gameId: string) =>
  apiFetch<import('./types').ReplayResponse>(`/api/games/${gameId}/replay`);

export { BASE_URL };
