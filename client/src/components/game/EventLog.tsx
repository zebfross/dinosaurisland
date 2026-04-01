import { useRef, useEffect } from 'react';
import { useGameStore } from '../../state/gameStore';

export function EventLog() {
  const { eventLog } = useGameStore();
  const scrollRef = useRef<HTMLDivElement>(null);
  const isAtBottomRef = useRef(true);

  // Track whether user is scrolled to bottom
  const handleScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    isAtBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 20;
  };

  // Only auto-scroll if already at bottom
  useEffect(() => {
    if (isAtBottomRef.current && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [eventLog]);

  const chronological = [...eventLog].reverse();

  return (
    <div className="flex-grow px-6 pb-4">
      <h3 className="text-on-surface-variant/60 font-bold uppercase tracking-widest text-xs mb-4 font-headline">
        Event_Log
      </h3>
      <div ref={scrollRef} onScroll={handleScroll} className="overflow-auto max-h-48 space-y-2 text-[11px] font-mono">
        {chronological.length === 0 && (
          <div className="text-on-surface-variant/50">Awaiting events...</div>
        )}
        {chronological.map((msg, i) => (
          <div key={i} className="flex gap-2">
            <span className="text-on-surface-variant">{msg}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
