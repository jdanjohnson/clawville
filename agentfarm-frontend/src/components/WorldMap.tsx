import { useRef, useEffect, useState, useCallback } from 'react';
import { Parcel, CropInfo } from '../lib/api';

interface WorldMapProps {
  parcels: Parcel[];
  worldSize: number;
  crops: CropInfo[];
  onParcelClick: (parcel: Parcel) => void;
  selectedParcelId: number | null;
}

const CROP_COLORS: Record<string, string> = {
  sea_kelp: '#2d5a27',
  coral_bloom: '#ff6b6b',
  pearl_oyster: '#e8d5b7',
  bioluminescent_algae: '#00ff88',
  anemone: '#ff69b4',
  deep_sea_mushroom: '#9b59b6',
};

const STAGE_OPACITY: Record<string, number> = {
  empty: 0,
  seedling: 0.3,
  sprouting: 0.6,
  growing: 0.85,
  mature: 1.0,
};

export default function WorldMap({ parcels, worldSize, onParcelClick, selectedParcelId }: WorldMapProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [hoveredParcel, setHoveredParcel] = useState<Parcel | null>(null);
  const animFrameRef = useRef(0);
  const timeRef = useRef(0);

  const TILE_SIZE = 40;
  const PLOT_SIZE = TILE_SIZE / 3;

  const parcelMap = useRef<Map<string, Parcel>>(new Map());

  useEffect(() => {
    const map = new Map<string, Parcel>();
    for (const p of parcels) {
      map.set(`${p.x},${p.y}`, p);
    }
    parcelMap.current = map;
  }, [parcels]);

  const drawBubble = useCallback((ctx: CanvasRenderingContext2D, x: number, y: number, r: number, time: number, speed: number) => {
    const floatY = y - Math.sin(time * speed) * 3;
    ctx.beginPath();
    ctx.arc(x, floatY, r, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(150, 220, 255, 0.15)';
    ctx.fill();
    ctx.strokeStyle = 'rgba(150, 220, 255, 0.25)';
    ctx.lineWidth = 0.5;
    ctx.stroke();
  }, []);

  const draw = useCallback((time: number) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const w = canvas.width;
    const h = canvas.height;
    timeRef.current = time / 1000;
    const t = timeRef.current;

    // Deep ocean gradient background
    const bgGrad = ctx.createLinearGradient(0, 0, 0, h);
    bgGrad.addColorStop(0, '#0a1628');
    bgGrad.addColorStop(0.3, '#0d2137');
    bgGrad.addColorStop(0.7, '#0f2847');
    bgGrad.addColorStop(1, '#0a1e3d');
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, w, h);

    // Floating particles / plankton
    for (let i = 0; i < 40; i++) {
      const px = ((i * 137.5 + t * 8) % (w + 100)) - 50;
      const py = ((i * 97.3 + t * 5 * (0.5 + (i % 3) * 0.3)) % (h + 100)) - 50;
      const size = 1 + (i % 3);
      ctx.beginPath();
      ctx.arc(px, py, size, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(100, 200, 255, ${0.05 + (i % 5) * 0.02})`;
      ctx.fill();
    }

    ctx.save();
    ctx.translate(offset.x + w / 2, offset.y + h / 2);
    ctx.scale(zoom, zoom);

    const totalW = worldSize * TILE_SIZE;
    const totalH = worldSize * TILE_SIZE;
    const startX = -totalW / 2;
    const startY = -totalH / 2;

    // Ocean floor base
    const floorGrad = ctx.createLinearGradient(startX, startY, startX, startY + totalH);
    floorGrad.addColorStop(0, '#0f2a4a');
    floorGrad.addColorStop(1, '#0a1e35');
    ctx.fillStyle = floorGrad;
    ctx.fillRect(startX - 5, startY - 5, totalW + 10, totalH + 10);

    // Draw grid
    for (let x = 0; x <= worldSize; x++) {
      ctx.beginPath();
      ctx.moveTo(startX + x * TILE_SIZE, startY);
      ctx.lineTo(startX + x * TILE_SIZE, startY + totalH);
      ctx.strokeStyle = 'rgba(40, 100, 160, 0.2)';
      ctx.lineWidth = 0.5;
      ctx.stroke();
    }
    for (let y = 0; y <= worldSize; y++) {
      ctx.beginPath();
      ctx.moveTo(startX, startY + y * TILE_SIZE);
      ctx.lineTo(startX + totalW, startY + y * TILE_SIZE);
      ctx.strokeStyle = 'rgba(40, 100, 160, 0.2)';
      ctx.lineWidth = 0.5;
      ctx.stroke();
    }

    // Draw parcels
    for (const parcel of parcels) {
      const px = startX + parcel.x * TILE_SIZE;
      const py = startY + parcel.y * TILE_SIZE;

      if (parcel.owner_id) {
        // Claimed parcel - ocean floor with sand
        const sandGrad = ctx.createLinearGradient(px, py, px, py + TILE_SIZE);
        sandGrad.addColorStop(0, '#1a3a5c');
        sandGrad.addColorStop(1, '#1d3f62');
        ctx.fillStyle = sandGrad;
        ctx.fillRect(px + 0.5, py + 0.5, TILE_SIZE - 1, TILE_SIZE - 1);

        // Subtle glow border for claimed parcels
        ctx.strokeStyle = 'rgba(0, 180, 255, 0.3)';
        ctx.lineWidth = 1;
        ctx.strokeRect(px + 0.5, py + 0.5, TILE_SIZE - 1, TILE_SIZE - 1);

        // Draw 3x3 plots within parcel
        for (const plot of parcel.plots) {
          const plotX = px + 1 + plot.local_x * PLOT_SIZE;
          const plotY = py + 1 + plot.local_y * PLOT_SIZE;

          if (plot.crop_type && plot.growth_stage !== 'empty') {
            const color = CROP_COLORS[plot.crop_type] || '#4488aa';
            const opacity = STAGE_OPACITY[plot.growth_stage] || 0.3;

            // Crop glow effect
            ctx.fillStyle = color;
            ctx.globalAlpha = opacity;

            // Pulsing effect for mature crops
            if (plot.growth_stage === 'mature') {
              const pulse = 0.7 + Math.sin(t * 3 + parcel.x + parcel.y) * 0.3;
              ctx.globalAlpha = pulse;
            }

            ctx.beginPath();
            const cr = (PLOT_SIZE - 2) / 2;
            const cx = plotX + PLOT_SIZE / 2;
            const cy = plotY + PLOT_SIZE / 2;

            if (plot.growth_stage === 'seedling') {
              ctx.arc(cx, cy, cr * 0.4, 0, Math.PI * 2);
            } else if (plot.growth_stage === 'sprouting') {
              ctx.arc(cx, cy, cr * 0.65, 0, Math.PI * 2);
            } else {
              ctx.arc(cx, cy, cr * 0.9, 0, Math.PI * 2);
            }
            ctx.fill();

            // Bioluminescent glow for specific crops
            if (plot.crop_type === 'bioluminescent_algae' || plot.growth_stage === 'mature') {
              ctx.shadowColor = color;
              ctx.shadowBlur = 6 + Math.sin(t * 2 + plot.local_x) * 3;
              ctx.fill();
              ctx.shadowBlur = 0;
            }

            ctx.globalAlpha = 1;
          }
        }

        // Selected highlight
        if (selectedParcelId === parcel.id) {
          ctx.strokeStyle = '#00ffff';
          ctx.lineWidth = 2;
          ctx.shadowColor = '#00ffff';
          ctx.shadowBlur = 8;
          ctx.strokeRect(px, py, TILE_SIZE, TILE_SIZE);
          ctx.shadowBlur = 0;
        }
      } else {
        // Unclaimed - dark ocean floor with subtle sand texture
        if ((parcel.x + parcel.y) % 7 === 0) {
          // Occasional sand patch
          ctx.fillStyle = 'rgba(60, 80, 100, 0.1)';
          ctx.fillRect(px + 2, py + 2, TILE_SIZE - 4, TILE_SIZE - 4);
        }
      }
    }

    // Bubbles floating up from claimed parcels
    for (const parcel of parcels) {
      if (!parcel.owner_id) continue;
      const hasCrops = parcel.plots.some(p => p.crop_type);
      if (!hasCrops) continue;

      const px = startX + parcel.x * TILE_SIZE + TILE_SIZE / 2;
      const py = startY + parcel.y * TILE_SIZE;
      const bubbleOffset = ((t * 10 + parcel.x * 7 + parcel.y * 13) % 30);
      drawBubble(ctx, px + Math.sin(parcel.x + t) * 3, py - bubbleOffset, 1.5, t, 1 + parcel.x * 0.1);
    }

    // Hovered parcel tooltip
    if (hoveredParcel) {
      const hx = startX + hoveredParcel.x * TILE_SIZE;
      const hy = startY + hoveredParcel.y * TILE_SIZE - 28;

      ctx.fillStyle = 'rgba(0, 20, 40, 0.85)';
      ctx.strokeStyle = 'rgba(0, 180, 255, 0.5)';
      ctx.lineWidth = 1;

      const label = hoveredParcel.owner_name
        ? `${hoveredParcel.owner_name}'s plot`
        : `Unclaimed (${hoveredParcel.x}, ${hoveredParcel.y})`;

      ctx.font = '10px monospace';
      const tw = ctx.measureText(label).width + 12;

      const roundRect = (x: number, y: number, w: number, h: number, r: number) => {
        ctx.beginPath();
        ctx.moveTo(x + r, y);
        ctx.lineTo(x + w - r, y);
        ctx.quadraticCurveTo(x + w, y, x + w, y + r);
        ctx.lineTo(x + w, y + h - r);
        ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
        ctx.lineTo(x + r, y + h);
        ctx.quadraticCurveTo(x, y + h, x, y + h - r);
        ctx.lineTo(x, y + r);
        ctx.quadraticCurveTo(x, y, x + r, y);
        ctx.closePath();
      };

      roundRect(hx - 2, hy - 2, tw, 18, 4);
      ctx.fill();
      ctx.stroke();

      ctx.fillStyle = '#8cf';
      ctx.fillText(label, hx + 4, hy + 11);
    }

    ctx.restore();

    animFrameRef.current = requestAnimationFrame(draw);
  }, [parcels, worldSize, offset, zoom, selectedParcelId, hoveredParcel, drawBubble, TILE_SIZE, PLOT_SIZE]);

  useEffect(() => {
    animFrameRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(animFrameRef.current);
  }, [draw]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const resize = () => {
      canvas.width = container.clientWidth;
      canvas.height = container.clientHeight;
    };
    resize();
    window.addEventListener('resize', resize);
    return () => window.removeEventListener('resize', resize);
  }, []);

  const getParcelAt = useCallback((clientX: number, clientY: number): Parcel | null => {
    const canvas = canvasRef.current;
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    const mx = clientX - rect.left;
    const my = clientY - rect.top;

    const wx = (mx - canvas.width / 2 - offset.x) / zoom;
    const wy = (my - canvas.height / 2 - offset.y) / zoom;

    const totalW = worldSize * TILE_SIZE;
    const totalH = worldSize * TILE_SIZE;
    const startX = -totalW / 2;
    const startY = -totalH / 2;

    const gx = Math.floor((wx - startX) / TILE_SIZE);
    const gy = Math.floor((wy - startY) / TILE_SIZE);

    if (gx < 0 || gx >= worldSize || gy < 0 || gy >= worldSize) return null;
    return parcelMap.current.get(`${gx},${gy}`) || null;
  }, [offset, zoom, worldSize, TILE_SIZE]);

  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    setDragStart({ x: e.clientX - offset.x, y: e.clientY - offset.y });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isDragging) {
      setOffset({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
    }
    const p = getParcelAt(e.clientX, e.clientY);
    setHoveredParcel(p);
  };

  const handleMouseUp = (e: React.MouseEvent) => {
    if (isDragging) {
      const dx = Math.abs(e.clientX - (dragStart.x + offset.x));
      const dy = Math.abs(e.clientY - (dragStart.y + offset.y));
      // Only trigger click if not dragged
      if (dx < 3 && dy < 3) {
        const p = getParcelAt(e.clientX, e.clientY);
        if (p) onParcelClick(p);
      }
    }
    setIsDragging(false);
  };

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setZoom(z => Math.max(0.3, Math.min(5, z * delta)));
  };

  return (
    <div ref={containerRef} className="w-full h-full relative overflow-hidden cursor-grab active:cursor-grabbing">
      <canvas
        ref={canvasRef}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={() => { setIsDragging(false); setHoveredParcel(null); }}
        onWheel={handleWheel}
        className="w-full h-full"
      />
      {/* Zoom controls */}
      <div className="absolute bottom-4 right-4 flex flex-col gap-2">
        <button
          onClick={() => setZoom(z => Math.min(5, z * 1.3))}
          className="w-8 h-8 rounded-full bg-slate-800/80 border border-cyan-500/30 text-cyan-300 flex items-center justify-center hover:bg-slate-700/80 text-lg font-bold"
        >
          +
        </button>
        <button
          onClick={() => setZoom(z => Math.max(0.3, z / 1.3))}
          className="w-8 h-8 rounded-full bg-slate-800/80 border border-cyan-500/30 text-cyan-300 flex items-center justify-center hover:bg-slate-700/80 text-lg font-bold"
        >
          -
        </button>
        <button
          onClick={() => { setZoom(1); setOffset({ x: 0, y: 0 }); }}
          className="w-8 h-8 rounded-full bg-slate-800/80 border border-cyan-500/30 text-cyan-300 flex items-center justify-center hover:bg-slate-700/80 text-xs"
        >
          R
        </button>
      </div>
    </div>
  );
}
