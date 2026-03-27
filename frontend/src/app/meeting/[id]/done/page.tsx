"use client";

import Header from "@/components/layout/Header";
import CompletionPage from "@/components/meeting/CompletionPage";

export default function DonePage() {
  return (
    <div className="min-h-screen bg-white flex flex-col">
      <Header showSteps currentStep="done" />
      <CompletionPage />
    </div>
  );
}
