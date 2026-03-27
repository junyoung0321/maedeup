"use client";

import Header from "@/components/layout/Header";
import ChatPane from "@/components/meeting/ChatPane";
import PlaceAiPane from "@/components/meeting/PlaceAiPane";
import PlaceDetailPane from "@/components/meeting/PlaceDetailPane";

export default function PlacePage() {
  return (
    <div className="min-h-screen bg-white">
      <Header showSteps currentStep="place" />
      <main className="flex justify-center items-start gap-[53px] pt-10 px-12">
        <ChatPane />
        <PlaceAiPane />
        <PlaceDetailPane />
      </main>
    </div>
  );
}
