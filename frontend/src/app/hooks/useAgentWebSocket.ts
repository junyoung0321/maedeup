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

export function useAgentWebSocket(roomId: string, sender: string) {
  const [messages, setMessages] = useState<ChatMessagePayload[]>([]);
  const [status, setStatus] = useState<WsStatus>("connecting");
  const [isAiLoading, setIsAiLoading] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("auth_token");
    if (!token) {
      window.location.href = "/";
      return;
    }

    const ws = new WebSocket(
      `ws://localhost:8000/ws/agent/${roomId}?token=${encodeURIComponent(token)}`
    );
    wsRef.current = ws;
    setStatus("connecting");

    ws.onopen = () => setStatus("open");

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data as string) as
        | ChatMessagePayload
        | { type: string; room_id: string };

      // 로딩 신호
      if ("type" in data && data.type === "loading") {
        setIsAiLoading(true);
        return;
      }

      const msg = data as ChatMessagePayload;
      if (msg.role === "assistant") {
        setIsAiLoading(false);
      }
      setMessages((prev) => [...prev, msg]);
    };

    ws.onerror = () => setStatus("error");

    ws.onclose = (event) => {
      setStatus("closed");
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

  return { messages, sendMessage, status, isAiLoading };
}
