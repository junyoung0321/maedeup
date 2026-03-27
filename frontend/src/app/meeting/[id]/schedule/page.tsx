"use client";

import Header from "@/components/layout/Header";
import ChatPane from "@/components/meeting/ChatPane";
import AiAssistantPane from "@/components/meeting/AiAssistantPane";
import CalendarPane from "@/components/meeting/CalendarPane";

export default function SchedulePage() {
  return (
    <div style={{ minHeight: "100vh", background: "#ffffff", fontFamily: "Pretendard, sans-serif" }}>
      <Header showSteps currentStep="schedule" />
      <main
        style={{
          display: "flex",
          justifyContent: "center",
          alignItems: "flex-start",
          gap: 53,
          paddingTop: 40,
          paddingLeft: 48,
          paddingRight: 48,
        }}
      >
        <ChatPane />
        <AiAssistantPane />
        <CalendarPane />
      </main>
    </div>
  );
}
