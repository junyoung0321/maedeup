"use client";

import { useState } from "react";
import { SlidersHorizontal, Shield } from "lucide-react";

interface ToggleItem {
  id: string;
  label: string;
  desc: string;
  defaultOn: boolean;
}

const toggleItems: ToggleItem[] = [
  {
    id: "calendar-sync",
    label: "캘린더 자동 동기화",
    desc: "구글 캘린더 일정 실시간 반영",
    defaultOn: true,
  },
  {
    id: "food-share",
    label: "음식 제한 공유",
    desc: "모임 장소 추천 시 자동 반영",
    defaultOn: true,
  },
  {
    id: "location-rec",
    label: "위치 기반 추천",
    desc: "선호 지역 기반 장소 추천",
    defaultOn: false,
  },
  {
    id: "transport",
    label: "이동수단 고려",
    desc: "대중교통/자차 기반 접근성 반영",
    defaultOn: true,
  },
];

export default function QuickPreferences() {
  const [toggles, setToggles] = useState<Record<string, boolean>>(
    Object.fromEntries(toggleItems.map((t) => [t.id, t.defaultOn]))
  );

  const toggle = (id: string) => {
    setToggles((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div
      className="bg-white rounded-[20px] p-6 flex flex-col h-full border border-[#e2e8f0] shadow-[0_4px_10.5px_rgba(0,0,0,0.08)]"
      style={{ width: 414, minHeight: 490 }}
    >
      {/* Header */}
      <div className="flex items-center gap-2 mb-1">
        <SlidersHorizontal className="w-4 h-4 text-[#4f46e5]" />
        <span className="text-[16px] font-bold text-[#1e293b]">
          빠른 선호 설정
        </span>
      </div>
      <p className="text-[11px] text-[#94a3b8] mb-4">
        어시스턴트가 모임 추천 시 참고합니다
      </p>

      {/* Divider */}
      <div className="h-px bg-[#e2e8f0] mb-4" />

      {/* Toggle rows */}
      <div className="flex flex-col gap-5 flex-1">
        {toggleItems.map((item) => {
          const isOn = toggles[item.id];
          return (
            <div key={item.id} className="flex items-center justify-between">
              <div>
                <p className="text-[13px] font-semibold text-[#1e293b]">
                  {item.label}
                </p>
                <p className="text-[11px] text-[#94a3b8]">{item.desc}</p>
              </div>
              <button
                onClick={() => toggle(item.id)}
                className="relative w-11 h-6 rounded-full transition-colors duration-200 shrink-0 ml-3"
                style={{ backgroundColor: isOn ? "#4f46e5" : "#e2e8f0" }}
              >
                <div
                  className="absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform duration-200"
                  style={{
                    transform: isOn ? "translateX(22px)" : "translateX(2px)",
                  }}
                />
              </button>
            </div>
          );
        })}
      </div>

      {/* Divider */}
      <div className="h-px bg-[#e2e8f0] mt-4 mb-3" />

      {/* Privacy note */}
      <div className="flex items-start gap-2 bg-[#f8faff] rounded-[12px] px-3 py-2.5">
        <Shield className="w-3.5 h-3.5 text-[#4f46e5] shrink-0 mt-0.5" />
        <p className="text-[10px] text-[#64748b] leading-relaxed">
          개인 데이터는 이 레이어에만 저장되며
          <br />
          모임 채팅방에 공유되지 않습니다
        </p>
      </div>
    </div>
  );
}
