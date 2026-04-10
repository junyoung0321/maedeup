"use client";

import { useParams } from "next/navigation";
import Header from "@/components/layout/Header";
import ChatPane from "@/components/meeting/ChatPane";
import AiAssistantPane from "@/components/meeting/AiAssistantPane";
import CalendarPane from "@/components/meeting/CalendarPane";
import PlaceAiPane from "@/components/meeting/PlaceAiPane";
import PlaceDetailPane from "@/components/meeting/PlaceDetailPane";
import CompletionPage from "@/components/meeting/CompletionPage";
import { CalendarDays, MapPin, CheckCircle2 } from "lucide-react";
import { MeetingProvider, useMeeting } from "@/contexts/MeetingContext";

export default function MeetingPage() {
  const params = useParams();
  const roomId = typeof params.id === "string" ? params.id : "1";

  return (
    <MeetingProvider initialRoomId={roomId}>
      <MeetingPageInner />
    </MeetingProvider>
  );
}

function MeetingPageInner() {
  const { contextMode, setContextMode, selectedPlace, setSelectedPlace } = useMeeting();

  if (contextMode === "done") {
    return (
      <div className="min-h-screen bg-white flex flex-col">
        <Header showSteps currentStep="done" />
        <CompletionPage />
      </div>
    );
  }

  return (
    <div style={{ minHeight: "100vh", background: "#ffffff", fontFamily: "Pretendard, sans-serif" }}>
      <Header showSteps currentStep={contextMode} />

      {/* Context Mode Switcher */}
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          gap: 8,
          padding: "16px 0 0",
        }}
      >
        <ModeTab
          active={contextMode === "schedule"}
          icon={<CalendarDays size={16} />}
          label="일정 조율"
          onClick={() => setContextMode("schedule")}
        />
        <ModeTab
          active={contextMode === "place"}
          icon={<MapPin size={16} />}
          label="장소 조율"
          onClick={() => setContextMode("place")}
        />
        <ModeTab
          active={false}
          icon={<CheckCircle2 size={16} />}
          label="생성 완료"
          onClick={() => setContextMode("done")}
        />
      </div>

      {/* 3-Panel Layout */}
      <main
        style={{
          display: "flex",
          justifyContent: "center",
          alignItems: "flex-start",
          gap: 53,
          paddingTop: 24,
          paddingLeft: 48,
          paddingRight: 48,
        }}
      >
        <ChatPane />

        {contextMode === "schedule" && (
          <>
            <AiAssistantPane />
            <CalendarPane />
          </>
        )}
        {contextMode === "place" && (
          <>
            <PlaceAiPane onSelectPlace={setSelectedPlace} />
            <PlaceDetailPane place={selectedPlace} />
          </>
        )}
      </main>
    </div>
  );
}

function ModeTab({
  active,
  icon,
  label,
  onClick,
}: {
  active: boolean;
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        padding: "8px 20px",
        borderRadius: 24,
        border: active ? "2px solid #4f46e5" : "1px solid #e2e8f0",
        background: active ? "#eef2ff" : "#ffffff",
        color: active ? "#4f46e5" : "#64748b",
        fontSize: 14,
        fontWeight: active ? 600 : 400,
        cursor: "pointer",
        fontFamily: "Pretendard, sans-serif",
        transition: "all 0.2s",
      }}
    >
      {icon}
      {label}
    </button>
  );
}
