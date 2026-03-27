"use client";

import { useEffect, useRef, useState } from "react";
import { useAgentWebSocket } from "../hooks/useAgentWebSocket";

export default function AgentPane({ sender }: { sender: string }) {
  const { messages, sendMessage, status, isAiLoading } = useAgentWebSocket(
    "room-1",
    sender
  );
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isAiLoading]);

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
      <style>{`
        @keyframes blink {
          0%, 80%, 100% { opacity: 0.2; transform: scale(0.8); }
          40% { opacity: 1; transform: scale(1); }
        }
        .dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: #a78bfa; margin: 0 2px; animation: blink 1.2s infinite; }
        .dot:nth-child(2) { animation-delay: 0.2s; }
        .dot:nth-child(3) { animation-delay: 0.4s; }
      `}</style>

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
        {messages.length === 0 && !isAiLoading && (
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

        {messages.map((msg) => {
          const isUser = msg.role === "user";
          return (
            <div
              key={msg.id}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: isUser ? "flex-end" : "flex-start",
              }}
            >
              {/* 발신자 레이블 */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                  marginBottom: 3,
                }}
              >
                {!isUser && (
                  <span style={{ fontSize: "14px" }}>🤖</span>
                )}
                <span style={{ fontSize: "11px", color: "#555" }}>
                  {isUser ? msg.sender ?? "나" : "AI 어시스턴트"}
                </span>
              </div>

              {/* 말풍선 */}
              <div
                style={{
                  background: isUser
                    ? "#2563eb"
                    : "linear-gradient(135deg, #5b21b6 0%, #7c3aed 50%, #a855f7 100%)",
                  color: "#f3f4f6",
                  borderRadius: isUser
                    ? "16px 16px 4px 16px"
                    : "16px 16px 16px 4px",
                  padding: "9px 13px",
                  fontSize: "13px",
                  maxWidth: "80%",
                  wordBreak: "break-word",
                  lineHeight: 1.55,
                  boxShadow: isUser
                    ? "0 1px 4px rgba(37,99,235,0.3)"
                    : "0 1px 4px rgba(124,58,237,0.35)",
                }}
              >
                {msg.content}
              </div>
            </div>
          );
        })}

        {/* AI 로딩 말풍선 */}
        {isAiLoading && (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "flex-start",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 4,
                marginBottom: 3,
              }}
            >
              <span style={{ fontSize: "14px" }}>🤖</span>
              <span style={{ fontSize: "11px", color: "#555" }}>
                AI 어시스턴트
              </span>
            </div>
            <div
              style={{
                background:
                  "linear-gradient(135deg, #5b21b6 0%, #7c3aed 50%, #a855f7 100%)",
                borderRadius: "16px 16px 16px 4px",
                padding: "10px 16px",
                display: "flex",
                alignItems: "center",
                gap: 2,
                boxShadow: "0 1px 4px rgba(124,58,237,0.35)",
              }}
            >
              <span className="dot" />
              <span className="dot" />
              <span className="dot" />
            </div>
          </div>
        )}

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
          disabled={isAiLoading}
          style={{
            flex: 1,
            background: "#161616",
            border: "1px solid #2a2a2a",
            borderRadius: 8,
            padding: "8px 12px",
            color: isAiLoading ? "#555" : "#e5e7eb",
            fontSize: "13px",
            outline: "none",
            cursor: isAiLoading ? "not-allowed" : "text",
          }}
        />
        <button
          onClick={handleSend}
          disabled={isAiLoading}
          style={{
            background: isAiLoading ? "#3b1f6e" : "#7c3aed",
            border: "none",
            borderRadius: 8,
            padding: "8px 16px",
            color: isAiLoading ? "#888" : "#fff",
            fontSize: "13px",
            cursor: isAiLoading ? "not-allowed" : "pointer",
            transition: "background 0.2s",
          }}
        >
          전송
        </button>
      </div>
    </section>
  );
}
