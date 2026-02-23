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
  brain_coral: '#e88a5a',
  sea_fan: '#ff6eb4',
  staghorn: '#7ecfc0',
  bubble_coral: '#a78bfa',
  tube_sponge: '#facc15',
};

const STAGE_OPACITY: Record<string, number> = {
  empty: 0,
  seedling: 0.4,
  sprouting: 0.65,
  growing: 0.85,
  mature: 1.0,
  dead: 0.2,
};

function drawBrainCoral(ctx: CanvasRenderingContext2D, cx: number, cy: number, r: number, t: number) {
  ctx.beginPath();
  for (let i = 0; i < 12; i++) {
    const angle = (i / 12) * Math.PI * 2;
    const wobble = 0.8 + Math.sin(angle * 3 + t) * 0.2;
    const px = cx + Math.cos(angle) * r * wobble;
    const py = cy + Math.sin(angle) * r * wobble;
    if (i === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  }
  ctx.closePath();
  ctx.fill();
  ctx.strokeStyle = 'rgba(0,0,0,0.2)';
  ctx.lineWidth = 0.3;
  for (let i = 0; i < 3; i++) {
    ctx.beginPath();
    const startAngle = (i / 3) * Math.PI;
    ctx.arc(cx, cy, r * (0.3 + i * 0.2), startAngle, startAngle + Math.PI * 0.8);
    ctx.stroke();
  }
}

function drawSeaFan(ctx: CanvasRenderingContext2D, cx: number, cy: number, r: number, t: number) {
  const sway = Math.sin(t * 1.5) * 0.1;
  const color = ctx.fillStyle as string;
  ctx.beginPath();
  ctx.moveTo(cx, cy + r);
  ctx.lineTo(cx + sway * r, cy - r * 0.2);
  ctx.strokeStyle = color;
  ctx.lineWidth = 1;
  ctx.stroke();
  for (let i = -3; i <= 3; i++) {
    const angle = (i / 6) * Math.PI * 0.8 - Math.PI / 2 + sway;
    const len = r * (0.7 + Math.abs(i) * 0.05);
    ctx.beginPath();
    ctx.moveTo(cx + sway * r, cy - r * 0.2);
    ctx.lineTo(cx + Math.cos(angle) * len + sway * r, cy + Math.sin(angle) * len - r * 0.2);
    ctx.strokeStyle = color;
    ctx.lineWidth = 0.6;
    ctx.stroke();
  }
  ctx.beginPath();
  ctx.arc(cx + sway * r, cy - r * 0.3, r * 0.55, Math.PI * 0.8, Math.PI * 2.2);
  ctx.globalAlpha *= 0.4;
  ctx.fill();
  ctx.globalAlpha /= 0.4;
}

function drawStaghorn(ctx: CanvasRenderingContext2D, cx: number, cy: number, r: number, t: number) {
  const sway = Math.sin(t * 0.8) * 0.05;
  const color = ctx.fillStyle as string;
  ctx.beginPath();
  ctx.moveTo(cx, cy + r);
  ctx.lineTo(cx, cy - r * 0.3);
  ctx.lineWidth = 1.2;
  ctx.strokeStyle = color;
  ctx.stroke();
  const branches = [
    { angle: -0.6 + sway, len: 0.7 },
    { angle: 0.5 + sway, len: 0.65 },
    { angle: -0.3 + sway, len: 0.5 },
    { angle: 0.2 + sway, len: 0.55 },
    { angle: -0.8 + sway, len: 0.4 },
  ];
  for (const b of branches) {
    ctx.beginPath();
    ctx.moveTo(cx, cy - r * 0.1);
    const endX = cx + Math.sin(b.angle) * r * b.len;
    const endY = cy - r * b.len * 0.8;
    ctx.lineTo(endX, endY);
    ctx.strokeStyle = color;
    ctx.lineWidth = 0.8;
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(endX, endY, 1, 0, Math.PI * 2);
    ctx.fill();
  }
}

function drawBubbleCoral(ctx: CanvasRenderingContext2D, cx: number, cy: number, r: number, t: number) {
  const color = ctx.fillStyle as string;
  const bubbles = [
    { dx: 0, dy: 0, s: 0.45 },
    { dx: -0.3, dy: -0.25, s: 0.35 },
    { dx: 0.35, dy: -0.2, s: 0.3 },
    { dx: -0.15, dy: 0.3, s: 0.28 },
    { dx: 0.25, dy: 0.25, s: 0.25 },
    { dx: 0, dy: -0.45, s: 0.22 },
  ];
  for (const b of bubbles) {
    const bx = cx + b.dx * r;
    const by = cy + b.dy * r;
    const br = r * b.s + Math.sin(t * 2 + b.dx * 5) * 0.5;
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(bx, by, br, 0, Math.PI * 2);
    ctx.fill();
    ctx.beginPath();
    ctx.arc(bx - br * 0.25, by - br * 0.25, br * 0.3, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(255,255,255,0.15)';
    ctx.fill();
  }
  ctx.fillStyle = color;
}

function drawTubeSponge(ctx: CanvasRenderingContext2D, cx: number, cy: number, r: number, t: number) {
  const color = ctx.fillStyle as string;
  const tubes = [
    { dx: -0.3, h: 0.9 },
    { dx: 0.1, h: 1.0 },
    { dx: 0.4, h: 0.75 },
  ];
  for (const tube of tubes) {
    const tx = cx + tube.dx * r;
    const baseY = cy + r * 0.4;
    const topY = cy - r * tube.h + Math.sin(t + tube.dx * 3) * 0.5;
    const tubeW = r * 0.28;
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.moveTo(tx - tubeW, baseY);
    ctx.lineTo(tx - tubeW * 0.8, topY);
    ctx.lineTo(tx + tubeW * 0.8, topY);
    ctx.lineTo(tx + tubeW, baseY);
    ctx.closePath();
    ctx.fill();
    ctx.beginPath();
    ctx.ellipse(tx, topY, tubeW * 0.8, tubeW * 0.3, 0, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(0,0,0,0.25)';
    ctx.fill();
  }
  ctx.fillStyle = color;
}

function drawCoralShape(ctx: CanvasRenderingContext2D, cropType: string, cx: number, cy: number, r: number, t: number) {
  switch (cropType) {
    case 'brain_coral': drawBrainCoral(ctx, cx, cy, r, t); break;
    case 'sea_fan': drawSeaFan(ctx, cx, cy, r, t); break;
    case 'staghorn': drawStaghorn(ctx, cx, cy, r, t); break;
    case 'bubble_coral': drawBubbleCoral(ctx, cx, cy, r, t); break;
    case 'tube_sponge': drawTubeSponge(ctx, cx, cy, r, t); break;
    default:
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.fill();
  }
}

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
    for (const p of parcels) { map.set(`${p.x},${p.y}`, p); }
    parcelMap.current = map;
  }, [parcels]);

  const draw = useCallback((time: number) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const w = canvas.width;
    const h = canvas.height;
    timeRef.current = time / 1000;
    const t = timeRef.current;

    const centerX = w / 2;
    const centerY = h / 2;
    const bgGrad = ctx.createRadialGradient(centerX, centerY * 0.7, 0, centerX, centerY, Math.max(w, h) * 0.7);
    bgGrad.addColorStop(0, '#0d2847');
    bgGrad.addColorStop(0.4, '#0a1e3d');
    bgGrad.addColorStop(0.7, '#081833');
    bgGrad.addColorStop(1, '#050e1f');
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, w, h);

    for (let i = 0; i < 8; i++) {
      const cxi = (w * 0.3 + Math.sin(t * 0.3 + i * 1.7) * w * 0.4);
      const cyi = (h * 0.3 + Math.cos(t * 0.2 + i * 2.3) * h * 0.3);
      const cg = ctx.createRadialGradient(cxi, cyi, 0, cxi, cyi, 120 + Math.sin(t + i) * 40);
      cg.addColorStop(0, 'rgba(40, 140, 200, 0.03)');
      cg.addColorStop(1, 'rgba(40, 140, 200, 0)');
      ctx.fillStyle = cg;
      ctx.fillRect(0, 0, w, h);
    }

    for (let i = 0; i < 50; i++) {
      const ppx = ((i * 137.5 + t * 8) % (w + 100)) - 50;
      const ppy = ((i * 97.3 + t * 5 * (0.5 + (i % 3) * 0.3)) % (h + 100)) - 50;
      ctx.beginPath();
      ctx.arc(ppx, ppy, 0.8 + (i % 3) * 0.5, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(100, 200, 255, ${0.04 + (i % 5) * 0.02})`;
      ctx.fill();
    }

    for (let i = 0; i < 15; i++) {
      const bx = ((i * 173.7 + t * 12) % (w + 60)) - 30;
      const by = h - ((i * 83.1 + t * 20 * (0.3 + (i % 4) * 0.2)) % (h + 80));
      const br = 2 + (i % 4) * 1.5;
      ctx.beginPath();
      ctx.arc(bx, by, br, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(150, 220, 255, ${0.06 + (i % 3) * 0.03})`;
      ctx.fill();
      ctx.strokeStyle = `rgba(150, 220, 255, ${0.1 + (i % 3) * 0.05})`;
      ctx.lineWidth = 0.3;
      ctx.stroke();
    }

    ctx.save();
    ctx.translate(offset.x + w / 2, offset.y + h / 2);
    ctx.scale(zoom, zoom);
    const totalW = worldSize * TILE_SIZE;
    const totalH = worldSize * TILE_SIZE;
    const startX = -totalW / 2;
    const startY = -totalH / 2;

    const floorGrad = ctx.createRadialGradient(0, 0, 0, 0, 0, totalW * 0.7);
    floorGrad.addColorStop(0, '#0f2a4a');
    floorGrad.addColorStop(0.5, '#0c2240');
    floorGrad.addColorStop(1, '#0a1e35');
    ctx.fillStyle = floorGrad;
    ctx.fillRect(startX - 5, startY - 5, totalW + 10, totalH + 10);

    ctx.strokeStyle = 'rgba(40, 100, 160, 0.15)';
    ctx.lineWidth = 0.5;
    for (let x = 0; x <= worldSize; x++) {
      ctx.beginPath();
      ctx.moveTo(startX + x * TILE_SIZE, startY);
      ctx.lineTo(startX + x * TILE_SIZE, startY + totalH);
      ctx.stroke();
    }
    for (let y = 0; y <= worldSize; y++) {
      ctx.beginPath();
      ctx.moveTo(startX, startY + y * TILE_SIZE);
      ctx.lineTo(startX + totalW, startY + y * TILE_SIZE);
      ctx.stroke();
    }

    for (const parcel of parcels) {
      const px = startX + parcel.x * TILE_SIZE;
      const py = startY + parcel.y * TILE_SIZE;
      if (parcel.owner_id) {
        const sg = ctx.createLinearGradient(px, py, px, py + TILE_SIZE);
        sg.addColorStop(0, '#1a3a5c');
        sg.addColorStop(1, '#1d3f62');
        ctx.fillStyle = sg;
        ctx.fillRect(px + 0.5, py + 0.5, TILE_SIZE - 1, TILE_SIZE - 1);
        ctx.strokeStyle = 'rgba(0, 180, 255, 0.25)';
        ctx.lineWidth = 1;
        ctx.strokeRect(px + 0.5, py + 0.5, TILE_SIZE - 1, TILE_SIZE - 1);

        for (const plot of parcel.plots) {
          const plotX = px + 1 + plot.local_x * PLOT_SIZE;
          const plotY = py + 1 + plot.local_y * PLOT_SIZE;
          if (plot.crop_type && plot.growth_stage !== 'empty') {
            const color = CROP_COLORS[plot.crop_type] || '#4488aa';
            let opacity = STAGE_OPACITY[plot.growth_stage] || 0.3;
            if (plot.growth_stage === 'mature' && plot.health < 1.0) opacity *= (0.4 + plot.health * 0.6);
            if (plot.is_dead) { opacity = 0.15; ctx.fillStyle = '#555'; }
            else { ctx.fillStyle = color; }
            ctx.globalAlpha = opacity;
            let sm = 0.4;
            if (plot.growth_stage === 'sprouting') sm = 0.6;
            else if (plot.growth_stage === 'growing') sm = 0.8;
            else if (plot.growth_stage === 'mature') sm = 0.9;
            const cr = ((PLOT_SIZE - 2) / 2) * sm;
            const ccx = plotX + PLOT_SIZE / 2;
            const ccy = plotY + PLOT_SIZE / 2;
            if (!plot.is_dead) { drawCoralShape(ctx, plot.crop_type, ccx, ccy, cr, t); }
            else { ctx.beginPath(); ctx.arc(ccx, ccy, cr * 0.5, 0, Math.PI * 2); ctx.fill(); }
            if (plot.growth_stage === 'mature' && !plot.is_dead) {
              const gi = 4 + Math.sin(t * 2 + plot.local_x * 3 + plot.local_y * 5) * 2;
              ctx.shadowColor = color;
              ctx.shadowBlur = gi * plot.health;
              ctx.fillStyle = color;
              ctx.globalAlpha = 0.3 * plot.health;
              ctx.beginPath();
              ctx.arc(ccx, ccy, cr * 0.5, 0, Math.PI * 2);
              ctx.fill();
              ctx.shadowBlur = 0;
            }
            ctx.globalAlpha = 1;
          }
        }
        if (selectedParcelId === parcel.id) {
          ctx.strokeStyle = '#00ffff';
          ctx.lineWidth = 2;
          ctx.shadowColor = '#00ffff';
          ctx.shadowBlur = 8;
          ctx.strokeRect(px, py, TILE_SIZE, TILE_SIZE);
          ctx.shadowBlur = 0;
        }
      } else {
        const dist = Math.max(Math.abs(parcel.x - 9.5), Math.abs(parcel.y - 9.5));
        if (dist <= 4) { ctx.fillStyle = 'rgba(0, 255, 100, 0.02)'; ctx.fillRect(px + 1, py + 1, TILE_SIZE - 2, TILE_SIZE - 2); }
        else if (dist <= 7) { ctx.fillStyle = 'rgba(255, 200, 0, 0.015)'; ctx.fillRect(px + 1, py + 1, TILE_SIZE - 2, TILE_SIZE - 2); }
      }
    }

    for (const parcel of parcels) {
      if (!parcel.owner_id) continue;
      if (!parcel.plots.some(p => p.crop_type)) continue;
      const bpx = startX + parcel.x * TILE_SIZE + TILE_SIZE / 2;
      const bpy = startY + parcel.y * TILE_SIZE;
      const bo = ((t * 10 + parcel.x * 7 + parcel.y * 13) % 30);
      ctx.beginPath();
      ctx.arc(bpx + Math.sin(parcel.x + t) * 3, bpy - bo, 1.2, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(150, 220, 255, 0.12)';
      ctx.fill();
    }

    if (hoveredParcel) {
      const hx = startX + hoveredParcel.x * TILE_SIZE;
      const hy = startY + hoveredParcel.y * TILE_SIZE - 28;
      const label = hoveredParcel.owner_name
        ? hoveredParcel.owner_name + "'s reef"
        : 'Unclaimed (' + hoveredParcel.x + ', ' + hoveredParcel.y + ') - ' + (hoveredParcel.price > 0 ? hoveredParcel.price + ' SD' : 'FREE');
      ctx.font = '10px monospace';
      const tw = ctx.measureText(label).width + 12;
      ctx.fillStyle = 'rgba(0, 20, 40, 0.9)';
      ctx.strokeStyle = 'rgba(0, 180, 255, 0.5)';
      ctx.lineWidth = 1;
      const rx = hx - 2, ry = hy - 2, rw = tw, rh = 18, rr = 4;
      ctx.beginPath();
      ctx.moveTo(rx + rr, ry);
      ctx.lineTo(rx + rw - rr, ry);
      ctx.quadraticCurveTo(rx + rw, ry, rx + rw, ry + rr);
      ctx.lineTo(rx + rw, ry + rh - rr);
      ctx.quadraticCurveTo(rx + rw, ry + rh, rx + rw - rr, ry + rh);
      ctx.lineTo(rx + rr, ry + rh);
      ctx.quadraticCurveTo(rx, ry + rh, rx, ry + rh - rr);
      ctx.lineTo(rx, ry + rr);
      ctx.quadraticCurveTo(rx, ry, rx + rr, ry);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
      ctx.fillStyle = '#8cf';
      ctx.fillText(label, hx + 4, hy + 11);
    }

    ctx.restore();
    animFrameRef.current = requestAnimationFrame(draw);
  }, [parcels, worldSize, offset, zoom, selectedParcelId, hoveredParcel, TILE_SIZE, PLOT_SIZE]);

  useEffect(() => {
    animFrameRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(animFrameRef.current);
  }, [draw]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;
    const resize = () => { canvas.width = container.clientWidth; canvas.height = container.clientHeight; };
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
    const sx = -(worldSize * TILE_SIZE) / 2;
    const sy = -(worldSize * TILE_SIZE) / 2;
    const gx = Math.floor((wx - sx) / TILE_SIZE);
    const gy = Math.floor((wy - sy) / TILE_SIZE);
    if (gx < 0 || gx >= worldSize || gy < 0 || gy >= worldSize) return null;
    return parcelMap.current.get(gx + ',' + gy) || null;
  }, [offset, zoom, worldSize, TILE_SIZE]);

  const handleMouseDown = (e: React.MouseEvent) => { setIsDragging(true); setDragStart({ x: e.clientX - offset.x, y: e.clientY - offset.y }); };
  const handleMouseMove = (e: React.MouseEvent) => {
    if (isDragging) setOffset({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
    setHoveredParcel(getParcelAt(e.clientX, e.clientY));
  };
  const handleMouseUp = (e: React.MouseEvent) => {
    if (isDragging) {
      const dx = Math.abs(e.clientX - (dragStart.x + offset.x));
      const dy = Math.abs(e.clientY - (dragStart.y + offset.y));
      if (dx < 3 && dy < 3) { const p = getParcelAt(e.clientX, e.clientY); if (p) onParcelClick(p); }
    }
    setIsDragging(false);
  };
  const handleWheel = (e: React.WheelEvent) => { e.preventDefault(); setZoom(z => Math.max(0.3, Math.min(5, z * (e.deltaY > 0 ? 0.9 : 1.1)))); };

  return (
    <div ref={containerRef} className="w-full h-full relative overflow-hidden cursor-grab active:cursor-grabbing">
      <canvas ref={canvasRef} onMouseDown={handleMouseDown} onMouseMove={handleMouseMove} onMouseUp={handleMouseUp} onMouseLeave={() => { setIsDragging(false); setHoveredParcel(null); }} onWheel={handleWheel} className="w-full h-full" />
      <div className="absolute bottom-4 right-4 flex flex-col gap-2">
        <button onClick={() => setZoom(z => Math.min(5, z * 1.3))} className="w-8 h-8 rounded-full bg-slate-800/80 border border-cyan-500/30 text-cyan-300 flex items-center justify-center hover:bg-slate-700/80 text-lg font-bold">+</button>
        <button onClick={() => setZoom(z => Math.max(0.3, z / 1.3))} className="w-8 h-8 rounded-full bg-slate-800/80 border border-cyan-500/30 text-cyan-300 flex items-center justify-center hover:bg-slate-700/80 text-lg font-bold">-</button>
        <button onClick={() => { setZoom(1); setOffset({ x: 0, y: 0 }); }} className="w-8 h-8 rounded-full bg-slate-800/80 border border-cyan-500/30 text-cyan-300 flex items-center justify-center hover:bg-slate-700/80 text-xs">R</button>
      </div>
    </div>
  );
}
