import { Stats } from '../lib/api';

interface StatsBarProps {
  stats: Stats | null;
}

export default function StatsBar({ stats }: StatsBarProps) {
  if (!stats) return null;

  const items = [
    { label: 'Agents', value: stats.total_agents, icon: '🐙' },
    { label: 'Claimed', value: `${stats.claimed_parcels}/${stats.total_parcels}`, icon: '🏴' },
    { label: 'Crops', value: stats.active_crops, icon: '🌱' },
    { label: 'Points', value: stats.total_points_earned.toLocaleString(), icon: '✨' },
    { label: 'Actions', value: stats.total_actions, icon: '🔵' },
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
