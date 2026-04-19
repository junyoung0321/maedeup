"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { AiTriggerIntent, ChatMessagePayload } from "@/types";

export type { ChatMessagePayload };

export interface IntentDetectedPayload {
  type: "intent_detected";
  intent: AiTriggerIntent;
  confidence: number;
  method: "rag" | "gemini" | "default";
  trigger_message_id: number;
}

export interface ReminderPayload {
  type: "reminder";
  message: string;
  meeting_id: number;
}

export interface VoteReminderPayload {
  type: "vote_reminder";
  message: string;
  meeting_id: number;
}

export interface PeerDateSelectionPayload {
  type: "peer_date_selection";
  user_id: number | null;
  sender: string | null;
  date: string | null; // "YYYY-MM-DD" or null (해제)
}

export interface PeerSelection {
  userId: number | null;
  name: string;
  date: string | null;
}

type WsStatus = "connecting" | "open" | "closed" | "error";

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

function isIntentDetectedPayload(data: unknown): data is IntentDetectedPayload {
  if (!data || typeof data !== "object") {
    return false;
  }

  const candidate = data as Partial<IntentDetectedPayload>;
  return (
    candidate.type === "intent_detected" &&
    typeof candidate.intent === "string" &&
    typeof candidate.confidence === "number" &&
    typeof candidate.method === "string" &&
    typeof candidate.trigger_message_id === "number"
  );
}

function isReminderPayload(data: unknown): data is ReminderPayload {
  if (!data || typeof data !== "object") {
    return false;
  }

  const candidate = data as Partial<ReminderPayload>;
  return (
    candidate.type === "reminder" &&
    typeof candidate.message === "string" &&
    typeof candidate.meeting_id === "number"
  );
}

function isPeerDateSelectionPayload(data: unknown): data is PeerDateSelectionPayload {
  if (!data || typeof data !== "object") {
    return false;
  }

  const candidate = data as Partial<PeerDateSelectionPayload>;
  return (
    candidate.type === "peer_date_selection" &&
    (candidate.date === null || typeof candidate.date === "string")
  );
}

function isVoteReminderPayload(data: unknown): data is VoteReminderPayload {
  if (!data || typeof data !== "object") {
    return false;
  }

  const candidate = data as Partial<VoteReminderPayload>;
  return (
    candidate.type === "vote_reminder" &&
    typeof candidate.message === "string" &&
    typeof candidate.meeting_id === "number"
  );
}

function getReconnectDelay(attempt: number): number {
  return Math.min(1000 * 2 ** attempt, MAX_RECONNECT_DELAY_MS);
}

export function useSocialWebSocket(roomId: string, sender: string) {
  const [messages, setMessages] = useState<ChatMessagePayload[]>([]);
  const [detectedIntent, setDetectedIntent] = useState<IntentDetectedPayload | null>(null);
  const [peerSelections, setPeerSelections] = useState<Record<string, PeerSelection>>({});
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

    let isActive = true;

    setMessages([]);
    setDetectedIntent(null);

    const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    const wsBase = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";
    const roomPk = /^\d+$/.test(roomId) ? roomId : null;

    if (roomPk) {
      fetch(`${apiBase}/api/v1/chat/messages?pane_type=social&room_id=${roomPk}&limit=50`, {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then(async (response) => {
          if (!response.ok) {
            throw new Error(`Failed to load social messages: ${response.status}`);
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

      const socket = new WebSocket(`${wsBase}/ws/social/${roomId}?token=${encodeURIComponent(token)}`);
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

        let data: unknown;
        try {
          data = JSON.parse(event.data as string);
        } catch {
          return;
        }

        if (isIntentDetectedPayload(data)) {
          setDetectedIntent(data);
          return;
        }

        if (isPeerDateSelectionPayload(data)) {
          // 자기 자신 이벤트는 무시 (로컬 clickedDay가 이미 반영됨)
          if (data.sender && data.sender === sender) {
            return;
          }
          const peerKey = data.user_id != null ? `u${data.user_id}` : `n:${data.sender ?? ""}`;
          setPeerSelections((prev) => {
            const next = { ...prev };
            if (data.date === null) {
              delete next[peerKey];
            } else {
              next[peerKey] = {
                userId: data.user_id,
                name: data.sender ?? "익명",
                date: data.date,
              };
            }
            return next;
          });
          return;
        }

        if (isReminderPayload(data) || isVoteReminderPayload(data)) {
          setMessages((prev) => [
            ...prev,
            {
              id: Date.now(),
              pane_type: "social",
              role: "system",
              content: data.message,
              sender: "매듭이",
              created_at: new Date().toISOString(),
            },
          ]);
          return;
        }

        if (!isChatMessagePayload(data)) {
          return;
        }

        setMessages((prev) => {
          if (prev.some((message) => message.id === data.id)) {
            return prev;
          }
          return [...prev, data];
        });
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

  const sendDateSelection = useCallback(
    (date: string | null) => {
      const ws = wsRef.current;
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "date_selection", date, sender }));
      }
    },
    [sender],
  );

  const dismissIntent = useCallback(() => {
    setDetectedIntent(null);
  }, []);

  return {
    messages,
    sendMessage,
    sendDateSelection,
    status,
    detectedIntent,
    dismissIntent,
    peerSelections,
  };
}
