"use client";

import { useParams } from "next/navigation";
import Header from "@/components/layout/Header";
import type { Step } from "@/components/layout/StepIndicator";
import ChatPane from "@/components/meeting/ChatPane";
import AiAssistantPane from "@/components/meeting/AiAssistantPane";
import CompletionPage from "@/components/meeting/CompletionPage";
import GuestJoinGate from "@/components/meeting/GuestJoinGate";
import InfoPane from "@/components/meeting/InfoPane";
import LeaveRoomButton from "@/components/meeting/LeaveRoomButton";
import { MeetingProvider, useMeeting } from "@/contexts/MeetingContext";
import MeetingPreferencePopup from "@/components/meeting/MeetingPreferencePopup";
import { useEffect, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { apiFetch } from "@/lib/api";

function getSingleParamValue(value: string | string[] | undefined): string | null {
  if (typeof value === "string" && value.trim()) {
    return value;
  }
  if (Array.isArray(value)) {
    const first = value[0];
    if (typeof first === "string" && first.trim()) {
      return first;
    }
  }
  return null;
}

export default function MeetingPage() {
  const params = useParams<{ id?: string | string[] }>();
  const roomId = getSingleParamValue(params?.id) ?? "1";

  return (
    <MeetingProvider initialRoomId={roomId}>
      <MeetingPageInner />
    </MeetingProvider>
  );
}

function MeetingPageInner() {
  const { contextMode, setContextMode, roomId, refreshPreferences } = useMeeting();
  const { user, loading: authLoading } = useAuth();
  const [showPreferencePopup, setShowPreferencePopup] = useState(false);
  const [preferenceChecked, setPreferenceChecked] = useState(false);

  // 입장 시 선호 정보 입력 여부 확인
  useEffect(() => {
    if (!roomId || !user || preferenceChecked) return;
    apiFetch<{ preferences: Array<{ user_id: number }> }>(
      `/api/v1/rooms/${roomId}/preferences`,
    )
      .then((data) => {
        const userId = user?.sub ? Number(user.sub) : NaN;
        const alreadySubmitted =
          Number.isFinite(userId) &&
          data.preferences.some((p) => p.user_id === userId);
        if (!alreadySubmitted) {
          setShowPreferencePopup(true);
        }
        setPreferenceChecked(true);
      })
      .catch(() => {
        setPreferenceChecked(true);
      });
  }, [roomId, user, preferenceChecked]);

  // 팝업 제출 후 팝업 닫기 + 선호도 데이터 InfoPane re-fetch 트리거 (F-2)
  const handlePreferenceSubmitted = () => {
    setShowPreferencePopup(false);
    refreshPreferences();
  };

  // 로그인/게스트 가입 전에는 나머지 UI를 로드하지 않음. 모든 hook 호출 이후에
  // 조건부 렌더링을 수행해 hook 순서 규칙을 유지.
  if (authLoading) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", color: "#94a3b8" }}>
        불러오는 중…
      </div>
    );
  }
  if (!user) {
    return (
      <GuestJoinGate
        roomId={roomId}
        onJoined={() => window.location.reload()}
      />
    );
  }

  const currentStep: Step = contextMode === "agent" ? "schedule" : contextMode;

  if (contextMode === "done") {
    return (
      <div className="min-h-screen bg-white flex flex-col">
        <Header showSteps currentStep="done" />
        <CompletionPage />
      </div>
    );
  }

  return (
    <div style={{ height: "100vh", overflow: "hidden", background: "#ffffff", fontFamily: "Pretendard, sans-serif", display: "flex", flexDirection: "column" }}>
      <Header showSteps currentStep={currentStep}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <LeaveRoomButton roomId={roomId} />
          <button
            onClick={() => setContextMode("done")}
            type="button"
            style={{
              display: "flex",
              alignItems: "center",
              padding: "6px 18px",
              borderRadius: 20,
              border: "1px solid rgba(255,255,255,0.3)",
              background: "rgba(255,255,255,0.15)",
              color: "#ffffff",
              fontSize: 13,
              fontWeight: 600,
              cursor: "pointer",
              fontFamily: "Pretendard, sans-serif",
              transition: "all 0.2s",
              backdropFilter: "blur(4px)",
            }}
          >
            생성 완료
          </button>
        </div>
      </Header>

      <main
        style={{
          display: "flex",
          alignItems: "stretch",
          gap: "clamp(6px, 0.8vw, 16px)",
          padding: "clamp(6px, 0.8vw, 16px)",
          flex: 1,
          minHeight: 0,
          maxWidth: 1800,
          margin: "0 auto",
          width: "100%",
        }}
      >
        <ChatPane />
        <AiAssistantPane />
        <InfoPane />
      </main>

      {showPreferencePopup && (
        <MeetingPreferencePopup
          roomId={roomId}
          onClose={() => setShowPreferencePopup(false)}
          onSubmitted={handlePreferenceSubmitted}
        />
      )}
    </div>
  );
}
