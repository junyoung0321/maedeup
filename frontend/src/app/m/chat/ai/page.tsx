"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, Menu } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { MeetingProvider, useMeeting } from "@/contexts/MeetingContext";
import ChatPane from "@/components/meeting/ChatPane";
import InfoPane from "@/components/meeting/InfoPane";
import AiAssistantPane from "@/components/meeting/AiAssistantPane";
import CompletionPage from "@/components/meeting/CompletionPage";
import type { Room } from "@/types";

type Tab = "chat" | "calendar" | "ai";

// 모바일 통합 meeting 화면 — 웹과 동일 컴포넌트로 완전 일치.
// 데스크탑은 ChatPane+AiAssistantPane+InfoPane 3단을 한 MeetingProvider에 동시 렌더한다.
// 모바일도 동일하게 3개 pane을 모두 마운트하고 탭은 visibility만 토글 → 상태·WS 브릿지가
// 데스크탑과 동치로 공유된다(ChatPane이 sendTimeSelection·consensus·미가용·finalization
// 브릿지를 세팅하므로 TimeBar 합의·호스트 확정이 작동). contextMode==="done"이면 완료 화면.
function MobileMeetingInner({ roomId, room }: { roomId: string; room: Room | null }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const init = searchParams.get("tab");
  const [tab, setTab] = useState<Tab>(init === "chat" ? "chat" : init === "calendar" ? "calendar" : "ai");
  const { contextMode, infoPanePhase, setContextMode } = useMeeting();
  const roomName = room?.name ?? "모임";

  // 데스크탑은 3 pane을 동시에 보여줘 흐름 진행 시 관련 pane(TimeBar·장소 상세)이 항상 보인다.
  // 모바일은 한 번에 한 탭이라, 흐름이 진행되면 캘린더 탭(InfoPane)으로 자동 전환해 같은 경험을
  // 준다 — (a) 시간대 조율 진입(dateConfirmed) (b) 장소 선택(contextMode="place")·확정 단계.
  // 첫 렌더는 건너뛰어 ?tab= 초기값을 존중.
  const prevPhase = useRef(infoPanePhase);
  const prevCtx = useRef(contextMode);
  useEffect(() => {
    const phaseChanged = infoPanePhase !== prevPhase.current;
    const ctxChanged = contextMode !== prevCtx.current;
    prevPhase.current = infoPanePhase;
    prevCtx.current = contextMode;
    if (ctxChanged && (contextMode === "place" || contextMode === "schedule")) {
      setTab("calendar");
    } else if (phaseChanged && infoPanePhase === "dateConfirmed") {
      setTab("calendar");
    }
  }, [infoPanePhase, contextMode]);

  // 완료(done) — 데스크탑 CompletionPage(고정 480px) 그대로, 390px엔 스케일 래핑.
  if (contextMode === "done") {
    return (
      <div style={{ width: "100%", height: "100dvh", overflowX: "hidden", overflowY: "auto", background: "#ffffff" }}>
        <div style={{ width: 480, transform: "scale(0.8125)", transformOrigin: "top left" }}>
          <CompletionPage />
        </div>
      </div>
    );
  }

  const TabBtn = ({ label, value }: { label: string; value: Tab }) => (
    <div
      className="flex-1 flex items-center justify-center cursor-pointer"
      onClick={() => setTab(value)}
      style={{
        fontFamily: "Pretendard, sans-serif",
        fontSize: 14,
        fontWeight: tab === value ? 600 : 500,
        color: tab === value ? "#4f46e5" : "#94a3b8",
        borderBottom: tab === value ? "2px solid #4f46e5" : "none",
      }}
    >
      {label}
    </div>
  );

  return (
    <div className="relative flex flex-col bg-white overflow-hidden" style={{ width: "100%", height: "100dvh" }}>
      {/* Header */}
      <div className="flex items-center shrink-0" style={{ height: 56, padding: "0 16px", borderBottom: "1px solid #e2e8f0" }}>
        <ArrowLeft size={24} color="#1e293b" className="shrink-0 cursor-pointer" onClick={() => router.push("/m/chat")} />
        <div className="flex-1 flex flex-col items-center gap-[2px]">
          <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 17, fontWeight: 600, color: "#1e293b" }}>{roomName}</span>
          <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 12, fontWeight: 400, color: "#94a3b8" }}>{room?.category ?? "모임"}</span>
        </div>
        {/* 데스크탑 '생성 완료' 헤더 버튼 parity — contextMode="done" → CompletionPage */}
        <button
          type="button"
          onClick={() => setContextMode?.("done")}
          className="shrink-0"
          style={{ marginRight: 10, padding: "5px 12px", borderRadius: 16, border: "1px solid #c7d2fe", background: "#eef2ff", color: "#4f46e5", fontFamily: "Pretendard, sans-serif", fontSize: 12, fontWeight: 600, cursor: "pointer" }}
        >
          완료
        </button>
        <Menu size={24} color="#64748b" className="shrink-0 cursor-pointer" onClick={() => router.push(`/m/meeting/detail?roomId=${roomId}`)} />
      </div>

      {/* Tab Bar — 채팅방 / 캘린더 / AI (모두 local, 3 pane 동시 마운트) */}
      <div className="flex shrink-0" style={{ height: 44, borderBottom: "1px solid #e2e8f0" }}>
        <TabBtn label="채팅방" value="chat" />
        <TabBtn label="캘린더" value="calendar" />
        <TabBtn label="AI" value="ai" />
      </div>

      {/* 3 pane 모두 마운트, visibility만 토글 — 데스크탑 3단 동시 렌더와 동치 */}
      <div className="flex-1 relative" style={{ minHeight: 0 }}>
        <div className="absolute inset-0 flex flex-col" style={{ display: tab === "chat" ? "flex" : "none", minHeight: 0 }}>
          <ChatPane />
        </div>
        <div className="absolute inset-0 flex flex-col" style={{ display: tab === "calendar" ? "flex" : "none", overflowY: "auto" }}>
          <InfoPane />
        </div>
        <div className="absolute inset-0 flex flex-col" style={{ display: tab === "ai" ? "flex" : "none", minHeight: 0 }}>
          <AiAssistantPane />
        </div>
      </div>
    </div>
  );
}

function MobileMeetingRoom() {
  const searchParams = useSearchParams();
  const roomId = searchParams.get("roomId") ?? "";
  const { user, loading: authLoading } = useAuth();
  const [room, setRoom] = useState<Room | null>(null);

  useEffect(() => {
    if (authLoading || !user || !roomId) return;
    apiFetch<Room>(`/api/v1/rooms/${roomId}`).then(setRoom).catch(() => null);
  }, [authLoading, user, roomId]);

  return (
    <MeetingProvider initialRoomId={roomId} initialRoomName={room?.name ?? ""}>
      <MobileMeetingInner roomId={roomId} room={room} />
    </MeetingProvider>
  );
}

export default function AiChatPage() {
  return (
    <Suspense fallback={null}>
      <MobileMeetingRoom />
    </Suspense>
  );
}
