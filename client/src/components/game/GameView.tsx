import { useEffect, useRef, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { GameCanvas } from './GameCanvas';
import { SpeciesPanel } from './SpeciesPanel';
import { EventLog } from './EventLog';
import { ReplayEventLog } from './ReplayEventLog';
import { TurnIndicator } from './TurnIndicator';
import { ReplayControls } from './ReplayControls';
import { useGameStore } from '../../state/gameStore';
import { getSpectatorState, getReplay } from '../../api/client';
import { GameWebSocket } from '../../api/websocket';
import type { WsMessage, ReplayResponse } from '../../api/types';

export function GameView() {
  const { gameId } = useParams<{ gameId: string }>();
  const navigate = useNavigate();
  const wsRef = useRef<GameWebSocket | null>(null);

  const {
    phase, applyState, addEvent,
    setDeadline, updateScores, setPhase, leaveGame,
  } = useGameStore();

  const [replay, setReplay] = useState<ReplayResponse | null>(null);
  const [replayFrame, setReplayFrame] = useState(0);
  const [isReplayMode, setIsReplayMode] = useState(false);

  useEffect(() => {
    if (!gameId) return;
    getSpectatorState(gameId)
      .then(state => {
        applyState(state);
        if (state.phase === 'finished') loadReplay();
        else connectLive();
      })
      .catch(err => addEvent(`Failed to load game: ${err.message}`));

    return () => {
      wsRef.current?.disconnect(); wsRef.current = null;
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    };
  }, [gameId]);

  const loadReplay = useCallback(() => {
    if (!gameId) return;
    getReplay(gameId).then(r => {
      setReplay(r);
      setIsReplayMode(true);
      setReplayFrame(0);
      useGameStore.setState({ eventLog: [] });
      if (r.frames.length > 0) {
        const f = r.frames[0];
        applyState({ game_id: r.game_id, turn: f.turn, max_turns: r.max_turns, phase: f.phase, visible_cells: r.cells, dinosaurs: f.dinosaurs, eggs: f.eggs, scores: f.scores });
      }
    }).catch(err => addEvent(`Failed to load replay: ${err.message}`));
  }, [gameId]);

  const pollRef = useRef<number | null>(null);

  const startPolling = useCallback(() => {
    if (!gameId || pollRef.current) return;
    let lastTurn = -1;
    pollRef.current = window.setInterval(async () => {
      try {
        const state = await getSpectatorState(gameId);
        if (state.turn !== lastTurn) {
          lastTurn = state.turn;
          applyState(state);
          if (state.turn > 0) addEvent(`Turn ${state.turn}`);
        }
        if (state.phase === 'finished') {
          if (pollRef.current) clearInterval(pollRef.current);
          pollRef.current = null;
          addEvent('Game over!');
          setTimeout(loadReplay, 500);
        }
      } catch { /* ignore poll errors */ }
    }, 2000);
  }, [gameId]);

  const connectLive = useCallback(() => {
    if (!gameId) return;
    const ws = new GameWebSocket(gameId, true);
    wsRef.current = ws;
    let wsConnected = false;

    let prevScores = new Map<string, number>();

    ws.onMessage((msg: WsMessage) => {
      wsConnected = true;
      switch (msg.type) {
        case 'state_update': applyState(msg.state); break;
        case 'turn_start': setDeadline(msg.deadline_seconds); break;
        case 'turn_result': {
          // Score deltas
          const parts: string[] = [];
          for (const s of msg.scores) {
            const prev = prevScores.get(s.species_id) ?? 0;
            const delta = s.score - prev;
            if (delta > 0) parts.push(`${s.name} +${delta}`);
            prevScores.set(s.species_id, s.score);
          }
          if (parts.length > 0) addEvent(`T${msg.turn}: ${parts.join(', ')}`);
          if (msg.hatches > 0) addEvent(`T${msg.turn}: ${msg.hatches} egg(s) hatched`);
          if (msg.combats > 0) addEvent(`T${msg.turn}: ${msg.combats} combat(s)`);
          if (msg.deaths > 0) addEvent(`T${msg.turn}: ${msg.deaths} death(s)`);
          updateScores(msg.scores);
          break;
        }
        case 'phase_change':
          setPhase(msg.phase);
          if (msg.phase === 'finished') {
            addEvent('Game over!');
            const winner = msg.final_scores.sort((a, b) => b.score - a.score)[0];
            if (winner) addEvent(`Winner: ${winner.name} with ${winner.score} points`);
            setTimeout(loadReplay, 500);
          }
          break;
        case 'error': addEvent(`Server: ${msg.message}`); break;
      }
    });

    ws.connect();

    // If WebSocket doesn't connect within 3s, fall back to polling
    setTimeout(() => {
      if (!wsConnected) {
        ws.disconnect();
        wsRef.current = null;
        addEvent('WebSocket unavailable, using polling');
        startPolling();
      }
    }, 3000);
  }, [gameId]);

  const handleFrameChange = useCallback((frame: number) => {
    if (!replay) return;
    const clamped = Math.max(0, Math.min(replay.frames.length - 1, frame));
    setReplayFrame(clamped);
    const f = replay.frames[clamped];
    if (f) applyState({ game_id: replay.game_id, turn: f.turn, max_turns: replay.max_turns, phase: f.phase, visible_cells: replay.cells, dinosaurs: f.dinosaurs, eggs: f.eggs, scores: f.scores });
  }, [replay]);

  return (
    <div className="flex h-screen bg-background text-on-background font-body overflow-hidden">
      {/* Left: Canvas area */}
      <section className="w-3/4 flex flex-col relative border-r border-outline-variant/20">
        <TurnIndicator />
        <div className="flex-grow relative grid-pattern min-h-0">
          <GameCanvas />

          {/* Status badge */}
          {!isReplayMode && (
            <div className="absolute bottom-4 left-4 bg-surface-container-highest/80 backdrop-blur-sm px-3 py-1.5 border border-outline-variant/30 text-[10px] font-mono text-on-surface-variant uppercase">
              {phase === 'active' ? 'Live_Feed // Scroll to zoom, drag to pan' :
               phase === 'waiting' ? 'Awaiting_Bots...' : 'Match_Complete'}
            </div>
          )}
        </div>

        {/* Replay controls at bottom */}
        {isReplayMode && replay && (
          <ReplayControls replay={replay} currentFrame={replayFrame} onFrameChange={handleFrameChange} />
        )}
      </section>

      {/* Right: Sidebar */}
      <aside className="w-1/4 bg-surface-container h-full flex flex-col border-l border-outline-variant/20 font-mono">
        <div className="flex-grow flex flex-col gap-4 overflow-y-auto">
          <SpeciesPanel />
          {isReplayMode && replay ? (
            <ReplayEventLog frames={replay.frames} currentFrame={replayFrame} />
          ) : (
            <EventLog />
          )}
        </div>

        <div className="p-4 bg-surface-container-low border-t border-outline-variant/20">
          <button
            onClick={() => { leaveGame(); navigate('/'); }}
            className="w-full bg-surface-container-highest text-on-surface-variant py-3 text-xs uppercase tracking-wider hover:bg-surface-container-high hover:text-on-surface flex items-center justify-center gap-2 border border-outline-variant/30 active:opacity-80 transition-all font-mono"
          >
            <span className="material-symbols-outlined text-sm">arrow_back</span>
            Back_to_Lobby
          </button>
        </div>
      </aside>
    </div>
  );
}
