"use client";

import { useParams } from "next/navigation";
import Header from "@/components/layout/Header";
import type { Step } from "@/components/layout/StepIndicator";
import ChatPane from "@/components/meeting/ChatPane";
import AiAssistantPane from "@/components/meeting/AiAssistantPane";
import CompletionPage from "@/components/meeting/CompletionPage";
import InfoPane from "@/components/meeting/InfoPane";
import { MeetingProvider, useMeeting } from "@/contexts/MeetingContext";

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
  const { contextMode, setContextMode } = useMeeting();
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
    <div style={{ minHeight: "100vh", background: "#ffffff", fontFamily: "Pretendard, sans-serif" }}>
      <Header showSteps currentStep={currentStep} />

      <div
        style={{
          display: "flex",
          justifyContent: "flex-end",
          padding: "16px 48px 0",
        }}
      >
        <button
          onClick={() => setContextMode("done")}
          type="button"
          style={{
            display: "flex",
            alignItems: "center",
            padding: "8px 20px",
            borderRadius: 24,
            border: "1px solid #4f46e5",
            background: "#4f46e5",
            color: "#ffffff",
            fontSize: 14,
            fontWeight: 600,
            cursor: "pointer",
            fontFamily: "Pretendard, sans-serif",
            transition: "all 0.2s",
          }}
        >
          생성 완료
        </button>
      </div>

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
        <AiAssistantPane />
        <InfoPane />
      </main>
    </div>
  );
}
