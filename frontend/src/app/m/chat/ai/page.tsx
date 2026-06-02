"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, Menu } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { MeetingProvider } from "@/contexts/MeetingContext";
import AiAssistantPane from "@/components/meeting/AiAssistantPane";
import type { Room } from "@/types";

// 모바일 AI 탭 — 웹과 동일한 AI 패널을 그대로 렌더한다.
// 데스크탑 AiAssistantPane(추천/장소/매듭 카드 + TimeBar + 공유 토글)을 MeetingProvider로
// 감싸 roomId만 주입하면 데스크탑과 완전히 동일한 기능·디자인·출력을 모바일에서 제공.
function MobileAiTab() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const roomId = searchParams.get("roomId") ?? "";
  const { user, loading: authLoading } = useAuth();
  const [room, setRoom] = useState<Room | null>(null);

  useEffect(() => {
    if (authLoading || !user || !roomId) return;
    apiFetch<Room>(`/api/v1/rooms/${roomId}`)
      .then(setRoom)
      .catch(() => null);
  }, [authLoading, user, roomId]);

  const roomName = room?.name ?? "모임";

  const tab = (label: string, active: boolean, onClick?: () => void) => (
    <div
      className={`flex-1 flex items-center justify-center ${active ? "" : "cursor-pointer"}`}
      onClick={onClick}
      style={{
        fontFamily: "Pretendard, sans-serif",
        fontSize: 14,
        fontWeight: active ? 600 : 500,
        color: active ? "#4f46e5" : "#94a3b8",
        borderBottom: active ? "2px solid #4f46e5" : "none",
      }}
    >
      {label}
    </div>
  );

  return (
    <div
      className="relative flex flex-col bg-white overflow-hidden"
      style={{ width: "100%", height: "100dvh" }}
    >
      {/* Header */}
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

      {/* Tab Bar — 채팅방 / 캘린더 / AI */}
      <div className="flex shrink-0" style={{ height: 44, borderBottom: "1px solid #e2e8f0" }}>
        {tab("채팅방", false, () => router.push(`/m/chat/schedule?roomId=${roomId}`))}
        {tab("캘린더", false, () => router.push(`/m/schedule?roomId=${roomId}`))}
        {tab("AI", true)}
      </div>

      {/* AI 패널 (데스크탑 컴포넌트 그대로) */}
      <div className="flex-1 flex flex-col" style={{ minHeight: 0 }}>
        <MeetingProvider initialRoomId={roomId} initialRoomName={roomName}>
          <AiAssistantPane />
        </MeetingProvider>
      </div>
    </div>
  );
}

export default function AiChatPage() {
  return (
    <Suspense fallback={null}>
      <MobileAiTab />
    </Suspense>
  );
}
