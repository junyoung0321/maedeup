"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export interface ChatMessagePayload {
  id: number;
  pane_type: string;
  role: string;
  content: string;
  sender: string | null;
  created_at: string;
}

type WsStatus = "connecting" | "open" | "closed" | "error";

export function useSocialWebSocket(roomId: string) {
  const [messages, setMessages] = useState<ChatMessagePayload[]>([]);
  const [status, setStatus] = useState<WsStatus>("connecting");
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const ws = new WebSocket(`ws://localhost:8000/ws/social/${roomId}`);
    wsRef.current = ws;
    setStatus("connecting");

    ws.onopen = () => setStatus("open");

    ws.onmessage = (event) => {
      const msg: ChatMessagePayload = JSON.parse(event.data as string);
      setMessages((prev) => [...prev, msg]);
    };

    ws.onerror = () => setStatus("error");

    ws.onclose = () => setStatus("closed");

    return () => {
      ws.close();
    };
  }, [roomId]);

  const sendMessage = useCallback(
    (content: string) => {
      const ws = wsRef.current;
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(
          JSON.stringify({ role: "user", content, sender: "테스트유저" })
        );
      }
    },
    []
  );

  return { messages, sendMessage, status };
}
