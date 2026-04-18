"use client";

import { useState } from "react";
import QuickMatchPopup from "./QuickMatchPopup";
import AiPlacePopup from "./AiPlacePopup";

export default function AiRecommendCard() {
  const [quickMatchOpen, setQuickMatchOpen] = useState(false);
  const [aiPlaceOpen, setAiPlaceOpen] = useState(false);

  return (
    <>
      <div
        className="bg-white rounded-[24px] p-6 border border-[#e5e7eb] shadow-[0_4px_3px_rgba(0,0,0,0.25)]"
        style={{ width: 728, minHeight: 419 }}
      >
        {/* Title */}
        <h2 className="text-[28px] font-semibold text-[#111827]">AI 추천</h2>
        <p className="text-[18px] text-[#6b7280] mt-1 mb-5">
          지금 상황에 맞는 모임을 바로 시작해보세요
        </p>

        {/* Two gradient cards side by side */}
        <div className="flex gap-4">
          {/* Card A: Purple gradient - friend availability */}
          <div
            onClick={() => setQuickMatchOpen(true)}
            className="flex-1 rounded-[18px] p-5 flex flex-col justify-between text-white min-h-[280px] cursor-pointer hover:opacity-95 transition-opacity"
            style={{
              background:
                "linear-gradient(160deg, #7c3aed 0%, #4f46e5 50%, #6366f1 100%)",
            }}
          >
            <div>
              <span className="text-[15px] font-medium text-[#e0e7ff]">
                지금 시간대 가능한 친구
              </span>
              <h3 className="text-[24px] font-bold mt-2 leading-snug text-white">
                지금 바로 모임 가능
              </h3>

              {/* Friend availability list */}
              <div className="mt-4 flex flex-col gap-2">
                <div className="flex items-center justify-between">
                  <span className="text-[14px] text-white">김창윤</span>
                  <span className="text-[13px] text-[#bbf7d0]">가능</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[14px] text-white">정준영</span>
                  <span className="text-[13px] text-[#bbf7d0]">가능</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[14px] text-white">한산희</span>
                  <span className="text-[13px] text-[#fde68a]">30분 후</span>
                </div>
              </div>
            </div>

            <button className="mt-4 self-start px-5 py-2 rounded-full bg-white/20 text-[15px] font-medium text-white hover:bg-white/30 transition-colors">
              모임 만들기
            </button>
          </div>

          {/* Card B: Green-to-teal gradient - place recommendations */}
          <div
            onClick={() => setAiPlaceOpen(true)}
            className="flex-1 rounded-[18px] p-5 flex flex-col justify-between text-white min-h-[280px] cursor-pointer hover:opacity-95 transition-opacity"
            style={{
              background:
                "linear-gradient(145deg, #0ea5e9 0%, #22c55e 100%)",
            }}
          >
            <div>
              <span className="text-[15px] font-medium text-[#dcfce7]">
                근처 10분 거리 카페
              </span>
              <h3 className="text-[24px] font-bold mt-2 leading-snug text-white">
                이번 주 모임 추천 장소
              </h3>

              {/* Place list */}
              <div className="mt-4 flex flex-col gap-3">
                <div>
                  <p className="text-[14px] font-semibold text-white">
                    1) 스터디 카페 노트
                  </p>
                  <p className="text-[12px] text-[#dcfce7]">
                    도보 7분 · 4인석 여유
                  </p>
                </div>
                <div>
                  <p className="text-[14px] font-semibold text-white">
                    2) 카페 라운지 24
                  </p>
                  <p className="text-[12px] text-[#dcfce7]">
                    도보 9분 · 조용한 좌석
                  </p>
                </div>
              </div>
            </div>

            <button className="mt-4 self-start px-5 py-2 rounded-full bg-white/20 text-[13px] font-semibold text-white hover:bg-white/30 transition-colors">
              추천으로 생성
            </button>
          </div>
        </div>
      </div>

      <QuickMatchPopup open={quickMatchOpen} onClose={() => setQuickMatchOpen(false)} />
      <AiPlacePopup open={aiPlaceOpen} onClose={() => setAiPlaceOpen(false)} />
    </>
  );
}
