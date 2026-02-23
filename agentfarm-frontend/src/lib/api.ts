const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface Agent {
  id: number;
  name: string;
  api_token: string;
  score: number;
  created_at: string;
}

export interface Plot {
  local_x: number;
  local_y: number;
  crop_type: string | null;
  crop_name: string | null;
  growth_stage: string;
  planted_at: string | null;
  watered_at: string | null;
  ready_at: string | null;
  progress_pct: number;
}

export interface Parcel {
  id: number;
  x: number;
  y: number;
  owner_id: number | null;
  owner_name: string | null;
  claimed_at: string | null;
  plots: Plot[];
}

export interface WorldData {
  world_size: number;
  total_parcels: number;
  claimed_parcels: number;
  total_agents: number;
  parcels: Parcel[];
}

export interface Activity {
  id: number;
  agent_name: string | null;
  action: string;
  details: string | null;
  created_at: string;
}

export interface CropInfo {
  key: string;
  name: string;
  grow_time_minutes: number;
  points: number;
  emoji: string;
  color: string;
}

export interface LeaderboardEntry {
  rank: number;
  agent_name: string;
  score: number;
}

export interface Stats {
  total_agents: number;
  claimed_parcels: number;
  total_parcels: number;
  active_crops: number;
  total_points_earned: number;
  total_actions: number;
}

export interface ChatMsg {
  id: number;
  agent_id: number;
  agent_name: string;
  message: string;
  created_at: string;
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'API error');
  }
  return res.json();
}

export const api = {
  getWorld: () => apiFetch<WorldData>('/api/world'),
  getStats: () => apiFetch<Stats>('/api/stats'),
  getActivity: (limit = 30) => apiFetch<Activity[]>(`/api/world/activity?limit=${limit}`),
  getCrops: () => apiFetch<CropInfo[]>('/api/crops'),
  getLeaderboard: (limit = 20) => apiFetch<LeaderboardEntry[]>(`/api/leaderboard?limit=${limit}`),
  getParcel: (id: number) => apiFetch<Parcel>(`/api/parcels/${id}`),
  getChat: (limit = 50, sinceId = 0) => apiFetch<ChatMsg[]>(`/api/chat?limit=${limit}&since_id=${sinceId}`),
};
