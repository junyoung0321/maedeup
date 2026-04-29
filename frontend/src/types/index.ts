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
  // Personal data extension. AI가 모임 종료 시 chat에서 추출, 또는 사용자가 직접 입력.
  food_restrictions?: string[] | null;
  liked_areas?: string[] | null;
  disliked_areas?: string[] | null;
  time_preference?: string | null;
  transport_mode?: string | null;
  // category_name → AI가 채웠는지. 사용자 수동 수정 시 false. ✨ 마크 결정.
  is_ai_filled?: Record<string, boolean>;
  calendar_consent: boolean;
  // QuickPreferences 토글 — opt-out 모델, 기본 true. OFF면 해당 카테고리는
  // group recommendation 합성에서 제외.
  share_food_data?: boolean;
  share_location_data?: boolean;
  share_schedule_data?: boolean;
}

// PersonalData ✨ 클릭 시 받는 receipts.
export interface PersonalDataSource {
  memory_type: string;
  content: {
    value: string[] | string;
    confidence: number;
    source_quote: string;
    status: string;
  };
  source_room_id: number | null;
  source_room_name: string | null;
  source_message_id: number | null;
  created_at: string;
}

// 6 personal data 카테고리 락인.
export type PersonalDataCategory =
  | "food_restrictions"
  | "food_preferences"
  | "liked_areas"
  | "disliked_areas"
  | "time_preference"
  | "transport_mode";

export const PERSONAL_DATA_CATEGORIES: PersonalDataCategory[] = [
  "food_restrictions",
  "food_preferences",
  "liked_areas",
  "disliked_areas",
  "time_preference",
  "transport_mode",
];

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
