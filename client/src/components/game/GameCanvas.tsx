// Spectator game canvas — pan/zoom, click to inspect dinos

import { useRef, useEffect } from 'react';
import { CanvasRenderer } from './CanvasRenderer';
import { useGameStore } from '../../state/gameStore';

export function GameCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rendererRef = useRef<CanvasRenderer | null>(null);
  const animFrameRef = useRef<number>(0);
  const centeredRef = useRef(false);

  const selectDino = useGameStore((s) => s.selectDino);

  // Initialize renderer + render loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const renderer = new CanvasRenderer(ctx);
    rendererRef.current = renderer;

    renderer.onCellClick = (x, y) => {
      const dinos = useGameStore.getState().dinosaurs;
      const clicked = dinos.find(d => d.x === x && d.y === y);
      selectDino(clicked ? clicked.id : null);
    };

    const onMouseDown = (e: MouseEvent) => renderer.handleMouseDown(e);
    const onMouseMove = (e: MouseEvent) => renderer.handleMouseMove(e);
    const onMouseUp = (e: MouseEvent) => renderer.handleMouseUp(e);
    const onWheel = (e: WheelEvent) => renderer.handleWheel(e);

    canvas.addEventListener('mousedown', onMouseDown);
    canvas.addEventListener('mousemove', onMouseMove);
    canvas.addEventListener('mouseup', onMouseUp);
    canvas.addEventListener('wheel', onWheel, { passive: false });

    // Render loop — reads directly from store each frame
    const render = () => {
      const state = useGameStore.getState();

      let maxX = 0, maxY = 0;
      for (const cell of state.visibleCells) {
        if (cell.x > maxX) maxX = cell.x;
        if (cell.y > maxY) maxY = cell.y;
      }
      const mapW = maxX > 0 ? maxX + 1 : 50;
      const mapH = maxY > 0 ? maxY + 1 : 50;

      // Center camera once we have both data and canvas size
      if (!centeredRef.current && state.visibleCells.length > 0 && canvas.width > 100) {
        renderer.centerOn(mapW / 2, mapH / 2, canvas.width, canvas.height);
        centeredRef.current = true;
      }

      renderer.render({
        visibleCells: state.visibleCells,
        dinosaurs: state.dinosaurs,
        eggs: state.eggs,
        selectedDinoId: state.selectedDinoId,
        mapWidth: mapW,
        mapHeight: mapH,
      });

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

  // Resize canvas to match container
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const container = canvas.parentElement;
    if (!container) return;

    const resize = () => {
      const w = container.clientWidth;
      const h = container.clientHeight;
      if (w > 0 && h > 0) {
        canvas.width = w;
        canvas.height = h;
      }
    };

    // Use ResizeObserver for layout changes + window resize as fallback
    const observer = new ResizeObserver(resize);
    observer.observe(container);
    window.addEventListener('resize', resize);
    // Also retry after a short delay for flex layout settling
    setTimeout(resize, 100);
    setTimeout(resize, 500);

    return () => {
      observer.disconnect();
      window.removeEventListener('resize', resize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', cursor: 'grab' }}
    />
  );
}
