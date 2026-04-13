"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ChatMessagePayload } from "@/types";

export type { ChatMessagePayload };

export interface IntentDetectedPayload {
  type: "intent_detected";
  intent: "meeting_schedule" | "place_suggestion" | "general";
  confidence: number;
  method: "rag" | "gemini" | "default";
  trigger_message_id: number;
}

export interface ReminderPayload {
  type: "reminder";
  message: string;
  meeting_id: number;
}

type WsStatus = "connecting" | "open" | "closed" | "error";

export function useSocialWebSocket(roomId: string, sender: string) {
  const [messages, setMessages] = useState<ChatMessagePayload[]>([]);
  const [detectedIntent, setDetectedIntent] =
    useState<IntentDetectedPayload | null>(null);
  const [status, setStatus] = useState<WsStatus>("connecting");
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("auth_token");
    if (!token) {
      window.location.href = "/";
      return;
    }

    // 이전 메시지 로드
    const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    const roomPk = /^\d+$/.test(roomId) ? roomId : null;
    if (roomPk) {
      fetch(
        `${apiBase}/api/v1/chat/messages?pane_type=social&room_id=${roomPk}&limit=50`,
        { headers: { Authorization: `Bearer ${token}` } }
      )
        .then((r) => r.json())
        .then((data) => {
          if (Array.isArray(data)) setMessages(data as ChatMessagePayload[]);
        })
        .catch(() => {/* ignore */});
    }

    const wsBase = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";
    const ws = new WebSocket(
      `${wsBase}/ws/social/${roomId}?token=${encodeURIComponent(token)}`
    );
    wsRef.current = ws;
    setStatus("connecting");

    ws.onopen = () => setStatus("open");

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data as string);

      // intent_detected 이벤트와 일반 채팅 메시지 구분
      if (data.type === "intent_detected") {
        setDetectedIntent(data as IntentDetectedPayload);
      } else if (data.type === "reminder") {
        const reminder = data as ReminderPayload;
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now(),
            pane_type: "social",
            role: "system",
            content: reminder.message,
            sender: "매듭이",
            created_at: new Date().toISOString(),
          },
        ]);
      } else {
        const msg = data as ChatMessagePayload;
        setMessages((prev) => {
          // 중복 방지 (REST 로드 후 WS에서 같은 메시지가 올 경우)
          if (msg.id && prev.some((m) => m.id === msg.id)) return prev;
          return [...prev, msg];
        });
      }
    };

    ws.onerror = () => setStatus("error");

    ws.onclose = (event) => {
      setStatus("closed");
      // 1008: Policy Violation - 토큰 없음 또는 만료
      if (event.code === 1008) {
        localStorage.removeItem("auth_token");
        window.location.href = "/";
      }
    };

    return () => {
      ws.close();
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

  const dismissIntent = useCallback(() => {
    setDetectedIntent(null);
  }, []);

  return { messages, sendMessage, status, detectedIntent, dismissIntent };
}
