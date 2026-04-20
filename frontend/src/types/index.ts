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
  distance_m?: number;
  score?: number;
}

// ─── Chat / WebSocket ───
export interface ChatMessagePayload {
  id: number;
  pane_type: string;
  role: string;
  content: string;
  sender: string | null;
  created_at: string;
  // docs/ai-separation.md §4 — visibility & sharing
  user_id?: number | null;
  visibility?: "private" | "shared" | null;
  shared_from_id?: number | null;
  shared_by_user_id?: number | null;
}

// ─── User / Friend ───
export interface FriendInfo {
  id: number;
  name: string;
  email: string;
  picture?: string | null;
}

export interface UserProfile {
  id: number;
  email: string;
  name: string;
  picture?: string | null;
  home_base?: string | null;
  food_preferences?: string[] | null;
  food_preference_note?: string | null;
  calendar_consent: boolean;
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

export interface UpcomingMeetingData {
  id: number;
  room_id: number;
  title: string;
  scheduled_at: string;
  end_at: string | null;
  location_name: string | null;
  location_address: string | null;
  status: string;
}

// ─── Context Mode ───
export type ContextMode = "schedule" | "place" | "done" | "agent";
export type AiTriggerIntent = "meeting_schedule" | "place_suggestion" | "general";
