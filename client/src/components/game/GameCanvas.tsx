// Spectator game canvas — pan/zoom, click to inspect dinos

import { useRef, useEffect } from 'react';
import { CanvasRenderer } from './CanvasRenderer';
import { useGameStore } from '../../state/gameStore';

export function GameCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rendererRef = useRef<CanvasRenderer | null>(null);
  const animFrameRef = useRef<number>(0);
  const centeredRef = useRef(false);

  // Use refs for render data so the render loop never restarts
  const renderDataRef = useRef({
    visibleCells: [] as any[],
    dinosaurs: [] as any[],
    eggs: [] as any[],
    selectedDinoId: null as string | null,
    mapWidth: 50,
    mapHeight: 50,
  });

  // Subscribe to store changes via refs (no re-renders, no effect restarts)
  useEffect(() => {
    const unsub = useGameStore.subscribe((state) => {
      // Update map size
      let maxX = 0, maxY = 0;
      for (const cell of state.visibleCells) {
        if (cell.x > maxX) maxX = cell.x;
        if (cell.y > maxY) maxY = cell.y;
      }
      const mapW = maxX > 0 ? maxX + 1 : renderDataRef.current.mapWidth;
      const mapH = maxY > 0 ? maxY + 1 : renderDataRef.current.mapHeight;

      renderDataRef.current = {
        visibleCells: state.visibleCells,
        dinosaurs: state.dinosaurs,
        eggs: state.eggs,
        selectedDinoId: state.selectedDinoId,
        mapWidth: mapW,
        mapHeight: mapH,
      };

      // Center camera once
      const renderer = rendererRef.current;
      const canvas = canvasRef.current;
      if (renderer && canvas && !centeredRef.current && mapW > 1 && mapH > 1) {
        renderer.centerOn(mapW / 2, mapH / 2, canvas.width, canvas.height);
        centeredRef.current = true;
      }
    });
    return unsub;
  }, []);

  // Also read the click handler's dinos from a ref
  const dinosaursRef = useRef<any[]>([]);
  useEffect(() => {
    const unsub = useGameStore.subscribe((state) => {
      dinosaursRef.current = state.dinosaurs;
    });
    return unsub;
  }, []);

  const selectDino = useGameStore((s) => s.selectDino);

  // Initialize renderer + render loop (runs once, never restarts)
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const renderer = new CanvasRenderer(ctx);
    rendererRef.current = renderer;

    renderer.onCellClick = (x, y) => {
      const clicked = dinosaursRef.current.find(d => d.x === x && d.y === y);
      selectDino(clicked ? clicked.id : null);
    };

    // Mouse/wheel handlers
    const onMouseDown = (e: MouseEvent) => renderer.handleMouseDown(e);
    const onMouseMove = (e: MouseEvent) => renderer.handleMouseMove(e);
    const onMouseUp = (e: MouseEvent) => renderer.handleMouseUp(e);
    const onWheel = (e: WheelEvent) => renderer.handleWheel(e);

    canvas.addEventListener('mousedown', onMouseDown);
    canvas.addEventListener('mousemove', onMouseMove);
    canvas.addEventListener('mouseup', onMouseUp);
    canvas.addEventListener('wheel', onWheel, { passive: false });

    // Single render loop — reads from ref, never restarts
    const render = () => {
      renderer.render(renderDataRef.current);
      animFrameRef.current = requestAnimationFrame(render);
    };
    animFrameRef.current = requestAnimationFrame(render);

    return () => {
      canvas.removeEventListener('mousedown', onMouseDown);
      canvas.removeEventListener('mousemove', onMouseMove);
      canvas.removeEventListener('mouseup', onMouseUp);
      canvas.removeEventListener('wheel', onWheel);
      cancelAnimationFrame(animFrameRef.current);
    };
  }, []);

  // Resize canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const resize = () => {
      const parent = canvas.parentElement;
      if (parent) {
        canvas.width = parent.clientWidth;
        canvas.height = parent.clientHeight;
      }
    };
    resize();
    window.addEventListener('resize', resize);
    return () => window.removeEventListener('resize', resize);
  }, []);

  return (
    <div style={{ flex: 1, position: 'relative', overflow: 'hidden', background: '#0a0a0a' }}>
      <canvas
        ref={canvasRef}
        style={{ display: 'block', width: '100%', height: '100%', cursor: 'grab' }}
      />
    </div>
  );
}
