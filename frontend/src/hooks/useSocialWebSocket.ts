"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ChatMessagePayload } from "@/types";

export type { ChatMessagePayload };

type WsStatus = "connecting" | "open" | "closed" | "error";

export function useSocialWebSocket(roomId: string, sender: string) {
  const [messages, setMessages] = useState<ChatMessagePayload[]>([]);
  const [status, setStatus] = useState<WsStatus>("connecting");
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("auth_token");
    if (!token) {
      window.location.href = "/";
      return;
    }

    const wsBase = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";
    const ws = new WebSocket(
      `${wsBase}/ws/social/${roomId}?token=${encodeURIComponent(token)}`
    );
    wsRef.current = ws;
    setStatus("connecting");

    ws.onopen = () => setStatus("open");

    ws.onmessage = (event) => {
      const msg: ChatMessagePayload = JSON.parse(event.data as string);
      setMessages((prev) => [...prev, msg]);
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

  return { messages, sendMessage, status };
}
