import { useRef, useEffect } from 'react';
import type { ReplayFrame } from '../../api/types';

interface ReplayEventLogProps {
  frames: ReplayFrame[];
  currentFrame: number;
}

export function ReplayEventLog({ frames, currentFrame }: ReplayEventLogProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [currentFrame]);

  const kindColors: Record<string, string> = {
    hatch: 'text-success',
    combat: 'text-warning',
    death: 'text-error',
  };

  const events: { turn: number; text: string; cls: string }[] = [];
  for (let i = 0; i <= currentFrame && i < frames.length; i++) {
    const f = frames[i];

    for (const ev of (f.events || [])) {
      events.push({ turn: f.turn, text: ev.detail, cls: kindColors[ev.kind] || 'text-on-surface-variant' });
    }

    // Scoreboard checkpoint every 25 turns
    if (f.turn % 25 === 0) {
      const scoreboard = f.scores
        .filter(s => s.score > 0)
        .sort((a, b) => b.score - a.score)
        .map(s => `${s.name}: ${s.score}`)
        .join(', ');
      if (scoreboard) events.push({ turn: f.turn, text: `Scores: ${scoreboard}`, cls: 'text-on-surface-variant/60' });
    }
  }

  const current = frames[currentFrame];
  const prev = currentFrame > 0 ? frames[currentFrame - 1] : null;

  let scoreSummary = '';
  if (current && prev) {
    const parts: string[] = [];
    const prevScores = new Map(prev.scores.map(s => [s.species_id, s.score]));
    for (const s of current.scores) {
      const delta = s.score - (prevScores.get(s.species_id) ?? 0);
      if (delta > 0) parts.push(`${s.name} +${delta}`);
    }
    if (parts.length > 0) scoreSummary = parts.join(', ');
  }

  return (
    <div className="flex-grow px-6 pb-4">
      <h3 className="text-on-surface-variant/60 font-bold uppercase tracking-widest text-xs mb-4 font-headline">
        Event_Log
      </h3>

      {current && (
        <div className="bg-primary/10 border border-primary/30 p-3 mb-4">
          <div className="text-[10px] text-primary uppercase font-bold font-mono mb-1">Current Event Cycle</div>
          <div className="text-xs text-on-surface font-mono">
            T{current.turn}: {current.dinosaurs.length} dinos alive
            {current.combats > 0 && `, ${current.combats} combat`}
            {current.deaths > 0 && `, ${current.deaths} death`}
            {current.hatches > 0 && `, ${current.hatches} hatch`}
          </div>
          {scoreSummary && (
            <div className="text-[10px] text-success font-mono mt-1">{scoreSummary}</div>
          )}
        </div>
      )}

      <div ref={scrollRef} className="overflow-auto max-h-48 space-y-2 text-[11px] font-mono">
        {events.length === 0 && (
          <div className="text-on-surface-variant/50">Awaiting events...</div>
        )}
        {events.map((ev, i) => (
          <div key={i} className="flex gap-2">
            <span className="text-on-surface-variant/40">T{ev.turn}:</span>
            <span className={ev.cls}>{ev.text}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
