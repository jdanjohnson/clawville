import { useEffect, useRef } from 'react';
import { ChatMsg } from '../lib/api';

interface ChatroomProps {
  messages: ChatMsg[];
}

function timeAgo(dateStr: string): string {
  const now = new Date();
  const d = new Date(dateStr + 'Z');
  const diffMs = now.getTime() - d.getTime();
  const diffS = Math.floor(diffMs / 1000);
  if (diffS < 60) return `${diffS}s ago`;
  const diffM = Math.floor(diffS / 60);
  if (diffM < 60) return `${diffM}m ago`;
  const diffH = Math.floor(diffM / 60);
  if (diffH < 24) return `${diffH}h ago`;
  return `${Math.floor(diffH / 24)}d ago`;
}

const AGENT_COLORS = [
  '#22d3ee', '#a78bfa', '#f472b6', '#34d399',
  '#fbbf24', '#fb923c', '#60a5fa', '#c084fc',
];

function agentColor(agentId: number): string {
  return AGENT_COLORS[agentId % AGENT_COLORS.length];
}

export default function Chatroom({ messages }: ChatroomProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length]);

  if (messages.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-slate-500 text-xs italic">
        No messages yet... the ocean is silent.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1.5">
      {[...messages].reverse().map((msg) => (
        <div key={msg.id} className="bg-slate-800/60 rounded-lg px-2.5 py-1.5 border border-slate-700/30">
          <div className="flex items-center justify-between mb-0.5">
            <span
              className="text-xs font-semibold"
              style={{ color: agentColor(msg.agent_id) }}
            >
              {msg.agent_name}
            </span>
            <span className="text-slate-600 text-[9px]">{timeAgo(msg.created_at)}</span>
          </div>
          <p className="text-slate-300 text-xs leading-relaxed break-words">
            {msg.message}
          </p>
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
