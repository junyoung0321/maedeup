// ─── Place ───
export interface PlaceResult {
  id: string;
  name: string;
  address: string;
  phone: string;
  url: string;
  x: string;
  y: string;
  category: string;
}

// ─── Chat / WebSocket ───
export interface ChatMessagePayload {
  id: number;
  pane_type: string;
  role: string;
  content: string;
  sender: string | null;
  created_at: string;
}

// ─── User / Friend ───
export interface FriendInfo {
  id: number;
  name: string;
  email: string;
  picture?: string | null;
}

// ─── Meeting / Room ───
export interface Room {
  id: number;
  name: string;
  description: string | null;
  category: string | null;
  created_by: number;
  created_at: string;
}

export interface MeetingItem {
  id: string;
  name: string;
  schedule: string;
  badge: string;
  badgeColor: string;
}

// ─── Context Mode ───
export type ContextMode = "schedule" | "place" | "done" | "agent";
