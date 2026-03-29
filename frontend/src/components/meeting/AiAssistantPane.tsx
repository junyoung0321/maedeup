"use client";

import { useState } from "react";
import { Sparkles, Send, MessageCircle } from "lucide-react";
import { useAgentWebSocket } from "@/hooks/useAgentWebSocket";
import { useAuth } from "@/hooks/useAuth";

export default function AiAssistantPane() {
  const [input, setInput] = useState("");
  const { user } = useAuth();
  const { messages, sendMessage, status } = useAgentWebSocket("room-1", user?.name ?? "나");

  const isAiLoading =
    status === "connecting" ||
    (messages.length > 0 && messages[messages.length - 1].role === "user");

  const handleSend = () => {
    if (!input.trim()) return;
    sendMessage(input.trim());
    setInput("");
  };

  return (
    <div
      style={{
        width: 414,
        height: 733,
        borderRadius: 20,
        border: "1px solid #e2e8f0",
        boxShadow: "0 4px 3.5px rgba(0,0,0,0.25)",
        background: "#fff",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        fontFamily: "Pretendard Variable, Pretendard, sans-serif",
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "16px 20px",
          background: "linear-gradient(135deg, #837cff, #6eb3ff)",
          borderBottom: "1px solid #e2e8f0",
        }}
      >
        <Sparkles style={{ width: 20, height: 20, color: "#ffffff" }} />
        <span
          style={{
            fontSize: 26,
            fontWeight: 400,
            color: "#ffffff",
            letterSpacing: 0.75,
          }}
        >
          AI 어시스턴트
        </span>
      </div>

      {/* Content */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "14px 20px",
          display: "flex",
          flexDirection: "column",
          gap: 14,
        }}
      >
        {/* Detect banner */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "8px 14px",
            background: "#eef2ff",
            borderRadius: 18,
          }}
        >
          <MessageCircle style={{ width: 16, height: 16, color: "#4f46e5" }} />
          <span style={{ fontSize: 15, fontWeight: 400, color: "#4f46e5", fontFamily: "Inter, sans-serif" }}>
            채팅방에서 회식 일정 대화가 감지되었습니다
          </span>
        </div>

        {/* Messages */}
        {messages.map((msg, i) => {
          const isMe = msg.role === "user";
          const senderLabel = isMe
            ? (msg.sender ?? user?.name ?? "나")
            : (msg.sender ?? "AI 어시스턴트");
          return (
            <div
              key={msg.id ?? i}
              style={{
                display: "flex",
                flexDirection: isMe ? "row-reverse" : "row",
                gap: 8,
                alignItems: "flex-end",
              }}
            >
              {!isMe && (
                <div
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: "50%",
                    background: "#818cf8",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "#fff",
                    fontSize: 12,
                    fontWeight: 300,
                    flexShrink: 0,
                  }}
                >
                  {senderLabel.charAt(0)}
                </div>
              )}
              <div
                style={{
                  maxWidth: "75%",
                  display: "flex",
                  flexDirection: "column",
                  alignItems: isMe ? "flex-end" : "flex-start",
                }}
              >
                {!isMe && (
                  <span style={{ fontSize: 11, color: "#94a3b8", marginBottom: 4 }}>
                    {senderLabel}
                  </span>
                )}
                <div
                  style={{
                    padding: "10px 16px",
                    borderRadius: 16,
                    ...(isMe
                      ? {
                          borderBottomRightRadius: 6,
                          background: "#4f46e5",
                          color: "#ffffff",
                        }
                      : {
                          borderBottomLeftRadius: 6,
                          background: "#f1f5f9",
                          color: "#000000",
                        }),
                    fontSize: 17,
                    fontWeight: 300,
                    lineHeight: 1.5,
                    whiteSpace: "pre-wrap" as const,
                  }}
                >
                  {msg.content}
                </div>
              </div>
            </div>
          );
        })}

        {/* AI Card — 메시지 없을 때 또는 AI 응답 대기 중 */}
        {(messages.length === 0 || isAiLoading) && (
          <div
            style={{
              background: "linear-gradient(135deg, #4f46e5 0%, #7c3aed 50%, #a855f7 100%)",
              borderRadius: 16,
              padding: 20,
              display: "flex",
              flexDirection: "column",
              gap: 12,
              marginTop: 4,
              boxShadow: "0 4px 14px rgba(79, 70, 229, 0.13)",
            }}
          >
            {/* AI icon + label row */}
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Sparkles style={{ width: 20, height: 20, color: "#ffffff" }} />
              <span style={{ fontSize: 12, fontWeight: 600, color: "#ffffff", fontFamily: "Inter, sans-serif" }}>
                AI 어시스턴트
              </span>
            </div>
            <span style={{ fontSize: 18, fontWeight: 600, color: "#ffffff", fontFamily: "Pretendard Variable, Pretendard, sans-serif" }}>
              {isAiLoading ? "분석 중..." : "일정 조율을 시작하겠습니다"}
            </span>
            <span
              style={{
                fontSize: 13,
                fontWeight: 300,
                color: "#ffffff",
                lineHeight: 1.5,
                whiteSpace: "pre-wrap",
                fontFamily: "Pretendard Variable, Pretendard, sans-serif",
              }}
            >
              {isAiLoading
                ? "채팅 내용을 분석하여 모임원들의\n가능한 시간대를 정리하고 있어요."
                : "메시지를 보내 일정 조율을 시작해보세요."}
            </span>
            {/* Divider */}
            <div style={{ width: "100%", height: 1, background: "rgba(255,255,255,0.19)" }} />
            {/* Status row */}
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: isAiLoading ? "#fbbf24" : "#34d399",
                  flexShrink: 0,
                }}
              />
              <span style={{ fontSize: 12, fontWeight: 300, color: "#ffffff", fontFamily: "Pretendard Variable, Pretendard, sans-serif" }}>
                {status === "connecting"
                  ? "연결 중..."
                  : isAiLoading
                  ? "AI가 응답 중..."
                  : "연결됨 · 메시지를 기다리는 중"}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: 12,
          background: "linear-gradient(135deg, #837cff, #6eb3ff)",
          borderTop: "1px solid #e2e8f0",
        }}
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
          placeholder="AI에게 질문하세요"
          style={{
            flex: 1,
            padding: "10px 16px",
            background: "#ffffff",
            borderRadius: 60,
            border: "1.5px solid #a2f4fd",
            outline: "none",
            fontSize: 15,
            color: "#1e293b",
            fontFamily: "Pretendard Variable, Pretendard, sans-serif",
            boxShadow: "0 2px 3.5px rgba(0,0,0,0.15)",
          }}
        />
        <button
          onClick={handleSend}
          style={{
            width: 40,
            height: 40,
            borderRadius: "50%",
            background: "#ffffff",
            border: "none",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
            flexShrink: 0,
            boxShadow: "0 2px 3.5px rgba(0,0,0,0.15)",
          }}
        >
          <Send style={{ width: 16, height: 16, color: "#837cff" }} />
        </button>
      </div>
    </div>
  );
}
