// Pure canvas drawing logic — spectator view with terrain rendering

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

// Deterministic pseudo-random per tile (stable across frames)
function tileRng(x: number, y: number, seed: number = 0): number {
  let h = (x * 374761393 + y * 668265263 + seed * 1274126177) | 0;
  h = ((h ^ (h >> 13)) * 1274126177) | 0;
  return (h & 0x7fffffff) / 0x7fffffff; // 0..1
}

// Lerp between two hex colors
function lerpColor(a: string, b: string, t: number): string {
  const ar = parseInt(a.slice(1, 3), 16), ag = parseInt(a.slice(3, 5), 16), ab = parseInt(a.slice(5, 7), 16);
  const br = parseInt(b.slice(1, 3), 16), bg = parseInt(b.slice(3, 5), 16), bb = parseInt(b.slice(5, 7), 16);
  const r = Math.round(ar + (br - ar) * t);
  const g = Math.round(ag + (bg - ag) * t);
  const bl = Math.round(ab + (bb - ab) * t);
  return `rgb(${r},${g},${bl})`;
}

// Terrain color palettes (multiple shades for natural variation)
const WATER_COLORS = ['#1a3a6e', '#1e40af', '#1d4ed8', '#2563eb', '#1e3a8a'];
const PLAIN_COLORS = ['#92764a', '#a3865a', '#b5956a', '#8b7340', '#9e8858'];
const VEG_RICH = ['#15803d', '#16a34a', '#22c55e', '#1a7a3a', '#1d9e48'];
const VEG_MED = ['#166534', '#15803d', '#14532d', '#1a6b38', '#137a32'];
const VEG_LOW = ['#14532d', '#1a3d24', '#0f3d1c', '#163828', '#12472a'];
const CARRION_HIGH = ['#991b1b', '#b91c1c', '#dc2626', '#a31d1d', '#c42020'];
const CARRION_LOW = ['#7f1d1d', '#6b1a1a', '#5c1616', '#701b1b', '#641818'];

function pickTileColor(palette: string[], x: number, y: number): string {
  const idx = Math.floor(tileRng(x, y, 1) * palette.length);
  return palette[idx];
}


// Animation state for a dino
interface DinoAnim {
  fromX: number;
  fromY: number;
  toX: number;
  toY: number;
  startTime: number;
}

// Combat/death flash effect
interface FlashEffect {
  x: number;
  y: number;
  startTime: number;
  color: string; // species color
}

const MOVE_DURATION = 400; // ms for movement animation
const FLASH_DURATION = 600; // ms for combat flash

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

  // Animation tracking
  private dinoAnims = new Map<string, DinoAnim>();
  private prevDinoPositions = new Map<string, { x: number; y: number }>();
  private prevDinoIds = new Set<string>();
  private flashEffects: FlashEffect[] = [];

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
    ctx.fillStyle = '#050a14';
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

    // --- Draw terrain ---
    for (let y = startY; y < endY; y++) {
      for (let x = startX; x < endX; x++) {
        const sx = x * ts - this.cameraX;
        const sy = y * ts - this.cameraY;
        const cell = cellMap.get(`${x},${y}`);

        if (!cell) {
          continue; // unexplored = background color
        }

        this._drawTerrain(ctx, cell, x, y, sx, sy, ts, cellMap);
      }
    }

    // --- Draw eggs ---
    for (const egg of state.eggs) {
      const sx = egg.x * ts - this.cameraX;
      const sy = egg.y * ts - this.cameraY;
      if (sx + ts < 0 || sx > w || sy + ts < 0 || sy > h) continue;

      ctx.fillStyle = COLORS.egg;
      ctx.beginPath();
      ctx.ellipse(sx + ts / 2, sy + ts / 2, ts * 0.2, ts * 0.25, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = 'rgba(0,0,0,0.3)';
      ctx.lineWidth = 1;
      ctx.stroke();
    }

    // --- Update animations ---
    const now = performance.now();
    const currentIds = new Set(state.dinosaurs.map(d => d.id));

    // Detect new positions and start movement animations
    for (const dino of state.dinosaurs) {
      const prev = this.prevDinoPositions.get(dino.id);
      if (prev && (prev.x !== dino.x || prev.y !== dino.y)) {
        // Position changed — start animation
        this.dinoAnims.set(dino.id, {
          fromX: prev.x, fromY: prev.y,
          toX: dino.x, toY: dino.y,
          startTime: now,
        });
      }
      this.prevDinoPositions.set(dino.id, { x: dino.x, y: dino.y });
    }

    // Detect deaths — create flash effects
    for (const prevId of this.prevDinoIds) {
      if (!currentIds.has(prevId)) {
        const prevPos = this.prevDinoPositions.get(prevId);
        if (prevPos) {
          // Check if another dino is at this position (combat kill)
          const killer = state.dinosaurs.find(d => d.x === prevPos.x && d.y === prevPos.y);
          this.flashEffects.push({
            x: prevPos.x, y: prevPos.y,
            startTime: now,
            color: killer ? getSpeciesColor(killer.species_id) : '#ff716c',
          });
          this.prevDinoPositions.delete(prevId);
        }
      }
    }
    this.prevDinoIds = currentIds;

    // Clean up finished animations
    for (const [id, anim] of this.dinoAnims) {
      if (now - anim.startTime > MOVE_DURATION) {
        this.dinoAnims.delete(id);
      }
    }
    this.flashEffects = this.flashEffects.filter(f => now - f.startTime < FLASH_DURATION);

    // --- Draw flash effects (behind dinos) ---
    for (const flash of this.flashEffects) {
      const progress = (now - flash.startTime) / FLASH_DURATION;
      const sx = flash.x * ts - this.cameraX;
      const sy = flash.y * ts - this.cameraY;
      if (sx + ts < 0 || sx > w || sy + ts < 0 || sy > h) continue;

      const alpha = 1 - progress;
      const radius = ts * (0.5 + progress * 1.5);

      // Expanding ring
      ctx.strokeStyle = flash.color;
      ctx.globalAlpha = alpha * 0.8;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(sx + ts / 2, sy + ts / 2, radius, 0, Math.PI * 2);
      ctx.stroke();

      // Inner flash
      ctx.fillStyle = flash.color;
      ctx.globalAlpha = alpha * 0.3;
      ctx.beginPath();
      ctx.arc(sx + ts / 2, sy + ts / 2, radius * 0.5, 0, Math.PI * 2);
      ctx.fill();

      ctx.globalAlpha = 1;
    }

    // --- Draw dinos (with interpolated positions) ---
    for (const dino of state.dinosaurs) {
      let drawX = dino.x;
      let drawY = dino.y;

      // Interpolate if animating
      const anim = this.dinoAnims.get(dino.id);
      if (anim) {
        const t = Math.min(1, (now - anim.startTime) / MOVE_DURATION);
        // Ease out cubic
        const ease = 1 - Math.pow(1 - t, 3);
        drawX = anim.fromX + (anim.toX - anim.fromX) * ease;
        drawY = anim.fromY + (anim.toY - anim.fromY) * ease;
      }

      const sx = drawX * ts - this.cameraX;
      const sy = drawY * ts - this.cameraY;
      if (sx + ts < 0 || sx > w || sy + ts < 0 || sy > h) continue;

      this._drawDino(ctx, dino, sx, sy, ts, state.selectedDinoId);
    }

    // Legend
    this._drawLegend(state.dinosaurs);
  }

  private _drawTerrain(
    ctx: CanvasRenderingContext2D,
    cell: CellResponse,
    x: number, y: number,
    sx: number, sy: number,
    ts: number,
    cellMap: Map<string, CellResponse>,
  ) {
    const rng1 = tileRng(x, y, 0);
    const rng2 = tileRng(x, y, 2);
    const rng3 = tileRng(x, y, 3);

    switch (cell.cell_type) {
      case 'water': {
        // Base water color with variation
        ctx.fillStyle = pickTileColor(WATER_COLORS, x, y);
        ctx.fillRect(sx, sy, ts, ts);

        // Subtle wave highlights
        if (ts >= 10) {
          ctx.fillStyle = `rgba(100,180,255,${0.05 + rng1 * 0.08})`;
          const wx = sx + rng2 * ts * 0.6;
          const wy = sy + rng3 * ts * 0.4;
          ctx.fillRect(wx, wy, ts * 0.3, 1);
        }

        // Shore effect: lighten edges adjacent to land
        this._drawShore(ctx, x, y, sx, sy, ts, cellMap);
        break;
      }

      case 'plain': {
        ctx.fillStyle = pickTileColor(PLAIN_COLORS, x, y);
        ctx.fillRect(sx, sy, ts, ts);

        // Dirt/rock specks
        if (ts >= 12) {
          const specks = 1 + Math.floor(rng1 * 3);
          for (let i = 0; i < specks; i++) {
            const r = tileRng(x, y, 10 + i);
            const r2 = tileRng(x, y, 20 + i);
            ctx.fillStyle = `rgba(0,0,0,${0.08 + r * 0.1})`;
            ctx.fillRect(sx + r * ts * 0.8, sy + r2 * ts * 0.8, ts * 0.08, ts * 0.08);
          }
        }
        break;
      }

      case 'vegetation': {
        const ratio = cell.max_energy > 0 ? cell.energy / cell.max_energy : 0;

        // Base: earthy green ground
        const basePalette = ratio > 0.5 ? VEG_RICH : ratio > 0.15 ? VEG_MED : VEG_LOW;
        ctx.fillStyle = pickTileColor(basePalette, x, y);
        ctx.fillRect(sx, sy, ts, ts);

        // Draw foliage dots/patches proportional to energy
        if (ts >= 8) {
          const dotCount = Math.floor(ratio * 6) + 1;
          for (let i = 0; i < dotCount; i++) {
            const dx = tileRng(x, y, 30 + i) * ts * 0.8 + ts * 0.1;
            const dy = tileRng(x, y, 40 + i) * ts * 0.8 + ts * 0.1;
            const dr = ts * (0.06 + ratio * 0.08);
            const brightness = 0.3 + ratio * 0.5;
            ctx.fillStyle = `rgba(34,197,94,${brightness})`;
            ctx.beginPath();
            ctx.arc(sx + dx, sy + dy, dr, 0, Math.PI * 2);
            ctx.fill();
          }
        }
        break;
      }

      case 'carrion': {
        const ratio = cell.max_energy > 0 ? cell.energy / cell.max_energy : 0;

        // Base: dark ground
        ctx.fillStyle = pickTileColor(PLAIN_COLORS, x, y);
        ctx.fillRect(sx, sy, ts, ts);

        // Carrion blob
        const blobColor = ratio > 0.5 ? pickTileColor(CARRION_HIGH, x, y) : pickTileColor(CARRION_LOW, x, y);
        ctx.fillStyle = blobColor;
        const blobSize = ts * (0.2 + ratio * 0.25);
        ctx.beginPath();
        ctx.ellipse(
          sx + ts * (0.4 + rng1 * 0.2),
          sy + ts * (0.4 + rng2 * 0.2),
          blobSize, blobSize * 0.7,
          rng3 * Math.PI, 0, Math.PI * 2,
        );
        ctx.fill();

        // Stain ring
        if (ts >= 10) {
          ctx.strokeStyle = `rgba(120,20,20,${0.2 + ratio * 0.2})`;
          ctx.lineWidth = 1;
          ctx.stroke();
        }
        break;
      }
    }

    // Subtle grid line
    ctx.strokeStyle = 'rgba(255,255,255,0.03)';
    ctx.lineWidth = 0.5;
    ctx.strokeRect(sx, sy, ts, ts);
  }

  private _drawShore(
    ctx: CanvasRenderingContext2D,
    x: number, y: number,
    sx: number, sy: number,
    ts: number,
    cellMap: Map<string, CellResponse>,
  ) {
    // Draw foam/shore on water edges adjacent to land
    const neighbors = [
      [x, y - 1, 'top'],
      [x, y + 1, 'bottom'],
      [x - 1, y, 'left'],
      [x + 1, y, 'right'],
    ] as const;

    for (const [nx, ny, side] of neighbors) {
      const neighbor = cellMap.get(`${nx},${ny}`);
      if (neighbor && neighbor.cell_type !== 'water') {
        ctx.fillStyle = 'rgba(140,200,255,0.15)';
        switch (side) {
          case 'top': ctx.fillRect(sx, sy, ts, ts * 0.2); break;
          case 'bottom': ctx.fillRect(sx, sy + ts * 0.8, ts, ts * 0.2); break;
          case 'left': ctx.fillRect(sx, sy, ts * 0.2, ts); break;
          case 'right': ctx.fillRect(sx + ts * 0.8, sy, ts * 0.2, ts); break;
        }
      }
    }
  }

  private _drawDino(
    ctx: CanvasRenderingContext2D,
    dino: DinoResponse,
    sx: number, sy: number,
    ts: number,
    selectedDinoId: string | null,
  ) {
    const color = getSpeciesColor(dino.species_id);
    const isSelected = dino.id === selectedDinoId;
    const radius = ts * 0.15 + (dino.dimension * ts * 0.06);

    // Shadow
    ctx.fillStyle = 'rgba(0,0,0,0.3)';
    ctx.beginPath();
    ctx.ellipse(sx + ts / 2 + 1, sy + ts / 2 + 2, radius * 0.9, radius * 0.5, 0, 0, Math.PI * 2);
    ctx.fill();

    // Selection ring
    if (isSelected) {
      ctx.strokeStyle = COLORS.selected;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(sx + ts / 2, sy + ts / 2, radius + 4, 0, Math.PI * 2);
      ctx.stroke();
    }

    // Body
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(sx + ts / 2, sy + ts / 2, radius, 0, Math.PI * 2);
    ctx.fill();

    // Highlight (top-left shine)
    ctx.fillStyle = 'rgba(255,255,255,0.2)';
    ctx.beginPath();
    ctx.arc(sx + ts / 2 - radius * 0.25, sy + ts / 2 - radius * 0.25, radius * 0.4, 0, Math.PI * 2);
    ctx.fill();

    // Border
    ctx.strokeStyle = 'rgba(0,0,0,0.4)';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.arc(sx + ts / 2, sy + ts / 2, radius, 0, Math.PI * 2);
    ctx.stroke();

    // Dimension number
    if (ts >= 14) {
      ctx.fillStyle = '#fff';
      ctx.font = `bold ${Math.max(9, ts * 0.4)}px monospace`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(String(dino.dimension), sx + ts / 2, sy + ts / 2 + 1);
    }

    // Diet indicator
    if (ts >= 18) {
      const label = dino.diet === 'herbivore' ? 'H' : 'C';
      ctx.fillStyle = 'rgba(255,255,255,0.6)';
      ctx.font = `${Math.max(7, ts * 0.25)}px monospace`;
      ctx.fillText(label, sx + ts / 2, sy + ts / 2 + radius + 6);
    }
  }

  private _drawLegend(dinosaurs: DinoResponse[]) {
    const { ctx } = this;
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

    ctx.fillStyle = 'rgba(0,0,0,0.7)';
    ctx.fillRect(x, y, 160, seen.size * lineHeight + 8);

    y += 4;
    for (const [, sp] of seen) {
      y += lineHeight;
      ctx.fillStyle = sp.color;
      ctx.beginPath();
      ctx.arc(x + 12, y - 5, 5, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#e5e7eb';
      ctx.font = '12px sans-serif';
      ctx.textAlign = 'left';
      ctx.textBaseline = 'middle';
      const dietLabel = sp.diet === 'herbivore' ? 'H' : 'C';
      ctx.fillText(`${sp.name} [${dietLabel}]`, x + 22, y - 5);
    }
  }
}
