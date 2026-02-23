import { Stats } from '../lib/api';

interface StatsBarProps {
  stats: Stats | null;
}

export default function StatsBar({ stats }: StatsBarProps) {
  if (!stats) return null;

  const items = [
    { label: 'Agents', value: stats.total_agents ?? 0, icon: '🐙' },
    { label: 'Claimed', value: `${stats.claimed_parcels ?? 0}/${stats.total_parcels ?? 400}`, icon: '🏴' },
    { label: 'Crops', value: stats.active_crops ?? 0, icon: '🪸' },
    { label: 'Points', value: (stats.total_points_earned ?? 0).toLocaleString(), icon: '✨' },
    { label: 'Sand $', value: (stats.total_sand_dollars ?? 0).toLocaleString(), icon: '🪙' },
    { label: 'Raids', value: stats.total_steals ?? 0, icon: '⚔️' },
  ];

  return (
    <div className="flex items-center gap-4 flex-wrap">
      {items.map(item => (
        <div key={item.label} className="flex items-center gap-1.5">
          <span className="text-sm">{item.icon}</span>
          <span className="text-cyan-300 font-mono text-sm font-bold">{item.value}</span>
          <span className="text-slate-500 text-xs">{item.label}</span>
        </div>
      ))}
    </div>
  );
}
