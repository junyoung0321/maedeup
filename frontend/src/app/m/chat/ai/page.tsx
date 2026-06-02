"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, Menu } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { MeetingProvider } from "@/contexts/MeetingContext";
import AiAssistantPane from "@/components/meeting/AiAssistantPane";
import InfoPane from "@/components/meeting/InfoPane";
import type { Room } from "@/types";

// 모바일 통합 meeting 화면 — 웹과 동일한 컴포넌트로 캘린더(InfoPane: TimeBar 시간대 조율)
// + AI(AiAssistantPane: 추천/장소/매듭 카드·공유 토글)를 한 MeetingProvider에 둘 다 마운트.
// 두 pane이 같은 provider+WS 상태를 공유하므로 데스크탑처럼 "AI 카드 → 시간대 변경 →
// 캘린더 탭 TimeBar"가 그대로 동작한다. 탭은 visibility 토글(둘 다 살아있음).
// 채팅방 탭은 별도 라우트(/m/chat/schedule, social 채팅)로 이동.
function MobileMeetingRoom() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const roomId = searchParams.get("roomId") ?? "";
  const initialTab = searchParams.get("tab") === "calendar" ? "calendar" : "ai";
  const { user, loading: authLoading } = useAuth();
  const [room, setRoom] = useState<Room | null>(null);
  const [tab, setTab] = useState<"calendar" | "ai">(initialTab);

  useEffect(() => {
    if (authLoading || !user || !roomId) return;
    apiFetch<Room>(`/api/v1/rooms/${roomId}`)
      .then(setRoom)
      .catch(() => null);
  }, [authLoading, user, roomId]);

  const roomName = room?.name ?? "모임";

  const TabBtn = ({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) => (
    <div
      className="flex-1 flex items-center justify-center cursor-pointer"
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

      {/* Tab Bar — 채팅방(라우트) / 캘린더(local) / AI(local) */}
      <div className="flex shrink-0" style={{ height: 44, borderBottom: "1px solid #e2e8f0" }}>
        <TabBtn label="채팅방" active={false} onClick={() => router.push(`/m/chat/schedule?roomId=${roomId}`)} />
        <TabBtn label="캘린더" active={tab === "calendar"} onClick={() => setTab("calendar")} />
        <TabBtn label="AI" active={tab === "ai"} onClick={() => setTab("ai")} />
      </div>

      {/* 두 pane 모두 마운트(상태·WS 공유), visibility만 토글 — 데스크탑 동시 렌더와 동치 */}
      <div className="flex-1 relative" style={{ minHeight: 0 }}>
        <MeetingProvider initialRoomId={roomId} initialRoomName={roomName}>
          <div
            className="absolute inset-0 flex flex-col"
            style={{ display: tab === "calendar" ? "flex" : "none", overflowY: "auto" }}
          >
            <InfoPane />
          </div>
          <div
            className="absolute inset-0 flex flex-col"
            style={{ display: tab === "ai" ? "flex" : "none" }}
          >
            <AiAssistantPane />
          </div>
        </MeetingProvider>
      </div>
    </div>
  );
}

export default function AiChatPage() {
  return (
    <Suspense fallback={null}>
      <MobileMeetingRoom />
    </Suspense>
  );
}
