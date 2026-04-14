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
}

export interface VoteCardPayload {
  type: "vote_card";
  title: string;
  room_id: string;
  meeting_id?: number;
  time_options: VoteCardTimeOption[];
  headcount: number;
}

export interface VoteUpdatePayload {
  type: "vote_update";
  meeting_id: number;
  votes: Record<string, number>;
  total_voters: number;
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
    typeof candidate.headcount === "number"
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
  return (
    candidate.type === "place_recommendation" &&
    typeof candidate.room_id === "string" &&
    typeof candidate.place_hint === "string" &&
    Array.isArray(candidate.recommendations)
  );
}

function isMaedeupCardPayload(data: unknown): data is MaedeupCardPayload {
  if (!data || typeof data !== "object") {
    return false;
  }

  const candidate = data as Partial<MaedeupCardPayload>;
  return (
    candidate.type === "maedeup_card" &&
    typeof candidate.title === "string" &&
    typeof candidate.meeting_type === "string" &&
    typeof candidate.date_hint === "string" &&
    typeof candidate.headcount === "number" &&
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

function getReconnectDelay(attempt: number): number {
  return Math.min(1000 * 2 ** attempt, MAX_RECONNECT_DELAY_MS);
}

export function useAgentWebSocket(roomId: string, sender: string, options?: AgentOptions) {
  const [messages, setMessages] = useState<ChatMessagePayload[]>([]);
  const [voteCard, setVoteCard] = useState<VoteCardPayload | null>(null);
  const [voteUpdate, setVoteUpdate] = useState<VoteUpdatePayload | null>(null);
  const [placeRecommendation, setPlaceRecommendation] =
    useState<PlaceRecommendationPayload | null>(null);
  const [maedeupCard, setMaedeupCard] = useState<MaedeupCardPayload | null>(null);
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
    setVoteCard(null);
    setVoteUpdate(null);
    setPlaceRecommendation(null);
    setMaedeupCard(null);
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

        if (isVoteCardPayload(parsed)) {
          setVoteCard(parsed);
          setVoteUpdate(null);
          return;
        }

        if (isVoteUpdatePayload(parsed)) {
          setVoteUpdate(parsed);
          return;
        }

        if (isPlaceRecommendationPayload(parsed)) {
          setPlaceRecommendation(parsed);
          return;
        }

        if (isMaedeupCardPayload(parsed)) {
          setMaedeupCard(parsed);
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

  return {
    messages,
    sendMessage,
    status,
    voteCard,
    voteUpdate,
    placeRecommendation,
    maedeupCard,
    autoTrigger,
    dismissAutoTrigger,
    meetingSummary,
  };
}
