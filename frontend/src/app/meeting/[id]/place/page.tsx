"use client";

import { useState } from "react";
import Header from "@/components/layout/Header";
import ChatPane from "@/components/meeting/ChatPane";
import PlaceAiPane from "@/components/meeting/PlaceAiPane";
import PlaceDetailPane from "@/components/meeting/PlaceDetailPane";

interface PlaceResult {
  id: string;
  name: string;
  address: string;
  phone: string;
  url: string;
  x: string;
  y: string;
  category: string;
}

export default function PlacePage() {
  const [selectedPlace, setSelectedPlace] = useState<PlaceResult | null>(null);

  return (
    <div className="min-h-screen bg-white">
      <Header showSteps currentStep="place" />
      <main className="flex justify-center items-start gap-[53px] pt-10 px-12">
        <ChatPane />
        <PlaceAiPane onSelectPlace={setSelectedPlace} />
        <PlaceDetailPane place={selectedPlace} />
      </main>
    </div>
  );
}
