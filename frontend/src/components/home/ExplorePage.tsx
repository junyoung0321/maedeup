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

      {/* 반응형: mobile 1열 → sm 2열 → lg 3열. padding/gap도 viewport 따라 축소. */}
      <main className="max-w-[1440px] mx-auto px-4 sm:px-8 lg:px-[55px] py-6 sm:py-8 flex flex-col gap-6 sm:gap-10">
        {/* ===== Row 1: AI 섹션 — desktop에서 좌우, mobile에서 stack ===== */}
        <div className="flex flex-col lg:flex-row gap-6 lg:gap-8">
          <div className="w-full lg:max-w-[728px] lg:flex-1">
            <AiRecommendCard />
          </div>
          <div className="w-full lg:max-w-[569px] lg:flex-1 lg:pt-[60px]">
            <UpcomingMeeting />
          </div>
        </div>

        {/* ===== Row 2: 1열 → 2열 → 3열 ===== */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6 lg:gap-[45px]">
          <FriendList />
          <MeetingList />
          <MiniCalendar />
        </div>

        {/* ===== Row 3: 1열 → 2열 → 3열 ===== */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6 lg:gap-[45px]">
          <PersonalData />
          <AssistantChat />
          <QuickPreferences />
        </div>

        {/* spacer for floating bar — mobile에선 stack된 버튼 두 개 + 여유 */}
        <div className="h-[140px] sm:h-[100px]" />
      </main>

      {/* Floating bottom bar — mobile에선 버튼 stack, desktop은 가로 배치 */}
      <div className="fixed bottom-0 left-0 right-0 z-50 bg-white/80 backdrop-blur-md border-t border-[#e2e8f0]">
        <div className="max-w-[1440px] mx-auto px-4 sm:px-8 lg:px-[55px] py-3 sm:py-4 flex flex-col sm:flex-row sm:justify-end gap-2 sm:gap-4 lg:gap-6">
          <button
            onClick={() => setInviteOpen(true)}
            className="w-full sm:w-[180px] lg:w-[215px] h-[48px] sm:h-[64px] lg:h-[76px] rounded-[15px] bg-[#4f46e5] text-white text-[16px] sm:text-[22px] lg:text-[30px] font-semibold hover:bg-[#4338ca] transition-colors shadow-lg"
          >
            모임 초대
          </button>
          <button
            onClick={() => router.push("/meeting/new")}
            className="w-full sm:w-[180px] lg:w-[215px] h-[48px] sm:h-[64px] lg:h-[76px] rounded-[15px] bg-[#4f46e5] text-white text-[16px] sm:text-[22px] lg:text-[30px] font-semibold hover:bg-[#4338ca] transition-colors shadow-lg"
          >
            모임 생성
          </button>
        </div>
      </div>

      <InviteModal open={inviteOpen} onClose={() => setInviteOpen(false)} />
    </div>
  );
}
