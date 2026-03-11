"use client";

import { useEffect, useRef, useState } from "react";
import { useAgentWebSocket } from "../hooks/useAgentWebSocket";

export default function AgentPane() {
  const { messages, sendMessage, status } = useAgentWebSocket("room-1");
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed) return;
    sendMessage(trimmed);
    setInput("");
  };

  return (
    <section
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        borderRight: "1px solid #222",
        minWidth: 0,
      }}
    >
      <header
        style={{
          padding: "12px 16px",
          borderBottom: "1px solid #222",
          fontWeight: 600,
          fontSize: "13px",
          letterSpacing: "0.05em",
          color: "#aaa",
          textTransform: "uppercase",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        Agent
        <span
          style={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            background: status === "open" ? "#22c55e" : "#444",
            display: "inline-block",
          }}
        />
      </header>

      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "16px",
          display: "flex",
          flexDirection: "column",
          gap: "8px",
        }}
      >
        {messages.length === 0 && (
          <div
            style={{
              flex: 1,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#444",
              fontSize: "13px",
            }}
          >
            AI 에이전트 채팅 영역
          </div>
        )}
        {messages.map((msg) => (
          <div
            key={msg.id}
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: msg.role === "user" ? "flex-end" : "flex-start",
            }}
          >
            {msg.sender && (
              <span
                style={{ fontSize: "11px", color: "#555", marginBottom: 2 }}
              >
                {msg.sender}
              </span>
            )}
            <div
              style={{
                background: msg.role === "user" ? "#7c3aed" : "#1a1a1a",
                color: "#e5e7eb",
                borderRadius: 8,
                padding: "8px 12px",
                fontSize: "13px",
                maxWidth: "80%",
                wordBreak: "break-word",
              }}
            >
              {msg.content}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <div
        style={{
          padding: "12px 16px",
          borderTop: "1px solid #222",
          display: "flex",
          gap: "8px",
        }}
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          placeholder="메시지를 입력하세요..."
          style={{
            flex: 1,
            background: "#161616",
            border: "1px solid #2a2a2a",
            borderRadius: 8,
            padding: "8px 12px",
            color: "#e5e7eb",
            fontSize: "13px",
            outline: "none",
          }}
        />
        <button
          onClick={handleSend}
          style={{
            background: "#7c3aed",
            border: "none",
            borderRadius: 8,
            padding: "8px 16px",
            color: "#fff",
            fontSize: "13px",
            cursor: "pointer",
          }}
        >
          전송
        </button>
      </div>
    </section>
  );
}
