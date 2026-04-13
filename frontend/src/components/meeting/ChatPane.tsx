"use client";

import { useContext, useEffect, useRef, useState } from "react";
import { User, Send, X, Calendar, MapPin } from "lucide-react";
import { useSocialWebSocket } from "@/hooks/useSocialWebSocket";
import { MeetingContext } from "@/contexts/MeetingContext";

function getNameFromToken(): string {
  try {
    const token = localStorage.getItem("auth_token");
    if (!token) return "익명";
    const payload = token.split(".")[1];
    if (!payload) return "익명";
    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
    const decoded = JSON.parse(atob(padded));
    return decoded.name ?? "익명";
  } catch {
    return "익명";
  }
}

const INTENT_BANNER: Record<
  string,
  { icon: React.ReactNode; message: string; color: string }
> = {
  meeting_schedule: {
    icon: <Calendar style={{ width: 14, height: 14 }} />,
    message: "채팅방에서 모임 일정 대화가 감지되었습니다",
    color: "#4f46e5",
  },
  place_suggestion: {
    icon: <MapPin style={{ width: 14, height: 14 }} />,
    message: "채팅방에서 장소 관련 대화가 감지되었습니다",
    color: "#0891b2",
  },
};

export default function ChatPane() {
  const [input, setInput] = useState("");
  const [currentUserName, setCurrentUserName] = useState<string>("익명");
  const scrollRef = useRef<HTMLDivElement>(null);
  const meetingContext = useContext(MeetingContext);

  useEffect(() => {
    setCurrentUserName(getNameFromToken());
  }, []);

  const roomId = meetingContext?.roomId || "room-1";
  const setAiTriggerIntent = meetingContext?.setAiTriggerIntent;

  const { messages, sendMessage, detectedIntent, dismissIntent } =
    useSocialWebSocket(roomId, currentUserName);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const handleSend = () => {
    if (!input.trim()) return;
    sendMessage(input.trim());
    setInput("");
  };

  const banner =
    detectedIntent && INTENT_BANNER[detectedIntent.intent]
      ? INTENT_BANNER[detectedIntent.intent]
      : null;

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

      {/* 의도 감지 배너 */}
      {banner && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "8px 16px",
            background: banner.color,
            color: "#fff",
            fontSize: 13,
            fontWeight: 400,
            gap: 8,
          }}
        >
          <button
            onClick={() => {
              if (detectedIntent && setAiTriggerIntent) {
                setAiTriggerIntent(detectedIntent.intent);
              }
              dismissIntent();
            }}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              flex: 1,
              background: "none",
              border: "none",
              color: "#fff",
              cursor: "pointer",
              padding: 0,
              textAlign: "left",
            }}
          >
            {banner.icon}
            <span>{banner.message}</span>
            <span style={{ marginLeft: 4, fontWeight: 600, textDecoration: "underline" }}>
              AI로 일정 잡기 →
            </span>
          </button>
          <button
            onClick={dismissIntent}
            style={{
              background: "none",
              border: "none",
              color: "#fff",
              cursor: "pointer",
              padding: 0,
              display: "flex",
              alignItems: "center",
            }}
          >
            <X style={{ width: 14, height: 14 }} />
          </button>
        </div>
      )}

      {/* Messages */}
      <div
        ref={scrollRef}
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
