import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { listGames, createGame, startGame } from '../../api/client';
import { useGameStore } from '../../state/gameStore';
import type { GameSummary } from '../../api/types';

export function LobbyView() {
  const navigate = useNavigate();
  const { username, clearAuth, games, setGames, setGameId } = useGameStore();
  const [showCreate, setShowCreate] = useState(false);
  const [error, setError] = useState('');

  const refreshGames = () => { listGames().then(setGames).catch(() => {}); };

  useEffect(() => {
    refreshGames();
    const id = setInterval(refreshGames, 3000);
    return () => clearInterval(id);
  }, []);

  const handleSpectate = (game: GameSummary) => {
    setGameId(game.game_id);
    navigate(`/game/${game.game_id}`);
  };

  const handleStart = async (gameId: string) => {
    try { await startGame(gameId); refreshGames(); }
    catch (err: any) { setError(err.message); }
  };

  return (
    <div className="min-h-screen bg-background text-on-background font-body flex flex-col">
      {/* Header */}
      <header className="bg-surface-container flex justify-between items-center px-6 py-4 border-b border-outline-variant/20">
        <div className="flex items-center gap-8">
          <span className="text-xl font-black text-primary tracking-tighter font-headline uppercase">
            Dinosaur_Island_Spectator
          </span>
          <nav className="hidden md:flex gap-6 items-center">
            <span className="font-headline tracking-wider uppercase font-bold text-primary border-b-2 border-primary pb-1 text-sm">
              Lobby
            </span>
          </nav>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-on-surface-variant text-xs font-mono uppercase">user: {username}</span>
          <button
            onClick={() => { clearAuth(); navigate('/'); }}
            className="bg-surface-container-highest text-on-surface-variant px-3 py-1.5 text-xs uppercase tracking-wider font-mono border border-outline-variant/30 hover:text-on-surface hover:bg-surface-container-high"
          >
            Logout
          </button>
        </div>
      </header>

      <div className="max-w-4xl mx-auto w-full px-6 py-8">
        {error && (
          <div className="bg-error/10 border border-error/30 p-3 mb-6 flex justify-between items-center">
            <span className="text-error text-xs font-mono">{error}</span>
            <button onClick={() => setError('')} className="text-error hover:text-on-surface text-sm">x</button>
          </div>
        )}

        <div className="flex justify-between items-center mb-6">
          <h2 className="text-on-surface font-headline font-bold uppercase tracking-wider">Active_Games</h2>
          <button
            onClick={() => setShowCreate(!showCreate)}
            className="bg-primary text-on-primary px-5 py-2 font-headline font-bold text-sm tracking-widest uppercase hover:brightness-110 active:scale-95 duration-75"
          >
            {showCreate ? 'Cancel' : 'New_Game'}
          </button>
        </div>

        {showCreate && <CreateGamePanel onCreated={() => { setShowCreate(false); refreshGames(); }} />}

        {/* Persistent game — featured at top */}
        {games.filter(g => g.persistent).map(game => (
          <div key={game.game_id} className="bg-surface-container-high p-6 mb-6 border-l-4 border-primary">
            <div className="flex justify-between items-start">
              <div>
                <div className="flex items-center gap-3 mb-2">
                  <span className="font-headline font-bold text-primary text-lg uppercase">Persistent_Arena</span>
                  <div className="px-2 py-0.5 text-[10px] font-mono uppercase text-primary bg-primary/10 border border-primary/30">
                    Always Open
                  </div>
                </div>
                <div className="text-xs text-on-surface-variant font-mono">
                  {game.species_names.length > 0
                    ? `${game.species_names.length} species: ${game.species_names.join(' // ')}`
                    : 'No bots connected yet — be the first!'}
                  {' | '}Turn {game.turn}
                </div>
                <div className="text-[10px] text-on-surface-variant/50 font-mono mt-2">
                  Connect your bot to this game ID: {game.game_id}
                </div>
              </div>
              <button
                onClick={() => handleSpectate(game)}
                className="bg-primary text-on-primary px-5 py-2 font-headline font-bold text-sm tracking-widest uppercase hover:brightness-110 active:scale-95 duration-75"
              >
                Watch
              </button>
            </div>
          </div>
        ))}

        {/* Other games */}
        {games.filter(g => !g.persistent).length === 0 && games.filter(g => g.persistent).length > 0 && (
          <div className="text-on-surface-variant/50 text-center py-8 font-mono text-sm uppercase">
            No other games. Create one for a private match, or join the arena above.
          </div>
        )}

        {games.length === 0 && (
          <div className="text-on-surface-variant/50 text-center py-16 font-mono text-sm uppercase">
            No active games. Create one, then connect bots via the API.
          </div>
        )}

        <div className="flex flex-col gap-2">
          {games.filter(g => !g.persistent).map(game => (
            <div key={game.game_id} className="bg-surface-container-high p-5 flex justify-between items-center border-l-4 border-outline-variant/30 hover:border-primary/50 transition-colors">
              <div>
                <div className="font-mono font-bold text-on-surface text-sm">
                  MATCH_{game.game_id.slice(0, 8).toUpperCase()}
                </div>
                <div className="text-xs text-on-surface-variant font-mono mt-1">
                  {game.species_names.length > 0 ? game.species_names.join(' // ') : 'Awaiting bots'}
                  {' | '}Turn {game.turn}/{game.max_turns}
                </div>
              </div>
              <div className="flex gap-3 items-center">
                <div className={`px-2 py-0.5 text-[10px] font-mono uppercase border ${
                  game.phase === 'active' ? 'text-primary bg-primary/10 border-primary/30' :
                  game.phase === 'finished' ? 'text-error bg-error/10 border-error/30' :
                  'text-on-surface-variant bg-surface-container-highest border-outline-variant/30'
                }`}>
                  {game.phase}
                </div>
                {game.phase === 'waiting' && game.player_count > 0 && (
                  <button onClick={() => handleStart(game.game_id)} className="bg-surface-container-highest text-on-surface-variant px-3 py-1.5 text-xs uppercase font-mono border border-outline-variant/30 hover:text-primary hover:border-primary/30">
                    Start
                  </button>
                )}
                <button onClick={() => handleSpectate(game)} className="bg-surface-container-highest text-on-surface-variant px-3 py-1.5 text-xs uppercase font-mono border border-outline-variant/30 hover:text-primary hover:border-primary/30">
                  {game.phase === 'active' ? 'Watch' : game.phase === 'finished' ? 'Replay' : 'View'}
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function CreateGamePanel({ onCreated }: { onCreated: () => void }) {
  const [width, setWidth] = useState(30);
  const [height, setHeight] = useState(30);
  const [maxTurns, setMaxTurns] = useState(120);
  const [turnTimeout, setTurnTimeout] = useState(30);
  const [error, setError] = useState('');

  const handleCreate = async () => {
    try { await createGame({ width, height, max_turns: maxTurns, turn_timeout: turnTimeout }); onCreated(); }
    catch (err: any) { setError(err.message); }
  };

  return (
    <div className="bg-surface-container-high p-6 mb-6 border border-outline-variant/20">
      <h3 className="font-headline font-bold uppercase tracking-wider text-on-surface mb-1">New_Game</h3>
      <p className="text-on-surface-variant text-xs font-mono mb-4">
        Create a game, then have bots connect via the API to join and play.
      </p>

      <div className="grid grid-cols-2 gap-4">
        {[
          { label: 'Map_Width', value: width, set: setWidth },
          { label: 'Map_Height', value: height, set: setHeight },
          { label: 'Max_Turns', value: maxTurns, set: setMaxTurns },
          { label: 'Turn_Timeout', value: turnTimeout, set: setTurnTimeout },
        ].map(({ label, value, set }) => (
          <label key={label} className="flex flex-col gap-1">
            <span className="text-[10px] font-mono text-on-surface-variant uppercase">{label}</span>
            <input
              type="number"
              value={value}
              onChange={e => set(+e.target.value)}
              className="px-3 py-2 bg-surface-container-highest border border-outline-variant/30 text-on-surface font-mono text-sm outline-none focus:border-primary"
            />
          </label>
        ))}
      </div>

      {error && <p className="text-error text-xs font-mono mt-3">{error}</p>}

      <button onClick={handleCreate} className="mt-4 bg-primary text-on-primary px-6 py-2.5 font-headline font-bold text-sm tracking-widest uppercase hover:brightness-110 active:scale-95 duration-75">
        Initialize_Match
      </button>
    </div>
  );
}
