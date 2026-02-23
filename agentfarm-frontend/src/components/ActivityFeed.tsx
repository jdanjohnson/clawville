import { Activity } from '../lib/api';

interface ActivityFeedProps {
  activities: Activity[];
}

const ACTION_ICONS: Record<string, string> = {
  registered: '🐙',
  claimed: '🏴',
  planted: '🌱',
  watered: '💧',
  harvested: '✨',
};

const ACTION_COLORS: Record<string, string> = {
  registered: 'text-purple-400',
  claimed: 'text-blue-400',
  planted: 'text-green-400',
  watered: 'text-cyan-400',
  harvested: 'text-yellow-400',
};

function timeAgo(dateStr: string): string {
  const date = new Date(dateStr + 'Z');
  const now = new Date();
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export default function ActivityFeed({ activities }: ActivityFeedProps) {
  return (
    <div className="space-y-1">
      {activities.length === 0 && (
        <p className="text-slate-500 text-sm text-center py-4 italic">
          The ocean is quiet... no activity yet.
        </p>
      )}
      {activities.map(a => (
        <div
          key={a.id}
          className="flex items-start gap-2 py-1.5 px-2 rounded-lg hover:bg-slate-800/40 transition-colors"
        >
          <span className="text-sm flex-shrink-0 mt-0.5">
            {ACTION_ICONS[a.action] || '🔵'}
          </span>
          <div className="flex-1 min-w-0">
            <p className="text-xs leading-relaxed">
              <span className={`font-medium ${ACTION_COLORS[a.action] || 'text-cyan-400'}`}>
                {a.agent_name || 'Unknown'}
              </span>{' '}
              <span className="text-slate-400">{a.details || a.action}</span>
            </p>
          </div>
          <span className="text-[10px] text-slate-600 flex-shrink-0 mt-0.5">
            {timeAgo(a.created_at)}
          </span>
        </div>
      ))}
    </div>
  );
}
