import { useEffect, useState } from 'react';
import { useGameStore } from '../../state/gameStore';

export function TurnIndicator() {
  const { turn, maxTurns, phase, deadline, turnStartTime } = useGameStore();
  const [remaining, setRemaining] = useState<number | null>(null);

  useEffect(() => {
    if (deadline == null || turnStartTime == null) {
      setRemaining(null);
      return;
    }
    const tick = () => {
      const elapsed = (Date.now() - turnStartTime) / 1000;
      setRemaining(Math.max(0, Math.round(deadline - elapsed)));
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [deadline, turnStartTime]);

  return (
    <div className="bg-surface-container-high px-6 py-3 flex justify-between items-center border-b border-outline-variant/10">
      <div className="flex items-center gap-4">
        <span className="font-mono text-primary text-lg font-bold tracking-tighter">
          TURN {turn} / {maxTurns}
        </span>
        {remaining !== null && phase === 'active' && (
          <>
            <div className="h-4 w-px bg-outline-variant" />
            <div className="flex items-center gap-2">
              <span className={`material-symbols-outlined text-sm ${remaining <= 5 ? 'text-error' : 'text-on-surface-variant'}`}>timer</span>
              <span className={`font-mono text-sm ${remaining <= 5 ? 'text-error' : 'text-on-surface-variant'}`}>
                REMAINING: 00:{String(remaining).padStart(2, '0')}
              </span>
            </div>
          </>
        )}
      </div>
      <div className="flex gap-2">
        <div className="bg-surface-container-highest px-3 py-1 flex items-center gap-2 border border-outline-variant/30">
          <div className={`w-2 h-2 ${
            phase === 'active' ? 'bg-primary animate-pulse' :
            phase === 'finished' ? 'bg-error' : 'bg-outline'
          }`} />
          <span className="text-[10px] font-mono uppercase text-on-surface-variant">
            {phase === 'active' ? 'System_Live' : phase === 'finished' ? 'Match_Complete' : 'Awaiting_Bots'}
          </span>
        </div>
      </div>
    </div>
  );
}
