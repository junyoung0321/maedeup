"use client";

import { useState } from "react";
import { User, Pencil, Calendar, Utensils, MapPin, Car, Plus } from "lucide-react";
import PersonalDataModal from "./PersonalDataModal";

const dataItems = [
  {
    icon: Calendar,
    iconBg: "#ede9fe",
    iconColor: "#7c3aed",
    rowBg: "#f8faff",
    label: "구글 캘린더",
    desc: "연동됨 · 이번 주 일정 3건",
    badge: "연동",
    badgeBg: "#dcfce7",
    badgeColor: "#16a34a",
    borderColor: "#e0e7ff",
  },
  {
    icon: Utensils,
    iconBg: "#fef3c7",
    iconColor: "#d97706",
    rowBg: "#fffbf5",
    label: "음식 제한",
    desc: "땅콩 알레르기 · 갑각류",
    badge: "2건",
    badgeBg: "#fef3c7",
    badgeColor: "#d97706",
    borderColor: "#fde68a",
  },
  {
    icon: MapPin,
    iconBg: "#dcfce7",
    iconColor: "#16a34a",
    rowBg: "#f0fdf8",
    label: "선호 지역",
    desc: "강남 · 홍대 · 신촌",
    badge: "3곳",
    badgeBg: "#dcfce7",
    badgeColor: "#16a34a",
    borderColor: "#bbf7d0",
  },
  {
    icon: Car,
    iconBg: "#e0f2fe",
    iconColor: "#2563eb",
    rowBg: "#f0f9ff",
    label: "이동 수단",
    desc: "대중교통 선호 · 자차 없음",
    badge: null,
    badgeBg: "",
    badgeColor: "",
    borderColor: "#bae6fd",
  },
];

export default function PersonalData() {
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <>
      <div
        className="bg-white rounded-[20px] p-5 flex flex-col h-full border border-[#e2e8f0] shadow-[0_4px_10.5px_rgba(0,0,0,0.08)]"
        style={{ width: 414, minHeight: 490 }}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-2">
            <User className="w-4 h-4 text-[#7c3aed]" />
            <span className="text-[16px] font-bold text-[#1e293b]">
              내 개인 데이터
            </span>
          </div>
          <Pencil className="w-4 h-4 text-[#94a3b8] cursor-pointer hover:text-[#64748b]" />
        </div>
        <p className="text-[11px] text-[#94a3b8] mb-4">
          어시스턴트가 참고하는 나의 정보
        </p>

        {/* Data items */}
        <div className="flex flex-col gap-3 flex-1">
          {dataItems.map((item) => {
            const Icon = item.icon;
            return (
              <div
                key={item.label}
                className="flex items-center gap-3 rounded-[12px] px-3 py-2.5 border"
                style={{ backgroundColor: item.rowBg, borderColor: item.borderColor }}
              >
                <div
                  className="w-10 h-10 rounded-[10px] flex items-center justify-center shrink-0"
                  style={{ backgroundColor: item.iconBg }}
                >
                  <Icon className="w-4 h-4" style={{ color: item.iconColor }} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-[14px] font-semibold text-[#1e293b]">
                    {item.label}
                  </p>
                  <p className="text-[11px] text-[#64748b]">{item.desc}</p>
                </div>
                {item.badge && (
                  <span
                    className="px-2.5 py-0.5 rounded-full text-[11px] font-medium shrink-0"
                    style={{
                      backgroundColor: item.badgeBg,
                      color: item.badgeColor,
                    }}
                  >
                    {item.badge}
                  </span>
                )}
              </div>
            );
          })}
        </div>

        {/* Add button */}
        <button
          onClick={() => setModalOpen(true)}
          className="mt-4 w-full py-2.5 rounded-[12px] bg-[#f8faff] border border-[#e0e7ff] text-[13px] font-medium text-[#4f46e5] hover:bg-[#eef2ff] transition-colors flex items-center justify-center gap-1.5"
        >
          <Plus className="w-3.5 h-3.5" />
          개인 데이터 추가
        </button>
      </div>

      <PersonalDataModal open={modalOpen} onClose={() => setModalOpen(false)} />
    </>
  );
}
