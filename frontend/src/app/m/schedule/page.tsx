"use client";

import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Menu,
  ChevronLeft,
  ChevronRight,
  Check,
  Circle,
  Vote,
} from "lucide-react";

export default function ScheduleVotePage() {
  const router = useRouter();
  // Calendar data: [day, fraction, total]
  const calendarRows: (null | { day: number; count?: number; total?: number })[][] = [
    [
      null,
      { day: 2, count: 3, total: 5 },
      { day: 3, count: 4, total: 5 },
      { day: 4, count: 5, total: 5 },
      { day: 5, count: 4, total: 5 },
      { day: 6, count: 3, total: 5 },
      { day: 7 },
    ],
    [
      null,
      { day: 9, count: 2, total: 5 },
      { day: 10, count: 4, total: 5 },
      { day: 11, count: 5, total: 5 },
      { day: 12, count: 5, total: 5 },
      { day: 13, count: 3, total: 5 },
      null,
    ],
    [
      null,
      { day: 16, count: 4, total: 5 },
      { day: 17, count: 5, total: 5 },
      { day: 18, count: 5, total: 5 },
      { day: 19, count: 4, total: 5 },
      { day: 20, count: 3, total: 5 },
      null,
    ],
    [
      null,
      { day: 23, count: 5, total: 5 },
      { day: 24, count: 5, total: 5 },
      { day: 25, count: 4, total: 5 },
      { day: 26, count: 3, total: 5 },
      { day: 27, count: 2, total: 5 },
      null,
    ],
  ];

  const getFractionColor = (count: number) => {
    if (count === 5) return "#22c55e";
    if (count === 4) return "#eab308";
    return "#ef4444";
  };

  const selectedDay = 24;
  const highlightDays = [4, 11, 12, 17, 23, 25];

  const timeSlots = [
    { label: "3/23 (월) 3:00~5:00", fraction: "5/5", selected: true, avatarColors: ["#c7d2fe", "#93c5fd", "#86efac"] },
    { label: "3/24 (화) 2:00~4:00", fraction: "4/5", selected: true, avatarColors: ["#c7d2fe", "#93c5fd", "#86efac"] },
    { label: "3/24 (화) 6:00~8:00", fraction: "3/5", selected: false, avatarColors: ["#c7d2fe", "#93c5fd", "#86efac"] },
    { label: "3/25 (수) 1:00~3:00", fraction: "2/5", selected: false, avatarColors: ["#c7d2fe", "#93c5fd"] },
  ];

  return (
    <div
      style={{
        width: 390,
        height: 844,
        overflow: "hidden",
        backgroundColor: "#ffffffff",
        fontFamily: "Pretendard, sans-serif",
      }}
      className="flex flex-col mx-auto"
    >
      {/* 1. Header */}
      <div
        className="flex items-center shrink-0"
        style={{
          height: 56,
          backgroundColor: "#ffffff",
          padding: "0 16px",
          borderBottom: "1px solid #e2e8f0",
          gap: 12,
        }}
      >
        <ArrowLeft size={24} color="#1e293b" className="shrink-0 cursor-pointer" onClick={() => router.push("/m/chat/schedule")} />
        <div className="flex-1 flex flex-col items-center" style={{ gap: 2 }}>
          <span
            style={{
              fontFamily: "Pretendard, sans-serif",
              fontSize: 17,
              fontWeight: 600,
              color: "#1e293b",
              textAlign: "center",
            }}
          >
            졸업 프로젝트 회의
          </span>
          <span
            style={{
              fontFamily: "Pretendard, sans-serif",
              fontSize: 12,
              fontWeight: 400,
              color: "#94a3b8",
              textAlign: "center",
            }}
          >
            5명 참여 중
          </span>
        </div>
        <Menu size={24} color="#64748b" className="shrink-0 cursor-pointer" onClick={() => router.push("/m/meeting/detail")} />
      </div>

      {/* 2. Tabs */}
      <div
        className="flex shrink-0"
        style={{
          height: 44,
          backgroundColor: "#ffffff",
          borderBottom: "1px solid #e2e8f0",
        }}
      >
        <div
          className="flex-1 flex items-center justify-center cursor-pointer"
          onClick={() => router.push("/m/chat/schedule")}
          style={{
            fontFamily: "Pretendard, sans-serif",
            fontSize: 14,
            fontWeight: 500,
            color: "#94a3b8",
          }}
        >
          채팅방
        </div>
        <div
          className="flex-1 flex items-center justify-center"
          style={{
            fontFamily: "Pretendard, sans-serif",
            fontSize: 14,
            fontWeight: 600,
            color: "#4f46e5",
            borderBottom: "2px solid #4f46e5",
          }}
        >
          캘린더
        </div>
      </div>

      {/* 3. Calendar content */}
      <div
        className="flex-1 flex flex-col"
        style={{
          padding: "12px 16px 16px 16px",
          gap: 12,
          overflowY: "auto",
        }}
      >
        {/* Month navigation */}
        <div className="flex items-center justify-between">
          <ChevronLeft size={20} color="#64748b" style={{ cursor: "pointer" }} />
          <span
            style={{
              fontFamily: "Pretendard, sans-serif",
              fontSize: 16,
              fontWeight: 600,
              color: "#1e293b",
            }}
          >
            매듭 2026년 3월
          </span>
          <ChevronRight size={20} color="#64748b" style={{ cursor: "pointer" }} />
        </div>

        {/* Day headers */}
        <div className="grid grid-cols-7">
          {["일", "월", "화", "수", "목", "금", "토"].map((d) => (
            <div
              key={d}
              className="text-center"
              style={{
                fontFamily: "Pretendard, sans-serif",
                fontSize: 12,
                fontWeight: 400,
                color: "#94a3b8",
              }}
            >
              {d}
            </div>
          ))}
        </div>

        {/* Calendar grid */}
        <div className="flex flex-col" style={{ gap: 2 }}>
          {calendarRows.map((row, ri) => (
            <div key={ri} className="grid grid-cols-7" style={{ gap: 2 }}>
              {row.map((cell, ci) => {
                if (!cell) {
                  return <div key={ci} style={{ height: 48 }} />;
                }

                const isSelected = cell.day === selectedDay;
                const is5of5 = cell.count === 5 && cell.total === 5;
                const isHighlight = highlightDays.includes(cell.day);

                let bgColor = "transparent";
                if (isSelected) bgColor = "#4f46e5";
                else if (is5of5 && isHighlight) bgColor = "#e0e7ff";

                return (
                  <div
                    key={ci}
                    className="flex flex-col items-center justify-center"
                    style={{
                      height: 48,
                      gap: 2,
                      backgroundColor: bgColor,
                      borderRadius: isSelected || isHighlight ? 8 : 0,
                    }}
                  >
                    <span
                      style={{
                        fontFamily: "Pretendard, sans-serif",
                        fontSize: 13,
                        fontWeight: 400,
                        color: isSelected ? "#ffffff" : "#334155",
                      }}
                    >
                      {cell.day}
                    </span>
                    {cell.count !== undefined && cell.total !== undefined && (
                      <span
                        style={{
                          fontFamily: "Inter, sans-serif",
                          fontSize: 9,
                          fontWeight: 600,
                          color: isSelected
                            ? "#ffffff"
                            : getFractionColor(cell.count),
                        }}
                      >
                        {cell.count}/{cell.total}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          ))}
        </div>

        {/* Divider */}
        <div style={{ height: 1, backgroundColor: "#e2e8f0" }} />

        {/* Available time header */}
        <div className="flex flex-col" style={{ gap: 4 }}>
          <span
            style={{
              fontFamily: "Pretendard, sans-serif",
              fontSize: 15,
              fontWeight: 600,
              color: "#1e293b",
            }}
          >
            모두가 가능한 시간대
          </span>
          <span
            style={{
              fontFamily: "Pretendard, sans-serif",
              fontSize: 11,
              fontWeight: 400,
              color: "#94a3b8",
            }}
          >
            3월 23일 ~ 25일 기준
          </span>
        </div>

        {/* Time slots */}
        <div className="flex flex-col" style={{ gap: 8 }}>
          {timeSlots.map((slot, i) => (
            <div
              key={i}
              className="flex items-center"
              style={{
                height: 36,
                borderRadius: 10,
                padding: "0 12px",
                gap: 8,
                backgroundColor: slot.selected ? "#f0fdf4" : "#ffffff",
                border: slot.selected
                  ? "1.5px solid #22c55e"
                  : "1px solid #e2e8f0",
                boxShadow: slot.selected
                  ? "0 1px 3px #4f46e520"
                  : "none",
              }}
            >
              {slot.selected ? (
                <Check size={14} color="#4f46e5" strokeWidth={2.5} />
              ) : (
                <Circle size={14} color="#cbd5e1" strokeWidth={1.5} />
              )}
              <span
                style={{
                  fontFamily: "Inter, sans-serif",
                  fontSize: 11,
                  fontWeight: slot.selected ? 600 : 500,
                  color: slot.selected ? "#166534" : "#374151",
                }}
              >
                {slot.label}
              </span>
              <div className="flex-1" />
              <span
                style={{
                  fontFamily: "Inter, sans-serif",
                  fontSize: 10,
                  fontWeight: 600,
                  color: slot.selected ? "#22c55e" : "#94a3b8",
                }}
              >
                {slot.fraction}
              </span>
              {/* Avatar dots */}
              <div className="flex items-center" style={{ marginLeft: 4 }}>
                {slot.avatarColors.map((color, ai) => (
                  <div
                    key={ai}
                    style={{
                      width: 16,
                      height: 16,
                      borderRadius: "50%",
                      backgroundColor: color,
                      marginLeft: ai > 0 ? -4 : 0,
                      border: "1.5px solid #ffffff",
                    }}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Selection count */}
        <span
          style={{
            fontFamily: "Pretendard, sans-serif",
            fontSize: 12,
            fontWeight: 500,
            color: "#4f46e5",
          }}
        >
          2개 선택됨
        </span>
      </div>

      {/* 4. Button area */}
      <div
        className="shrink-0 flex items-center justify-center"
        style={{
          backgroundColor: "#ffffff",
          padding: "12px 20px",
          borderTop: "1px solid #e2e8f0",
        }}
      >
        <button
          className="flex items-center justify-center w-full"
          onClick={() => router.push("/m/schedule/confirm")}
          style={{
            height: 44,
            borderRadius: 12,
            backgroundColor: "#4f46e5",
            gap: 8,
            border: "none",
            cursor: "pointer",
          }}
        >
          <Vote size={18} color="#ffffff" />
          <span
            style={{
              fontFamily: "Pretendard, sans-serif",
              fontSize: 14,
              fontWeight: 600,
              color: "#ffffff",
            }}
          >
            투표 제출
          </span>
        </button>
      </div>

      {/* 5. Home bar */}
      <div
        className="shrink-0 flex items-center justify-center"
        style={{ height: 20 }}
      >
        <div
          style={{
            width: 134,
            height: 5,
            borderRadius: 100,
            backgroundColor: "#000000",
          }}
        />
      </div>
    </div>
  );
}
