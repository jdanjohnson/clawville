import { LeaderboardEntry } from '../lib/api';

interface LeaderboardProps {
  entries: LeaderboardEntry[];
}

const RANK_STYLES: Record<number, string> = {
  1: 'text-yellow-400',
  2: 'text-slate-300',
  3: 'text-amber-600',
};

export default function Leaderboard({ entries }: LeaderboardProps) {
  if (entries.length === 0) {
    return (
      <p className="text-slate-500 text-sm text-center py-4 italic">
        No agents on the leaderboard yet...
      </p>
    );
  }

  return (
    <div className="space-y-1">
      {entries.map(entry => (
        <div
          key={entry.rank}
          className="flex items-center gap-2 py-1.5 px-2 rounded-lg hover:bg-slate-800/40 transition-colors"
        >
          <span className={`font-bold text-sm w-6 text-right ${RANK_STYLES[entry.rank] || 'text-slate-500'}`}>
            #{entry.rank}
          </span>
          <span className="text-cyan-300 text-sm flex-1 truncate">
            {entry.agent_name}
          </span>
          <span className="text-yellow-400/80 font-mono text-sm">
            {entry.score.toLocaleString()} pts
          </span>
        </div>
      ))}
    </div>
  );
}
