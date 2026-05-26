"use client";

import { useRouter } from "next/navigation";
import { Sparkles, Users, Calendar, MapPin, Zap } from "lucide-react";

const QUICK_ITEMS = [
  { icon: Users, label: "인원 수", color: "#818cf8" },
  { icon: Calendar, label: "일정", color: "#34d399" },
  { icon: MapPin, label: "장소", color: "#f472b6" },
  { icon: Zap, label: "활동", color: "#fbbf24" },
];

const MEETING_TYPES = ["식사", "카페", "술자리", "회의", "모임"];

export default function QuickPreferences() {
  const router = useRouter();

  return (
    <div
      className="rounded-[20px] flex flex-col overflow-hidden border border-[#e2e8f0] shadow-[0_4px_10.5px_rgba(0,0,0,0.08)] w-full"
      style={{ minHeight: 490 }}
    >
      {/* Gradient header */}
      <div
        className="flex items-center gap-2.5 px-[28px] py-[22px]"
        style={{
          background: "linear-gradient(200deg, #a855f7 0%, #7c3aed 45%, #4f46e5 100%)",
          minHeight: 140,
          flexShrink: 0,
        }}
      >
        <Sparkles className="w-5 h-5 text-white shrink-0" />
        <div className="flex flex-col gap-1">
          <span className="text-[16px] font-bold text-white">AI 빠른 추천 보고서</span>
          <span className="text-[11px] text-white/75 leading-relaxed">
            조건을 선택하면 AI가 맞춤 모임 계획을 바로 추천해드려요
          </span>
        </div>
      </div>

      {/* Card body */}
      <div className="bg-white flex flex-col gap-4 px-[28px] py-[20px] flex-1">
        {/* Quick items */}
        <div className="grid grid-cols-4 gap-2">
          {QUICK_ITEMS.map(({ icon: Icon, label, color }) => (
            <div
              key={label}
              className="flex flex-col items-center gap-1.5 bg-[#f8fafc] rounded-[10px] py-2.5"
            >
              <Icon className="w-4 h-4" style={{ color }} />
              <span className="text-[10px] font-medium text-[#475569]">{label}</span>
            </div>
          ))}
        </div>

        {/* Meeting type chips */}
        <div className="flex flex-col gap-2">
          <span className="text-[11px] font-semibold text-[#94a3b8]">모임 종류 빠른 선택</span>
          <div className="flex flex-wrap gap-1.5">
            {MEETING_TYPES.map((type) => (
              <span
                key={type}
                className="text-[11px] font-medium text-[#4f46e5] bg-[#eef2ff] rounded-full px-2.5 py-1"
              >
                {type}
              </span>
            ))}
          </div>
        </div>

        {/* Info note */}
        <div className="flex items-start gap-2 bg-[#f8faff] rounded-[12px] px-3 py-2.5 mt-auto">
          <Sparkles className="w-3 h-3 text-[#4f46e5] shrink-0 mt-0.5" />
          <p className="text-[10px] text-[#64748b] leading-relaxed">
            일정·인원·장소·모임 종류를 선택하면 AI가 최적의 모임 계획을 추천합니다
          </p>
        </div>

        {/* CTA button */}
        <button
          onClick={() => router.push("/ai-recommend")}
          className="w-full h-[50px] rounded-[14px] text-white text-[14px] font-bold flex items-center justify-center gap-2 hover:opacity-90 transition-opacity"
          style={{
            background: "linear-gradient(180deg, #4f46e5 0%, #6366f1 100%)",
          }}
        >
          <Sparkles className="w-4 h-4" />
          AI 추천 보고서 작성하기
        </button>
      </div>
    </div>
  );
}
