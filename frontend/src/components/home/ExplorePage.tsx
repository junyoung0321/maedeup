"use client";

import { useState } from "react";
import Header from "@/components/layout/Header";
import AiRecommendCard from "./AiRecommendCard";
import UpcomingMeeting from "./UpcomingMeeting";
import FriendList from "./FriendList";
import MeetingList from "./MeetingList";
import MiniCalendar from "./MiniCalendar";
import PersonalData from "./PersonalData";
import AssistantChat from "./AssistantChat";
import QuickPreferences from "./QuickPreferences";
import InviteModal from "./InviteModal";
import { useRouter } from "next/navigation";

export default function ExplorePage() {
  const router = useRouter();
  const [inviteOpen, setInviteOpen] = useState(false);

  return (
    <div className="min-h-screen bg-white">
      <Header />

      <main className="max-w-[1440px] mx-auto px-[55px] py-8 flex flex-col gap-10">
        {/* ===== Row 1: AI Section — 2 columns ===== */}
        <div className="flex gap-8">
          {/* Left: AI 추천 card (728x419) */}
          <div className="shrink-0">
            <AiRecommendCard />
          </div>

          {/* Right: 가장 임박한 모임 (569x320) */}
          <div className="shrink-0 pt-[60px]">
            <UpcomingMeeting />
          </div>
        </div>

        {/* ===== Row 2: 3 equal columns ===== */}
        <div className="grid grid-cols-3 gap-[45px]">
          <FriendList />
          <MeetingList />
          <MiniCalendar />
        </div>

        {/* ===== Row 3: 3 equal columns ===== */}
        <div className="grid grid-cols-3 gap-[45px]">
          <PersonalData />
          <AssistantChat />
          <QuickPreferences />
        </div>

        {/* spacer for floating bar */}
        <div className="h-[100px]" />
      </main>

      {/* Floating bottom bar */}
      <div className="fixed bottom-0 left-0 right-0 z-50 bg-white/80 backdrop-blur-md border-t border-[#e2e8f0]">
        <div className="max-w-[1440px] mx-auto px-[55px] py-4 flex justify-end gap-6">
          <button
            onClick={() => setInviteOpen(true)}
            className="w-[215px] h-[76px] rounded-[15px] bg-[#4f46e5] text-white text-[30px] font-semibold hover:bg-[#4338ca] transition-colors shadow-lg"
          >
            모임 초대
          </button>
          <button
            onClick={() => router.push("/meeting/new")}
            className="w-[215px] h-[76px] rounded-[15px] bg-[#4f46e5] text-white text-[30px] font-semibold hover:bg-[#4338ca] transition-colors shadow-lg"
          >
            모임 생성
          </button>
        </div>
      </div>

      <InviteModal open={inviteOpen} onClose={() => setInviteOpen(false)} />
    </div>
  );
}
