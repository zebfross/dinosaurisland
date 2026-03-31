import { useState } from 'react';
import { register, setToken } from '../../api/client';
import { useGameStore } from '../../state/gameStore';

export function LoginScreen() {
  const [username, setUsername] = useState('');
  const [error, setError] = useState('');
  const { setAuth } = useGameStore();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim()) return;

    try {
      const resp = await register(username.trim());
      setToken(resp.token);
      setAuth(resp.token, resp.player_id, username.trim());
    } catch (err: any) {
      const msg = err.message || String(err);
      if (msg.includes('Failed to fetch') || msg.includes('NetworkError') || msg.includes('API error')) {
        setError('Cannot reach server. Make sure the backend is running.');
      } else {
        setError(msg);
      }
    }
  };

  return (
    <div className="flex items-center justify-center h-screen bg-background grid-pattern">
      <div className="bg-surface-container border border-outline-variant/30 p-12 w-[400px] text-center">
        <h1 className="text-primary text-3xl font-black tracking-tighter font-headline uppercase mb-1">
          Dinosaur_Island
        </h1>
        <p className="text-on-surface-variant text-sm font-mono mb-8">
          // Turn-based survival game
        </p>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <input
            type="text"
            placeholder="ENTER_CALLSIGN"
            value={username}
            onChange={e => setUsername(e.target.value)}
            className="w-full px-4 py-3 bg-surface-container-highest border border-outline-variant/30 text-on-surface font-mono text-sm outline-none focus:border-primary placeholder:text-on-surface-variant/40 uppercase tracking-wider"
          />
          <button
            type="submit"
            className="w-full py-3 bg-primary text-on-primary font-headline font-bold text-sm tracking-widest uppercase hover:brightness-110 active:scale-[0.98] duration-75"
          >
            Initialize
          </button>
        </form>

        {error && (
          <p className="text-error text-xs font-mono mt-4">{error}</p>
        )}

        <p className="text-on-surface-variant/40 text-[10px] font-mono mt-6 uppercase">
          Bots connect via REST API // This is the spectator interface
        </p>
      </div>
    </div>
  );
}
