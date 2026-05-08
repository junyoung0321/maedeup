"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  Menu,
  Sparkles,
  ChevronRight,
  Send,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { useSocialWebSocket } from "@/hooks/useSocialWebSocket";
import type { Room } from "@/types";

const AVATAR_COLORS = ["#818cf8", "#f472b6", "#34d399", "#fb923c", "#60a5fa", "#a78bfa"];

function avatarColor(name: string) {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) & 0xffff;
  return AVATAR_COLORS[h % AVATAR_COLORS.length];
}

function ScheduleChatPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const roomId = searchParams.get("roomId") ?? "";
  const { user, loading: authLoading } = useAuth();
  const [room, setRoom] = useState<Room | null>(null);
  const [inputText, setInputText] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  const { messages, sendMessage, finalizationPending, finalizationProposal, status } =
    useSocialWebSocket(roomId, user?.name ?? "익명");

  useEffect(() => {
    if (authLoading || !user || !roomId) return;
    apiFetch<Room>(`/api/v1/rooms/${roomId}`)
      .then(setRoom)
      .catch(() => null);
  }, [authLoading, user, roomId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function handleSend() {
    const text = inputText.trim();
    if (!text) return;
    sendMessage(text);
    setInputText("");
  }

  const roomName = room?.name ?? "모임";
  const hasBanner = finalizationPending || !!finalizationProposal;

  return (
    <div
      className="relative mx-auto flex flex-col bg-white overflow-hidden"
      style={{ width: 390, height: 844 }}
    >
      {/* 1. Header */}
      <div
        className="flex items-center shrink-0"
        style={{ height: 56, padding: "0 16px", borderBottom: "1px solid #e2e8f0" }}
      >
        <ArrowLeft size={24} color="#1e293b" className="shrink-0 cursor-pointer" onClick={() => router.push("/m/chat")} />
        <div className="flex-1 flex flex-col items-center gap-[2px]">
          <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 17, fontWeight: 600, color: "#1e293b" }}>
            {roomName}
          </span>
          <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 12, fontWeight: 400, color: "#94a3b8" }}>
            {room?.category ?? "모임"}
          </span>
        </div>
        <Menu
          size={24}
          color="#64748b"
          className="shrink-0 cursor-pointer"
          onClick={() => router.push(`/m/meeting/detail?roomId=${roomId}`)}
        />
      </div>

      {/* 2. Tab Bar */}
      <div className="flex shrink-0" style={{ height: 44, borderBottom: "1px solid #e2e8f0" }}>
        <div
          className="flex-1 flex items-center justify-center"
          style={{ fontFamily: "Pretendard, sans-serif", fontSize: 14, fontWeight: 600, color: "#4f46e5", borderBottom: "2px solid #4f46e5" }}
        >
          채팅방
        </div>
        <div
          className="flex-1 flex items-center justify-center cursor-pointer"
          onClick={() => router.push(`/m/schedule?roomId=${roomId}`)}
          style={{ fontFamily: "Pretendard, sans-serif", fontSize: 14, fontWeight: 500, color: "#94a3b8" }}
        >
          캘린더
        </div>
      </div>

      {/* 3. AI Banner */}
      {hasBanner && (
        <div
          className="flex items-center justify-center shrink-0 cursor-pointer"
          style={{ height: 40, background: "#eef2ff", borderBottom: "1px solid #e0e7ff", gap: 6 }}
          onClick={() => router.push(`/m/schedule?roomId=${roomId}`)}
        >
          <Sparkles size={14} color="#4f46e5" />
          <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 12, fontWeight: 600, color: "#4f46e5" }}>
            {finalizationProposal ? "AI가 일정을 제안했습니다 — 캘린더에서 투표하세요" : "AI가 일정 조율을 시작했습니다"}
          </span>
          <ChevronRight size={14} color="#4f46e5" />
        </div>
      )}

      {/* 4. Message Area */}
      <div
        className="flex-1 flex flex-col overflow-y-auto"
        style={{ background: "#f8fafc", padding: "12px 16px", gap: 12 }}
      >
        {status === "connecting" && messages.length === 0 && (
          <div style={{ textAlign: "center", paddingTop: 40 }}>
            <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 13, color: "#94a3b8" }}>연결 중...</span>
          </div>
        )}

        {messages.map((msg) => {
          if (msg.role === "system") {
            return (
              <div key={msg.id} style={{ textAlign: "center" }}>
                <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 11, color: "#94a3b8", lineHeight: 1.5 }}>
                  {msg.content}
                </span>
              </div>
            );
          }

          const isMe = msg.user_id != null && msg.user_id === user?.id;
          const senderName = msg.sender ?? "?";
          const initial = senderName.charAt(0).toUpperCase();

          if (isMe) {
            return (
              <div key={msg.id} className="flex justify-end">
                <div style={{ borderRadius: "16px 16px 6px 16px", background: "#4f46e5", padding: "10px 14px", maxWidth: 240 }}>
                  <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 13, fontWeight: 400, color: "#ffffff" }}>
                    {msg.content}
                  </span>
                </div>
              </div>
            );
          }

          return (
            <div key={msg.id} className="flex items-end" style={{ gap: 8 }}>
              <div
                className="shrink-0 flex items-center justify-center"
                style={{ width: 32, height: 32, borderRadius: 16, background: avatarColor(senderName) }}
              >
                <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 12, fontWeight: 500, color: "#ffffff" }}>
                  {initial}
                </span>
              </div>
              <div className="flex flex-col" style={{ gap: 4, maxWidth: 240 }}>
                <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 11, fontWeight: 400, color: "#94a3b8" }}>
                  {senderName}
                </span>
                <div style={{ borderRadius: "16px 16px 16px 6px", background: "#ffffff", border: "1px solid #e2e8f0", padding: "10px 14px" }}>
                  <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 13, fontWeight: 400, color: "#1e293b" }}>
                    {msg.content}
                  </span>
                </div>
              </div>
            </div>
          );
        })}

        {/* AI proposal card */}
        {finalizationProposal && (
          <div
            style={{
              borderRadius: 16,
              background: "linear-gradient(-225deg, #4f46e5 0%, #7c3aed 50%, #a855f7 100%)",
              padding: "16px 18px",
              display: "flex",
              flexDirection: "column",
              gap: 10,
              boxShadow: "0 4px 14px #4f46e520",
            }}
          >
            <div className="flex items-center" style={{ gap: 6 }}>
              <Sparkles size={16} color="#ffffff" />
              <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 11, fontWeight: 600, color: "#ffffff" }}>AI 어시스턴트</span>
            </div>
            <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 16, fontWeight: 700, color: "#ffffff" }}>
              일정이 제안되었습니다
            </span>
            {finalizationProposal.reason && (
              <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 12, fontWeight: 400, color: "#ffffffcc", lineHeight: 1.5 }}>
                {finalizationProposal.reason}
              </span>
            )}
            <div style={{ height: 1, background: "#ffffff30" }} />
            <div
              className="flex items-center justify-center cursor-pointer"
              style={{ gap: 6, padding: "8px 0", borderRadius: 8, background: "rgba(255,255,255,0.15)" }}
              onClick={() => router.push(`/m/schedule?roomId=${roomId}`)}
            >
              <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 11, fontWeight: 600, color: "#ffffff" }}>
                캘린더 탭에서 투표하기 →
              </span>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* 5. Input Bar */}
      <div
        className="flex items-center shrink-0"
        style={{ height: 60, background: "#ffffff", borderTop: "1px solid #e2e8f0", padding: "0 12px", gap: 8 }}
      >
        <input
          className="flex-1"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
          placeholder="메세지를 입력하세요"
          style={{
            height: 40,
            borderRadius: 20,
            background: "#ffffff",
            border: "1px solid #e2e8f0",
            padding: "0 16px",
            boxShadow: "0 2px 4px #0000001a",
            fontFamily: "Pretendard, sans-serif",
            fontSize: 14,
            color: "#1e293b",
            outline: "none",
          }}
        />
        <button
          onClick={handleSend}
          disabled={!inputText.trim()}
          className="flex items-center justify-center shrink-0 cursor-pointer"
          style={{
            width: 40,
            height: 40,
            borderRadius: 20,
            background: inputText.trim() ? "#4f46e5" : "#c7d2fe",
            border: "none",
            transition: "background 0.15s",
          }}
        >
          <Send size={16} color="#ffffff" />
        </button>
      </div>

      {/* 6. Home Indicator */}
      <div className="flex items-center justify-center shrink-0" style={{ height: 20, background: "#ffffff" }}>
        <div style={{ width: 134, height: 5, borderRadius: 3, background: "#000000" }} />
      </div>
    </div>
  );
}

export default function ScheduleChatPage() {
  return (
    <Suspense fallback={null}>
      <ScheduleChatPageContent />
    </Suspense>
  );
}
