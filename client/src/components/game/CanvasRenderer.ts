// Pure canvas drawing logic — spectator view, no player interaction

import type { CellResponse, DinoResponse, EggResponse } from '../../api/types';
import { COLORS } from '../../utils/colors';

const TILE_SIZE = 20;

interface RenderState {
  visibleCells: CellResponse[];
  dinosaurs: DinoResponse[];
  eggs: EggResponse[];
  selectedDinoId: string | null;
  mapWidth: number;
  mapHeight: number;
}

// Stable color assignment for species
const speciesColorCache = new Map<string, string>();
let colorIndex = 0;

function getSpeciesColor(speciesId: string): string {
  if (!speciesColorCache.has(speciesId)) {
    speciesColorCache.set(speciesId, COLORS.species[colorIndex % COLORS.species.length]);
    colorIndex++;
  }
  return speciesColorCache.get(speciesId)!;
}

export class CanvasRenderer {
  private ctx: CanvasRenderingContext2D;
  private cameraX = 0;
  private cameraY = 0;
  private zoom = 1;
  private isDragging = false;
  private dragStartX = 0;
  private dragStartY = 0;
  private dragCamStartX = 0;
  private dragCamStartY = 0;

  onCellClick: ((x: number, y: number) => void) | null = null;

  constructor(ctx: CanvasRenderingContext2D) {
    this.ctx = ctx;
  }

  get tileSize() {
    return TILE_SIZE * this.zoom;
  }

  centerOn(x: number, y: number, canvasWidth: number, canvasHeight: number) {
    this.cameraX = x * this.tileSize - canvasWidth / 2;
    this.cameraY = y * this.tileSize - canvasHeight / 2;
  }

  handleMouseDown(e: MouseEvent) {
    this.isDragging = true;
    this.dragStartX = e.clientX;
    this.dragStartY = e.clientY;
    this.dragCamStartX = this.cameraX;
    this.dragCamStartY = this.cameraY;
  }

  handleMouseMove(e: MouseEvent) {
    if (this.isDragging) {
      this.cameraX = this.dragCamStartX - (e.clientX - this.dragStartX);
      this.cameraY = this.dragCamStartY - (e.clientY - this.dragStartY);
    }
  }

  handleMouseUp(e: MouseEvent) {
    if (this.isDragging) {
      const dx = Math.abs(e.clientX - this.dragStartX);
      const dy = Math.abs(e.clientY - this.dragStartY);
      if (dx < 5 && dy < 5 && this.onCellClick) {
        const rect = this.ctx.canvas.getBoundingClientRect();
        const cx = e.clientX - rect.left + this.cameraX;
        const cy = e.clientY - rect.top + this.cameraY;
        const cellX = Math.floor(cx / this.tileSize);
        const cellY = Math.floor(cy / this.tileSize);
        this.onCellClick(cellX, cellY);
      }
    }
    this.isDragging = false;
  }

  handleWheel(e: WheelEvent) {
    e.preventDefault();
    const oldZoom = this.zoom;
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    this.zoom = Math.max(0.3, Math.min(3, this.zoom * delta));

    const rect = this.ctx.canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    this.cameraX = (this.cameraX + mx) * (this.zoom / oldZoom) - mx;
    this.cameraY = (this.cameraY + my) * (this.zoom / oldZoom) - my;
  }

  render(state: RenderState) {
    const { ctx } = this;
    const canvas = ctx.canvas;
    const w = canvas.width;
    const h = canvas.height;
    const ts = this.tileSize;

    // Clear
    ctx.fillStyle = COLORS.unexplored;
    ctx.fillRect(0, 0, w, h);

    const startX = Math.max(0, Math.floor(this.cameraX / ts));
    const startY = Math.max(0, Math.floor(this.cameraY / ts));
    const endX = Math.min(state.mapWidth, Math.ceil((this.cameraX + w) / ts));
    const endY = Math.min(state.mapHeight, Math.ceil((this.cameraY + h) / ts));

    // Build cell lookup
    const cellMap = new Map<string, CellResponse>();
    for (const cell of state.visibleCells) {
      cellMap.set(`${cell.x},${cell.y}`, cell);
    }

    // Draw terrain
    for (let y = startY; y < endY; y++) {
      for (let x = startX; x < endX; x++) {
        const sx = x * ts - this.cameraX;
        const sy = y * ts - this.cameraY;
        const cell = cellMap.get(`${x},${y}`);

        if (!cell) {
          ctx.fillStyle = COLORS.unexplored;
          ctx.fillRect(sx, sy, ts, ts);
          continue;
        }

        switch (cell.cell_type) {
          case 'water':
            ctx.fillStyle = COLORS.water;
            break;
          case 'plain':
            ctx.fillStyle = COLORS.plain;
            break;
          case 'vegetation': {
            const ratio = cell.max_energy > 0 ? cell.energy / cell.max_energy : 0;
            ctx.fillStyle = ratio > 0.6 ? COLORS.vegHigh : ratio > 0.2 ? COLORS.vegMed : COLORS.vegLow;
            break;
          }
          case 'carrion': {
            const ratio = cell.max_energy > 0 ? cell.energy / cell.max_energy : 0;
            ctx.fillStyle = ratio > 0.5 ? COLORS.carrionHigh : COLORS.carrionLow;
            break;
          }
        }
        ctx.fillRect(sx, sy, ts, ts);

        // Grid line
        ctx.strokeStyle = 'rgba(255,255,255,0.06)';
        ctx.strokeRect(sx, sy, ts, ts);
      }
    }

    // Draw eggs
    for (const egg of state.eggs) {
      const sx = egg.x * ts - this.cameraX;
      const sy = egg.y * ts - this.cameraY;
      if (sx + ts < 0 || sx > w || sy + ts < 0 || sy > h) continue;

      ctx.fillStyle = COLORS.egg;
      ctx.beginPath();
      ctx.ellipse(sx + ts / 2, sy + ts / 2, ts * 0.2, ts * 0.25, 0, 0, Math.PI * 2);
      ctx.fill();
    }

    // Draw dinos — colored by species
    for (const dino of state.dinosaurs) {
      const sx = dino.x * ts - this.cameraX;
      const sy = dino.y * ts - this.cameraY;
      if (sx + ts < 0 || sx > w || sy + ts < 0 || sy > h) continue;

      const color = getSpeciesColor(dino.species_id);
      const isSelected = dino.id === state.selectedDinoId;
      const radius = ts * 0.15 + (dino.dimension * ts * 0.06);

      // Selection ring
      if (isSelected) {
        ctx.strokeStyle = COLORS.selected;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(sx + ts / 2, sy + ts / 2, radius + 4, 0, Math.PI * 2);
        ctx.stroke();
      }

      // Dino body
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(sx + ts / 2, sy + ts / 2, radius, 0, Math.PI * 2);
      ctx.fill();

      // Border
      ctx.strokeStyle = 'rgba(0,0,0,0.4)';
      ctx.lineWidth = 1.5;
      ctx.stroke();

      // Dimension number
      if (ts >= 14) {
        ctx.fillStyle = '#fff';
        ctx.font = `bold ${Math.max(9, ts * 0.4)}px monospace`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(String(dino.dimension), sx + ts / 2, sy + ts / 2 + 1);
      }

      // Diet indicator (small H or C below)
      if (ts >= 18) {
        const label = dino.diet === 'herbivore' ? 'H' : 'C';
        ctx.fillStyle = 'rgba(255,255,255,0.6)';
        ctx.font = `${Math.max(7, ts * 0.25)}px monospace`;
        ctx.fillText(label, sx + ts / 2, sy + ts / 2 + radius + 6);
      }
    }

    // Legend (top-left corner)
    this._drawLegend(state.dinosaurs);
  }

  private _drawLegend(dinosaurs: DinoResponse[]) {
    const { ctx } = this;
    // Collect unique species
    const seen = new Map<string, { name: string; color: string; diet: string }>();
    for (const d of dinosaurs) {
      if (!seen.has(d.species_id)) {
        seen.set(d.species_id, {
          name: d.species_name,
          color: getSpeciesColor(d.species_id),
          diet: d.diet,
        });
      }
    }
    if (seen.size === 0) return;

    const x = 10;
    let y = 10;
    const lineHeight = 18;

    ctx.fillStyle = 'rgba(0,0,0,0.6)';
    ctx.fillRect(x, y, 160, seen.size * lineHeight + 8);

    y += 4;
    for (const [, sp] of seen) {
      y += lineHeight;
      // Color dot
      ctx.fillStyle = sp.color;
      ctx.beginPath();
      ctx.arc(x + 12, y - 5, 5, 0, Math.PI * 2);
      ctx.fill();
      // Name
      ctx.fillStyle = '#e5e7eb';
      ctx.font = '12px sans-serif';
      ctx.textAlign = 'left';
      ctx.textBaseline = 'middle';
      const dietLabel = sp.diet === 'herbivore' ? 'H' : 'C';
      ctx.fillText(`${sp.name} [${dietLabel}]`, x + 22, y - 5);
    }
  }
}
