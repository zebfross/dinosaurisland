import { useGameStore } from '../../state/gameStore';

const SPECIES_COLORS = [
  { border: 'border-primary', dot: 'bg-primary shadow-[0_0_4px_#53ddfc]', text: 'text-primary', badge: 'bg-primary/20 text-primary border-primary/30', bar: 'bg-primary', barAge: 'bg-primary-container' },
  { border: 'border-error', dot: 'bg-error shadow-[0_0_4px_#ff716c]', text: 'text-error', badge: 'bg-error/20 text-error border-error/30', bar: 'bg-error', barAge: 'bg-error-dim' },
  { border: 'border-warning', dot: 'bg-warning shadow-[0_0_4px_#eab308]', text: 'text-warning', badge: 'bg-warning/20 text-warning border-warning/30', bar: 'bg-warning', barAge: 'bg-warning' },
  { border: 'border-purple-400', dot: 'bg-purple-400 shadow-[0_0_4px_#a855f7]', text: 'text-purple-400', badge: 'bg-purple-400/20 text-purple-400 border-purple-400/30', bar: 'bg-purple-400', barAge: 'bg-purple-600' },
  { border: 'border-orange-400', dot: 'bg-orange-400 shadow-[0_0_4px_#f97316]', text: 'text-orange-400', badge: 'bg-orange-400/20 text-orange-400 border-orange-400/30', bar: 'bg-orange-400', barAge: 'bg-orange-600' },
  { border: 'border-emerald-400', dot: 'bg-emerald-400 shadow-[0_0_4px_#34d399]', text: 'text-emerald-400', badge: 'bg-emerald-400/20 text-emerald-400 border-emerald-400/30', bar: 'bg-emerald-400', barAge: 'bg-emerald-600' },
];

const speciesColorIndex = new Map<string, number>();
let nextColor = 0;
function getColor(speciesId: string) {
  if (!speciesColorIndex.has(speciesId)) {
    speciesColorIndex.set(speciesId, nextColor % SPECIES_COLORS.length);
    nextColor++;
  }
  return SPECIES_COLORS[speciesColorIndex.get(speciesId)!];
}

export function SpeciesPanel() {
  const { dinosaurs, scores, selectedDinoId, selectDino } = useGameStore();

  const speciesMap = new Map<string, { name: string; diet: string; dinos: typeof dinosaurs; score: number }>();
  for (const sc of scores) {
    speciesMap.set(sc.species_id, { name: sc.name, diet: sc.diet, dinos: [], score: sc.score });
  }
  for (const d of dinosaurs) {
    speciesMap.get(d.species_id)?.dinos.push(d);
  }

  const alive = [...speciesMap.entries()].filter(([, sp]) => sp.dinos.length > 0).sort((a, b) => b[1].score - a[1].score);
  const dead = [...speciesMap.entries()].filter(([, sp]) => sp.dinos.length === 0).sort((a, b) => b[1].score - a[1].score);

  return (
    <div className="p-6 flex flex-col gap-4">
      <h3 className="text-primary font-bold uppercase tracking-widest text-xs font-headline">
        Spectator_Mode
      </h3>

      {/* Alive species — full detail */}
      {alive.map(([speciesId, sp]) => {
        const c = getColor(speciesId);
        return (
          <div key={speciesId} className={`bg-surface-container-high p-4 border-l-4 ${c.border}`}>
            <div className="flex justify-between items-start mb-3">
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 ${c.dot}`} />
                <span className="text-on-surface font-bold font-mono text-sm">{sp.name}</span>
                <span className={`text-[10px] px-1 border ${c.badge}`}>
                  [{sp.diet === 'herbivore' ? 'H' : 'C'}]
                </span>
              </div>
              <div className={`${c.text} font-bold font-mono`}>{sp.score.toLocaleString()} pts</div>
            </div>

            <div className="space-y-3">
              {sp.dinos.map(d => {
                const energyPct = d.max_energy > 0 ? (d.energy / d.max_energy) * 100 : 0;
                const agePct = d.max_lifespan > 0 ? (d.age / d.max_lifespan) * 100 : 0;
                const isSelected = d.id === selectedDinoId;

                return (
                  <div
                    key={d.id}
                    onClick={() => selectDino(isSelected ? null : d.id)}
                    className={`text-[11px] text-on-surface-variant border-t border-outline-variant/10 pt-2 cursor-pointer
                      ${isSelected ? 'bg-primary/5 -mx-2 px-2 py-1' : 'hover:bg-surface-container-highest/50'}`}
                  >
                    <div className="flex justify-between mb-1 font-mono">
                      <span>{d.id.slice(0, 6).toUpperCase()} (v{d.dimension})</span>
                      <span className="text-on-surface">@ {d.x}, {d.y}</span>
                    </div>
                    <div className="grid grid-cols-2 gap-2 mt-2">
                      <div className="space-y-1">
                        <div className="flex justify-between text-[8px] uppercase font-mono">
                          <span>Energy</span>
                          <span>{Math.round(energyPct)}%</span>
                        </div>
                        <div className="h-1 bg-surface-container-highest w-full">
                          <div className={`h-full ${energyPct > 60 ? c.bar : energyPct > 30 ? 'bg-warning' : 'bg-error'}`} style={{ width: `${energyPct}%` }} />
                        </div>
                      </div>
                      <div className="space-y-1">
                        <div className="flex justify-between text-[8px] uppercase font-mono">
                          <span>Age</span>
                          <span>{d.age}/{d.max_lifespan}</span>
                        </div>
                        <div className="h-1 bg-surface-container-highest w-full">
                          <div className={`h-full ${c.barAge}`} style={{ width: `${agePct}%` }} />
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}

      {/* Dead species — compact scoreboard */}
      {dead.length > 0 && (
        <div className="text-[11px] font-mono">
          <div className="text-on-surface-variant/40 uppercase tracking-widest mb-2">Eliminated</div>
          {dead.map(([speciesId, sp]) => {
            const c = getColor(speciesId);
            return (
              <div key={speciesId} className="flex justify-between py-1 text-on-surface-variant/50">
                <div className="flex items-center gap-2">
                  <div className={`w-1.5 h-1.5 ${c.dot} opacity-40`} />
                  <span>{sp.name}</span>
                  <span className="text-[9px]">[{sp.diet === 'herbivore' ? 'H' : 'C'}]</span>
                </div>
                <span>{sp.score.toLocaleString()} pts</span>
              </div>
            );
          })}
        </div>
      )}

      {alive.length === 0 && dead.length === 0 && (
        <div className="text-on-surface-variant text-sm font-mono">Awaiting_bots...</div>
      )}
    </div>
  );
}
