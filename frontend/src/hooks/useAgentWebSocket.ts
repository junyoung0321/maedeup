"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ChatMessagePayload } from "@/types";

export type { ChatMessagePayload };

export interface VoteCardTimeOption {
  slot_id: string;
  label: string;
  start_at: string;
  end_at: string;
  is_holiday?: boolean;
  holiday_name?: string | null;
  is_weekend?: boolean;
  // PR-Y1 (F1 fallback): 슬롯별 가능자 수 + 불참자 명단 (다수결 추천 시).
  available_count?: number;
  total_count?: number;
  unavailable_users?: string[];
}

export type VoteCardCalendarStrategy =
  | "all_members_available"
  | "n_minus_one"
  | "multi_date_vote"
  | "preference_based"
  | "natural_language_time_options"
  | "majority_fallback";

export type VoteCardBlockerNotification =
  | {
      type: "social_system_message";
      reason?: string;
      [key: string]: unknown;
    }
  | {
      type: "f1_fallback";
      reason: string;
      missing_count: number;
      total_count: number;
      max_available_count: number;
    };

export interface VoteCardPayload {
  type: "vote_card";
  title: string;
  room_id: string;
  meeting_id?: number;
  time_options: VoteCardTimeOption[];
  headcount: number | null;
  calendar_strategy?: VoteCardCalendarStrategy | string | null;
  blocker_notification?: VoteCardBlockerNotification | null;
  // PR-Z1/Z2 (Q5 hybrid): 추천 기준 출처 및 토글 가능 여부.
  // 기본값은 "group" (다수결). 발화자/방장이 "내 선호" 기준으로 재추천 요청 가능.
  preference_source?: "group" | "speaker";
  preference_toggle_enabled?: boolean;
  // P0 hydration: pending-vote 복구 시 서버가 본인 투표 인덱스를 미리 추출해 내려줌.
  // WS vote_card 이벤트에는 없는 필드 (undefined). null = 미투표.
  current_user_vote?: number | null;
}

export interface VoteUpdatePayload {
  type: "vote_update";
  meeting_id: number;
  votes: Record<string, number>;
  total_voters: number;
  user_votes?: Record<string, number>;
}

export interface PlaceRecommendationItem {
  place_id: string;
  name: string;
  address: string;
  category: string;
  url: string;
  phone?: string;
  x?: string;
  y?: string;
  score: number;
  distance_m?: number;
  reason?: string;
}

export interface PlaceRecommendationPayload {
  type: "place_recommendation";
  room_id: string;
  place_hint: string;
  recommendations: PlaceRecommendationItem[];
  // A5-2: 백엔드가 _build_named_constraints_summary로 박는 멤버별 제약 요약.
  // 시드된 PersonalData가 있으면 이름+✨ 인용, 없으면 익명 그룹 톤.
  group_constraints_summary?: string;
  // PR-Z1/Z2 (Q5 hybrid): 추천 기준 출처 및 토글 가능 여부.
  preference_source?: "group" | "speaker";
  preference_toggle_enabled?: boolean;
}

// PR-Z1/Z2 (Q5 hybrid): 백엔드 §10에 명시된 narrator broadcast 메시지.
// 발행 시 일반 chat message가 아닌 별도 type으로 받을 수 있음.
// (현재 본 hook은 별도 처리하지 않고 chat message 흐름으로 흘려보냄 —
//  필요 시 추후 분기 추가)
export interface RefreshNarratorMessage {
  type: "preference_refresh_narrator";
  room_id: string;
  meeting_id: number;
  preference_source: "group" | "speaker";
  requester_user_id: number;
  content: string;
}

export interface MaedeupCardSelectionTime {
  label: string;
  start_at: string;
  end_at: string;
}

export interface MaedeupCardSelectionPlace {
  name: string;
  address: string;
}

export interface MaedeupCardPayload {
  type: "maedeup_card";
  title: string;
  meeting_type: string;
  date_hint: string;
  headcount: number;
  selected_time: MaedeupCardSelectionTime;
  selected_place: MaedeupCardSelectionPlace;
}

export type VotePayload = VoteCardPayload & { meeting_id?: number };
export type PlacePayload = PlaceRecommendationPayload & { meeting_id?: number };
export type MaedeupPayload = Omit<MaedeupCardPayload, "headcount" | "selected_place"> & {
  meeting_id?: number;
  headcount: number | null;
  selected_place: MaedeupCardSelectionPlace | Record<string, never>;
  date?: string | null;
  time?: string | { label?: string } | null;
  place?: string | null;
  place_pending?: boolean;
  place_pending_message?: string;
  calendar_registered?: boolean;
};

export type CardPayload =
  | { type: "vote_card"; meeting_id: number; payload: VotePayload }
  | { type: "place_recommendation"; meeting_id: number; payload: PlacePayload }
  | { type: "maedeup_card"; meeting_id: number; payload: MaedeupPayload };

export interface MeetingSummaryPayload {
  type: "meeting_summary";
  date?: string | null;
  place?: string | null;
  headcount?: string | null;
  meeting_type?: string | null;
  notes?: string[];
}

export interface AiAutoTriggerPayload {
  type: "ai_auto_trigger";
  intent: string;
  confidence: number;
  content: string;
  trigger_message_id: number;
}

type WsStatus = "connecting" | "open" | "closed" | "error";

interface AgentOptions {
  onPaneSwitch?: (paneType: string) => void;
}

const MAX_RECONNECT_ATTEMPTS = 5;
const MAX_RECONNECT_DELAY_MS = 30_000;

function isChatMessagePayload(data: unknown): data is ChatMessagePayload {
  if (!data || typeof data !== "object") {
    return false;
  }

  const candidate = data as Partial<ChatMessagePayload>;
  return (
    typeof candidate.id === "number" &&
    typeof candidate.pane_type === "string" &&
    typeof candidate.role === "string" &&
    typeof candidate.content === "string" &&
    typeof candidate.created_at === "string"
  );
  // visibility / user_id / shared_from_id / shared_by_user_id are optional;
  // the hook passes them through unchanged if present.
}

function isVoteCardPayload(data: unknown): data is VoteCardPayload {
  if (!data || typeof data !== "object") {
    return false;
  }

  const candidate = data as Partial<VoteCardPayload>;
  return (
    candidate.type === "vote_card" &&
    typeof candidate.title === "string" &&
    typeof candidate.room_id === "string" &&
    Array.isArray(candidate.time_options) &&
    (typeof candidate.headcount === "number" || candidate.headcount === null)
  );
}

function isVoteUpdatePayload(data: unknown): data is VoteUpdatePayload {
  if (!data || typeof data !== "object") {
    return false;
  }

  const candidate = data as Partial<VoteUpdatePayload>;
  return (
    candidate.type === "vote_update" &&
    typeof candidate.meeting_id === "number" &&
    typeof candidate.total_voters === "number" &&
    typeof candidate.votes === "object" &&
    candidate.votes !== null
  );
}

function isPlaceRecommendationPayload(data: unknown): data is PlaceRecommendationPayload {
  if (!data || typeof data !== "object") {
    return false;
  }

  const candidate = data as Partial<PlaceRecommendationPayload>;
  const summaryOk =
    candidate.group_constraints_summary === undefined ||
    typeof candidate.group_constraints_summary === "string";
  return (
    candidate.type === "place_recommendation" &&
    typeof candidate.room_id === "string" &&
    typeof candidate.place_hint === "string" &&
    Array.isArray(candidate.recommendations) &&
    summaryOk
  );
}

function isMaedeupCardPayload(data: unknown): data is MaedeupPayload {
  if (!data || typeof data !== "object") {
    return false;
  }

  const candidate = data as Partial<MaedeupCardPayload>;
  return (
    candidate.type === "maedeup_card" &&
    typeof candidate.title === "string" &&
    typeof candidate.meeting_type === "string" &&
    typeof candidate.date_hint === "string" &&
    (typeof candidate.headcount === "number" || candidate.headcount === null) &&
    typeof candidate.selected_time === "object" &&
    candidate.selected_time !== null &&
    typeof candidate.selected_place === "object" &&
    candidate.selected_place !== null
  );
}

function isMeetingSummaryPayload(data: unknown): data is MeetingSummaryPayload {
  if (!data || typeof data !== "object") {
    return false;
  }

  const candidate = data as Partial<MeetingSummaryPayload>;
  return candidate.type === "meeting_summary";
}

function isAiAutoTriggerPayload(data: unknown): data is AiAutoTriggerPayload {
  if (!data || typeof data !== "object") {
    return false;
  }

  const candidate = data as Partial<AiAutoTriggerPayload>;
  return (
    candidate.type === "ai_auto_trigger" &&
    typeof candidate.intent === "string" &&
    typeof candidate.confidence === "number" &&
    typeof candidate.content === "string" &&
    typeof candidate.trigger_message_id === "number"
  );
}

function getMeetingId(data: unknown): number | null {
  if (!data || typeof data !== "object") {
    return null;
  }

  const candidate = data as { meeting_id?: unknown };
  if (typeof candidate.meeting_id === "number" && Number.isFinite(candidate.meeting_id)) {
    return candidate.meeting_id;
  }
  if (typeof candidate.meeting_id === "string" && /^\d+$/.test(candidate.meeting_id)) {
    return Number(candidate.meeting_id);
  }
  return null;
}

function toCardPayload(data: unknown): CardPayload | null {
  const meetingId = getMeetingId(data);
  if (meetingId === null) {
    return null;
  }
  if (isVoteCardPayload(data)) {
    return { type: "vote_card", meeting_id: meetingId, payload: data };
  }
  if (isPlaceRecommendationPayload(data)) {
    return { type: "place_recommendation", meeting_id: meetingId, payload: data };
  }
  if (isMaedeupCardPayload(data)) {
    return { type: "maedeup_card", meeting_id: meetingId, payload: data };
  }
  return null;
}

// BUG-26-G: manual pick 후 첫 추천 메시지 본문 실시간 반영.
interface ChatMessageUpdatePayload {
  type: "chat_message_update";
  id: number;
  content: string;
}

function isChatMessageUpdatePayload(data: unknown): data is ChatMessageUpdatePayload {
  if (!data || typeof data !== "object") {
    return false;
  }
  const candidate = data as Partial<ChatMessageUpdatePayload>;
  return (
    candidate.type === "chat_message_update" &&
    typeof candidate.id === "number" &&
    typeof candidate.content === "string"
  );
}

function isMeetingResolvedPayload(data: unknown): data is { type: "meeting_confirmed" | "meeting_cancelled"; meeting_id: number } {
  if (!data || typeof data !== "object") {
    return false;
  }

  const candidate = data as { type?: unknown; meeting_id?: unknown };
  return (
    (candidate.type === "meeting_confirmed" || candidate.type === "meeting_cancelled") &&
    typeof candidate.meeting_id === "number"
  );
}

function getReconnectDelay(attempt: number): number {
  return Math.min(1000 * 2 ** attempt, MAX_RECONNECT_DELAY_MS);
}

export function useAgentWebSocket(roomId: string, sender: string, options?: AgentOptions) {
  const [messages, setMessages] = useState<ChatMessagePayload[]>([]);
  const [cardsByMeetingId, setCardsByMeetingId] = useState<Record<number, CardPayload>>({});
  const [voteUpdate, setVoteUpdate] = useState<VoteUpdatePayload | null>(null);
  const [autoTrigger, setAutoTrigger] = useState<AiAutoTriggerPayload | null>(null);
  const [meetingSummary, setMeetingSummary] = useState<MeetingSummaryPayload | null>(null);
  const [status, setStatus] = useState<WsStatus>("connecting");
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const shouldReconnectRef = useRef(true);
  const onPaneSwitchRef = useRef<AgentOptions["onPaneSwitch"]>(options?.onPaneSwitch);

  useEffect(() => {
    onPaneSwitchRef.current = options?.onPaneSwitch;
  }, [options?.onPaneSwitch]);

  useEffect(() => {
    const token = localStorage.getItem("auth_token");
    if (!token) {
      window.location.href = "/";
      return;
    }

    let isActive = true;

    setMessages([]);
    setCardsByMeetingId({});
    setVoteUpdate(null);
    setAutoTrigger(null);
    setMeetingSummary(null);

    const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    const wsBase = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";
    const roomPk = /^\d+$/.test(roomId) ? roomId : null;

    if (roomPk) {
      fetch(`${apiBase}/api/v1/chat/messages?pane_type=agent&room_id=${roomPk}&limit=50`, {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then(async (response) => {
          if (!response.ok) {
            throw new Error(`Failed to load agent messages: ${response.status}`);
          }
          return response.json();
        })
        .then((data: unknown) => {
          if (!isActive || !Array.isArray(data)) {
            return;
          }
          const nextMessages = data.filter(isChatMessagePayload);
          setMessages(nextMessages);
        })
        .catch(() => {
          if (!isActive) {
            return;
          }
          setMessages([]);
        });

      // 진행 중인 투표 카드 복구 — 새로고침해도 AI 추천 날짜가 유지되도록.
      fetch(`${apiBase}/api/v1/meetings/rooms/${roomPk}/pending-vote`, {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((response) => (response.ok ? response.json() : null))
        .then((data: unknown) => {
          if (!isActive || !data) {
            return;
          }
          const card = toCardPayload(data);
          if (card) {
            setCardsByMeetingId((prev) => ({ ...prev, [card.meeting_id]: card }));
          }
        })
        .catch(() => {
          /* 복구 실패 시 조용히 무시 */
        });

      // 장소 추천 카드 복구 — Redis 캐시에서 로드.
      fetch(`${apiBase}/api/v1/meetings/rooms/${roomPk}/pending-place`, {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((response) => (response.ok ? response.json() : null))
        .then((data: unknown) => {
          if (!isActive || !data) {
            return;
          }
          const card = toCardPayload(data);
          if (card) {
            setCardsByMeetingId((prev) => ({ ...prev, [card.meeting_id]: card }));
          }
        })
        .catch(() => {
          /* 복구 실패 시 조용히 무시 */
        });
    }

    const clearReconnectTimeout = () => {
      if (reconnectTimeoutRef.current !== null) {
        window.clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
    };

    const cleanupSocket = (socket: WebSocket) => {
      socket.onopen = null;
      socket.onmessage = null;
      socket.onerror = null;
      socket.onclose = null;
    };

    const scheduleReconnect = (socket: WebSocket, code?: number) => {
      if (!isActive || !shouldReconnectRef.current || wsRef.current !== socket) {
        return;
      }
      if (code === 4001 || code === 1008) {
        return;
      }
      if (reconnectTimeoutRef.current !== null) {
        return;
      }
      if (reconnectAttemptsRef.current >= MAX_RECONNECT_ATTEMPTS) {
        return;
      }

      const delay = getReconnectDelay(reconnectAttemptsRef.current);
      reconnectAttemptsRef.current += 1;
      reconnectTimeoutRef.current = window.setTimeout(() => {
        reconnectTimeoutRef.current = null;
        connect();
      }, delay);
    };

    const connect = () => {
      if (!isActive) {
        return;
      }

      clearReconnectTimeout();
      setStatus("connecting");

      const socket = new WebSocket(`${wsBase}/ws/agent/${roomId}?token=${encodeURIComponent(token)}`);
      wsRef.current = socket;

      socket.onopen = () => {
        if (!isActive || wsRef.current !== socket) {
          socket.close();
          return;
        }

        clearReconnectTimeout();
        reconnectAttemptsRef.current = 0;
        setStatus("open");
      };

      socket.onmessage = (event) => {
        if (!isActive || wsRef.current !== socket) {
          return;
        }

        let parsed: unknown;
        try {
          parsed = JSON.parse(event.data as string);
        } catch {
          return;
        }

        if (isAiAutoTriggerPayload(parsed)) {
          setAutoTrigger(parsed);
          return;
        }

        if (isMeetingSummaryPayload(parsed)) {
          setMeetingSummary(parsed);
          return;
        }

        const card = toCardPayload(parsed);
        if (card) {
          setCardsByMeetingId((prev) => ({ ...prev, [card.meeting_id]: card }));
          if (card.type === "vote_card") {
            setVoteUpdate(null);
          }
          return;
        }

        if (isMeetingResolvedPayload(parsed)) {
          setCardsByMeetingId((prev) => {
            if (!prev[parsed.meeting_id]) {
              return prev;
            }
            const next = { ...prev };
            delete next[parsed.meeting_id];
            return next;
          });
          setVoteUpdate(null);
          return;
        }

        if (isVoteUpdatePayload(parsed)) {
          setVoteUpdate(parsed);
          return;
        }

        // BUG-26-G: manual pick 후 첫 추천 메시지 본문 실시간 업데이트.
        if (isChatMessageUpdatePayload(parsed)) {
          setMessages((prev) =>
            prev.map((message) =>
              message.id === parsed.id ? { ...message, content: parsed.content } : message,
            ),
          );
          return;
        }

        if (!isChatMessagePayload(parsed)) {
          return;
        }

        setMessages((prev) => {
          if (prev.some((message) => message.id === parsed.id)) {
            return prev;
          }
          return [...prev, parsed];
        });

        if (parsed.pane_type && onPaneSwitchRef.current) {
          onPaneSwitchRef.current(parsed.pane_type);
        }
      };

      socket.onerror = () => {
        if (!isActive || wsRef.current !== socket) {
          return;
        }

        setStatus("error");
      };

      socket.onclose = (event) => {
        if (wsRef.current === socket) {
          wsRef.current = null;
        }

        cleanupSocket(socket);

        if (!isActive) {
          return;
        }

        setStatus("closed");
        if (event.code === 1008) {
          shouldReconnectRef.current = false;
          localStorage.removeItem("auth_token");
          window.location.href = "/";
          return;
        }

        scheduleReconnect(socket, event.code);
      };
    };

    shouldReconnectRef.current = true;
    reconnectAttemptsRef.current = 0;
    clearReconnectTimeout();
    connect();

    return () => {
      isActive = false;
      shouldReconnectRef.current = false;
      clearReconnectTimeout();

      const socket = wsRef.current;
      if (socket) {
        wsRef.current = null;
        cleanupSocket(socket);
        if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
          socket.close();
        }
      }
    };
  }, [roomId]);

  const sendMessage = useCallback(
    (content: string) => {
      const ws = wsRef.current;
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ role: "user", content, sender }));
      }
    },
    [sender],
  );

  const dismissAutoTrigger = useCallback(() => {
    setAutoTrigger(null);
  }, []);

  const removeCardByMeetingId = useCallback((meetingId: number) => {
    setCardsByMeetingId((prev) => {
      if (!prev[meetingId]) {
        return prev;
      }
      const next = { ...prev };
      delete next[meetingId];
      return next;
    });
  }, []);

  return {
    messages,
    sendMessage,
    status,
    cardsByMeetingId,
    voteUpdate,
    removeCardByMeetingId,
    autoTrigger,
    dismissAutoTrigger,
    meetingSummary,
  };
}
