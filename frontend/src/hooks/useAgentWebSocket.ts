"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ChatMessagePayload } from "@/types";

export type { ChatMessagePayload };

export interface VoteCardTimeOption {
  slot_id: string;
  label: string;
  start_at: string;
  end_at: string;
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
  score: number;
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

type AgentCardPayload =
  | VoteCardPayload
  | VoteUpdatePayload
  | PlaceRecommendationPayload
  | MaedeupCardPayload;

type WsStatus = "connecting" | "open" | "closed" | "error";

interface AgentOptions {
  /** Called when AI response suggests switching context (e.g. pane_type: "place") */
  onPaneSwitch?: (paneType: string) => void;
}

export function useAgentWebSocket(roomId: string, sender: string, options?: AgentOptions) {
  const [messages, setMessages] = useState<ChatMessagePayload[]>([]);
  const [voteCard, setVoteCard] = useState<VoteCardPayload | null>(null);
  const [voteUpdate, setVoteUpdate] = useState<VoteUpdatePayload | null>(null);
  const [placeRecommendation, setPlaceRecommendation] =
    useState<PlaceRecommendationPayload | null>(null);
  const [maedeupCard, setMaedeupCard] = useState<MaedeupCardPayload | null>(null);
  const [status, setStatus] = useState<WsStatus>("connecting");
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const shouldReconnectRef = useRef(true);

  useEffect(() => {
    const token = localStorage.getItem("auth_token");
    if (!token) {
      window.location.href = "/";
      return;
    }

    // 이전 에이전트 메시지 로드
    const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    const roomPk = /^\d+$/.test(roomId) ? roomId : null;
    if (roomPk) {
      fetch(
        `${apiBase}/api/v1/chat/messages?pane_type=agent&room_id=${roomPk}&limit=50`,
        { headers: { Authorization: `Bearer ${token}` } }
      )
        .then((r) => r.json())
        .then((data) => {
          if (Array.isArray(data)) setMessages(data as ChatMessagePayload[]);
        })
        .catch(() => {/* ignore */});
    }

    const wsBase = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";
    const scheduleReconnect = (code?: number) => {
      if (!shouldReconnectRef.current) return;
      if (code === 4001) return;
      if (reconnectTimeoutRef.current !== null) return;
      if (reconnectAttemptsRef.current >= 5) return;

      const delay = 1000 * (2 ** reconnectAttemptsRef.current);
      reconnectAttemptsRef.current += 1;
      reconnectTimeoutRef.current = window.setTimeout(() => {
        reconnectTimeoutRef.current = null;
        connect();
      }, delay);
    };

    const connect = () => {
      setStatus("connecting");
      const ws = new WebSocket(
        `${wsBase}/ws/agent/${roomId}?token=${encodeURIComponent(token)}`
      );
      wsRef.current = ws;

      ws.onopen = () => {
        if (reconnectTimeoutRef.current !== null) {
          window.clearTimeout(reconnectTimeoutRef.current);
          reconnectTimeoutRef.current = null;
        }
        reconnectAttemptsRef.current = 0;
        setStatus("open");
      };

      ws.onmessage = (event) => {
        let parsed: ChatMessagePayload | AgentCardPayload;
        try {
          parsed = JSON.parse(event.data as string) as ChatMessagePayload | AgentCardPayload;
        } catch {
          return;
        }

        if ("type" in parsed) {
          if (parsed.type === "vote_card") {
            setVoteCard(parsed);
          } else if (parsed.type === "vote_update") {
            setVoteUpdate(parsed);
          } else if (parsed.type === "place_recommendation") {
            setPlaceRecommendation(parsed);
          } else if (parsed.type === "maedeup_card") {
            setMaedeupCard(parsed);
          }
          return;
        }

        const msg = parsed;
        setMessages((prev) => {
          // 중복 방지 (REST 로드 후 WS에서 같은 메시지가 올 경우)
          if (msg.id && prev.some((m) => m.id === msg.id)) return prev;
          return [...prev, msg];
        });

        // Auto-switch context panel based on AI pane_type
        if (msg.pane_type && options?.onPaneSwitch) {
          options.onPaneSwitch(msg.pane_type);
        }
      };

      ws.onerror = () => {
        setStatus("error");
        scheduleReconnect(0);
      };

      ws.onclose = (event) => {
        setStatus("closed");
        // 1008: Policy Violation - 토큰 없음 또는 만료
        if (event.code === 1008) {
          shouldReconnectRef.current = false;
          localStorage.removeItem("auth_token");
          window.location.href = "/";
          return;
        }
        scheduleReconnect(event.code);
      };
    };

    shouldReconnectRef.current = true;
    reconnectAttemptsRef.current = 0;
    connect();

    return () => {
      shouldReconnectRef.current = false;
      if (reconnectTimeoutRef.current !== null) {
        window.clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      const ws = wsRef.current;
      if (ws) {
        ws.close();
      }
    };
  }, [roomId]);

  const sendMessage = useCallback(
    (content: string) => {
      const ws = wsRef.current;
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ role: "user", content, sender }));
      }
    },
    [sender]
  );

  return {
    messages,
    sendMessage,
    status,
    voteCard,
    voteUpdate,
    placeRecommendation,
    maedeupCard,
  };
}
