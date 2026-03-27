"use client";

import { useState, useEffect } from "react";
import { User, Send } from "lucide-react";
import { useSocialWebSocket } from "@/hooks/useSocialWebSocket";

function getNameFromToken(): string {
  try {
    const token = localStorage.getItem("auth_token");
    if (!token) return "익명";
    const payload = JSON.parse(atob(token.split(".")[1]));
    return payload.name ?? "익명";
  } catch {
    return "익명";
  }
}

export default function ChatPane() {
  const [input, setInput] = useState("");
  const [currentUserName, setCurrentUserName] = useState<string>("익명");

  useEffect(() => {
    setCurrentUserName(getNameFromToken());
  }, []);

  const { messages, sendMessage } = useSocialWebSocket("room-1", currentUserName);

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
          justifyContent: "space-between",
          padding: "16px 20px",
          background: "#f2f4f7",
          borderBottom: "1px solid #e2e8f0",
        }}
      >
        <span
          style={{
            fontSize: 26,
            fontWeight: 400,
            color: "#000000",
            letterSpacing: 0.75,
          }}
        >
          채팅방
        </span>
        <User style={{ width: 20, height: 20, color: "#94a3b8" }} />
      </div>

      {/* Messages */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "12px 16px",
          display: "flex",
          flexDirection: "column",
          gap: 12,
        }}
      >
        {messages.map((msg) => {
          const isMe = msg.sender === currentUserName;
          return (
            <div
              key={msg.id}
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
                  {(msg.sender ?? "?").charAt(0)}
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
                    {msg.sender}
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
      </div>

      {/* Input */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: 12,
          background: "#fcfdfe",
          borderTop: "1px solid #e2e8f0",
        }}
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
          placeholder="메세지를 입력하세요"
          style={{
            flex: 1,
            padding: "10px 16px",
            background: "#ffffff",
            borderRadius: 60,
            border: "1px solid #e2e8f0",
            boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
            outline: "none",
            fontSize: 15,
            color: "#1e293b",
            fontFamily: "Pretendard Variable, Pretendard, sans-serif",
          }}
        />
        <button
          onClick={handleSend}
          style={{
            width: 40,
            height: 40,
            borderRadius: "50%",
            background: "#4f46e5",
            border: "none",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
            flexShrink: 0,
          }}
        >
          <Send style={{ width: 16, height: 16, color: "#fff" }} />
        </button>
      </div>
    </div>
  );
}
