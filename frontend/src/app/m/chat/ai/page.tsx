"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  EllipsisVertical,
  Sparkles,
  Calendar,
  MapPin,
  Users,
  Send,
} from "lucide-react";
import { useAgentWebSocket } from "@/hooks/useAgentWebSocket";
import { useAuth } from "@/hooks/useAuth";

function relativeTime(iso: string): string {
  const d = new Date(iso);
  const h = d.getHours();
  const m = d.getMinutes();
  const period = h < 12 ? "오전" : "오후";
  const hh = h % 12 || 12;
  return `${period} ${hh}:${String(m).padStart(2, "0")}`;
}

function AiChatPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const roomId = searchParams.get("roomId") ?? "";
  const { user, loading: authLoading } = useAuth();
  const sender = !authLoading && user ? user.name : "익명";

  const { messages, sendMessage, status } = useAgentWebSocket(roomId, sender);

  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function handleSend() {
    const text = input.trim();
    if (!text || status !== "open") return;
    sendMessage(text);
    setInput("");
  }

  return (
    <div
      style={{
        width: "100%",
        height: "844px",
        background: "#ffffff",
        display: "flex",
        flexDirection: "column",
        fontFamily: "Pretendard, sans-serif",
      }}
    >
      {/* Header */}
      <div
        style={{
          height: 56,
          minHeight: 56,
          background: "#ffffff",
          padding: "0 16px",
          display: "flex",
          alignItems: "center",
          borderBottom: "1px solid #e2e8f0",
        }}
      >
        <ArrowLeft size={24} color="#1e293b" style={{ cursor: "pointer" }} onClick={() => router.back()} />
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
          <Sparkles size={20} color="#4f46e5" />
          <span style={{ fontSize: 17, fontWeight: 700, color: "#1e293b" }}>AI 비서</span>
          <span
            style={{
              fontSize: 10,
              fontWeight: 600,
              color: "#4f46e5",
              background: "#eef2ff",
              borderRadius: 10,
              padding: "0 8px",
              height: 20,
              display: "flex",
              alignItems: "center",
            }}
          >
            Beta
          </span>
        </div>
        <EllipsisVertical
          size={24}
          color="#64748b"
          style={{ cursor: "pointer" }}
          onClick={() => alert("AI 비서 설정은 준비 중입니다")}
        />
      </div>

      {/* Message Area */}
      <div
        style={{
          flex: 1,
          background: "#f8fafc",
          padding: 16,
          gap: 16,
          display: "flex",
          flexDirection: "column",
          overflowY: "auto",
        }}
      >
        {/* Welcome Card */}
        <div
          style={{
            borderRadius: 16,
            background: "linear-gradient(135deg, #4f46e5, #7c3aed)",
            padding: 20,
            display: "flex",
            flexDirection: "column",
            gap: 10,
          }}
        >
          <Sparkles size={28} color="#ffffff" />
          <span style={{ fontSize: 18, fontWeight: 700, color: "#ffffff" }}>안녕하세요! AI 비서입니다</span>
          <span style={{ fontSize: 13, color: "rgba(255,255,255,0.8)", lineHeight: 1.5, whiteSpace: "pre-wrap" }}>
            {"모임 일정 조율, 장소 추천, 빠른 매칭 등\n무엇이든 도와드릴게요 😊"}
          </span>
        </div>

        {/* Quick Action Chips */}
        <div style={{ display: "flex", gap: 8 }}>
          {[
            { icon: Calendar, label: "일정 잡기", color: "#4f46e5" },
            { icon: MapPin, label: "장소 추천", color: "#0ea5e9" },
            { icon: Users, label: "모임 매칭", color: "#7c3aed" },
          ].map((btn) => (
            <div
              key={btn.label}
              onClick={() => setInput(btn.label)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "8px 14px",
                borderRadius: 20,
                background: "#ffffff",
                border: "1px solid #e2e8f0",
                cursor: "pointer",
              }}
            >
              <btn.icon size={14} color={btn.color} />
              <span style={{ fontSize: 13, color: btn.color }}>{btn.label}</span>
            </div>
          ))}
        </div>

        {/* Messages */}
        {messages.map((msg) => {
          if (msg.role === "user") {
            return (
              <div key={msg.id} style={{ display: "flex", justifyContent: "flex-end" }}>
                <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
                  <div
                    style={{
                      borderRadius: "16px 0 16px 16px",
                      background: "#4f46e5",
                      padding: 12,
                      maxWidth: 260,
                    }}
                  >
                    <span style={{ fontSize: 14, color: "#ffffff", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                      {msg.content}
                    </span>
                  </div>
                  <span style={{ fontSize: 11, color: "#94a3b8" }}>{relativeTime(msg.created_at)}</span>
                </div>
              </div>
            );
          }

          if (msg.role === "assistant") {
            return (
              <div key={msg.id} style={{ display: "flex", gap: 8 }}>
                <div
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: 16,
                    background: "linear-gradient(135deg, #4f46e5, #7c3aed)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}
                >
                  <Sparkles size={16} color="#ffffff" />
                </div>
                <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 4 }}>
                  <span style={{ fontSize: 12, color: "#94a3b8" }}>AI 비서</span>
                  <div
                    style={{
                      borderRadius: "0 16px 16px 16px",
                      background: "#ffffff",
                      border: "0.5px solid #e2e8f0",
                      padding: 12,
                      maxWidth: 260,
                    }}
                  >
                    <span style={{ fontSize: 14, color: "#1e293b", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                      {msg.content}
                    </span>
                  </div>
                  <span style={{ fontSize: 11, color: "#94a3b8" }}>{relativeTime(msg.created_at)}</span>
                </div>
              </div>
            );
          }

          return (
            <div key={msg.id} style={{ display: "flex", justifyContent: "center" }}>
              <span
                style={{
                  fontSize: 11,
                  color: "#94a3b8",
                  background: "#f1f5f9",
                  borderRadius: 8,
                  padding: "4px 10px",
                }}
              >
                {msg.content}
              </span>
            </div>
          );
        })}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Bar */}
      <div
        style={{
          height: 60,
          background: "#ffffff",
          padding: "0 12px",
          display: "flex",
          alignItems: "center",
          gap: 8,
          borderTop: "1px solid #e2e8f0",
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          placeholder="AI 비서에게 물어보세요..."
          style={{
            flex: 1,
            height: 40,
            borderRadius: 20,
            background: "#ffffff",
            border: "1px solid #e2e8f0",
            padding: "0 16px",
            fontSize: 14,
            color: "#1e293b",
            outline: "none",
          }}
        />
        <div
          onClick={handleSend}
          style={{
            width: 40,
            height: 40,
            borderRadius: 20,
            background: status === "open" ? "#4f46e5" : "#c7d2fe",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: status === "open" ? "pointer" : "not-allowed",
            flexShrink: 0,
          }}
        >
          <Send size={18} color="#ffffff" />
        </div>
      </div>

      {/* Home Indicator */}
      <div
        style={{
          height: 20,
          background: "#ffffff",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <div style={{ width: 134, height: 5, borderRadius: 3, background: "#000000" }} />
      </div>
    </div>
  );
}

export default function AiChatPage() {
  return (
    <Suspense fallback={null}>
      <AiChatPageContent />
    </Suspense>
  );
}
