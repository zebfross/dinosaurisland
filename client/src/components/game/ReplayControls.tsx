import { useEffect, useRef, useState, useCallback } from 'react';
import type { ReplayResponse } from '../../api/types';

interface ReplayControlsProps {
  replay: ReplayResponse;
  currentFrame: number;
  onFrameChange: (frame: number) => void;
}

export function ReplayControls({ replay, currentFrame, onFrameChange }: ReplayControlsProps) {
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const intervalRef = useRef<number | null>(null);
  const frameRef = useRef(currentFrame);
  const totalFrames = replay.frames.length;

  frameRef.current = currentFrame;

  const stop = useCallback(() => {
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    setPlaying(false);
  }, []);

  const play = useCallback(() => {
    stop();
    setPlaying(true);
    intervalRef.current = window.setInterval(() => {
      const next = frameRef.current + 1;
      if (next >= totalFrames) { stop(); return; }
      onFrameChange(next);
    }, 1000 / speed);
  }, [speed, totalFrames, stop, onFrameChange]);

  useEffect(() => { if (playing) play(); }, [speed]);
  useEffect(() => () => stop(), [stop]);

  const frame = replay.frames[currentFrame];
  const pct = totalFrames > 1 ? (currentFrame / (totalFrames - 1)) * 100 : 0;

  return (
    <footer className="bg-surface-container/80 backdrop-blur-md border-t border-primary/10 flex flex-col px-12 py-3">
      {/* Scrubber track */}
      <div className="w-full h-6 flex items-center relative px-2 mb-2 cursor-pointer"
        onClick={e => {
          const rect = e.currentTarget.getBoundingClientRect();
          const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
          stop();
          onFrameChange(Math.round(ratio * (totalFrames - 1)));
        }}
      >
        <div className="w-full h-[2px] bg-surface-container-highest relative">
          <div className="absolute top-0 left-0 h-full bg-primary" style={{ width: `${pct}%` }} />
          <div className="absolute top-1/2 -translate-y-1/2 w-[2px] h-4 bg-primary shadow-[0_0_10px_#53ddfc]" style={{ left: `${pct}%` }} />
        </div>
      </div>

      <div className="flex justify-between items-center">
        {/* Playback controls */}
        <div className="flex items-center gap-6">
          <div className="flex gap-4 items-center">
            <button
              onClick={() => { stop(); onFrameChange(Math.max(0, currentFrame - 1)); }}
              disabled={currentFrame <= 0}
              className="text-on-surface-variant hover:bg-surface-container-highest p-2 active:scale-90 duration-75 flex flex-col items-center disabled:opacity-30"
            >
              <span className="material-symbols-outlined">fast_rewind</span>
              <span className="text-[10px] uppercase font-mono mt-1">Rewind</span>
            </button>

            <button
              onClick={() => {
                if (playing) { stop(); }
                else { if (currentFrame >= totalFrames - 1) onFrameChange(0); play(); }
              }}
              className="text-primary bg-primary/10 p-3 active:scale-90 duration-75 flex flex-col items-center border border-primary/20 hover:bg-primary/20"
            >
              <span className="material-symbols-outlined text-2xl">{playing ? 'pause' : 'play_arrow'}</span>
              <span className="text-[10px] uppercase font-mono mt-1 font-bold">{playing ? 'Pause' : 'Play'}</span>
            </button>

            <button
              onClick={() => { stop(); onFrameChange(Math.min(totalFrames - 1, currentFrame + 1)); }}
              disabled={currentFrame >= totalFrames - 1}
              className="text-on-surface-variant hover:bg-surface-container-highest p-2 active:scale-90 duration-75 flex flex-col items-center disabled:opacity-30"
            >
              <span className="material-symbols-outlined">fast_forward</span>
              <span className="text-[10px] uppercase font-mono mt-1">Forward</span>
            </button>
          </div>

          <div className="h-8 w-px bg-outline-variant/30" />

          {/* Speed selector */}
          <div className="flex gap-1 items-center">
            <span className="text-[9px] font-mono text-on-surface-variant/50 mr-2 uppercase">Playback_Speed:</span>
            {[0.5, 1, 2, 5, 10].map(s => (
              <button
                key={s}
                onClick={() => setSpeed(s)}
                className={`px-2 py-1 text-[10px] font-mono border ${
                  speed === s
                    ? 'text-primary bg-primary/10 border-primary/30'
                    : 'text-on-surface-variant hover:text-primary border-outline-variant/30'
                }`}
              >
                {s}x
              </button>
            ))}
          </div>
        </div>

        {/* Turn counter */}
        <div className="flex flex-col items-end">
          <span className="font-mono text-primary font-bold text-sm tracking-tighter uppercase">
            TURN {frame?.turn ?? 0} / {replay.max_turns}
          </span>
          <span className="font-mono text-[9px] text-on-surface-variant/40 uppercase">
            Frame {currentFrame + 1} / {totalFrames}
          </span>
        </div>
      </div>
    </footer>
  );
}
