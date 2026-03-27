"use client";

import { useState } from "react";
import { ChevronLeft, ChevronRight, Check, Vote } from "lucide-react";

/* Availability data matching .pen file exactly */
interface DayAvail {
  top?: { count: number; total: number };
  bottom?: { count: number; total: number };
}

const availabilityData: Record<number, DayAvail> = {
  2: { top: { count: 3, total: 5 }, bottom: { count: 3, total: 5 } },
  3: { top: { count: 4, total: 5 }, bottom: { count: 4, total: 5 } },
  4: { top: { count: 5, total: 5 }, bottom: { count: 5, total: 5 } },
  5: { top: { count: 4, total: 5 }, bottom: { count: 4, total: 5 } },
  6: { top: { count: 3, total: 5 }, bottom: { count: 3, total: 5 } },
  9: { top: { count: 2, total: 5 }, bottom: { count: 2, total: 5 } },
  10: { top: { count: 4, total: 5 }, bottom: { count: 3, total: 5 } },
  11: { top: { count: 5, total: 5 }, bottom: { count: 4, total: 5 } },
  12: { top: { count: 5, total: 5 }, bottom: { count: 5, total: 5 } },
  13: { top: { count: 3, total: 5 }, bottom: { count: 3, total: 5 } },
  16: { top: { count: 4, total: 5 }, bottom: { count: 4, total: 5 } },
  17: { top: { count: 5, total: 5 }, bottom: { count: 5, total: 5 } },
  18: { top: { count: 5, total: 5 }, bottom: { count: 3, total: 5 } },
  19: { top: { count: 4, total: 5 }, bottom: { count: 2, total: 5 } },
  20: { top: { count: 3, total: 5 }, bottom: { count: 4, total: 5 } },
  23: { top: { count: 5, total: 5 }, bottom: { count: 5, total: 5 } },
  24: { top: { count: 5, total: 5 }, bottom: { count: 5, total: 5 } },
  25: { top: { count: 4, total: 5 }, bottom: { count: 4, total: 5 } },
  26: { top: { count: 3, total: 5 }, bottom: { count: 3, total: 5 } },
  27: { top: { count: 2, total: 5 }, bottom: { count: 2, total: 5 } },
  30: { top: { count: 4, total: 5 }, bottom: { count: 4, total: 5 } },
  31: { top: { count: 5, total: 5 }, bottom: { count: 3, total: 5 } },
};

function availColor(count: number, total: number): string {
  if (count === total) return "#22c55e";
  if (count >= 4) return "#eab308";
  if (count >= 3) return "#eab308";
  return "#ef4444";
}

/* Highlighted days from .pen */
const highlightedDays = new Set([23, 25]);
const selectedDay = 24;

interface TimeSlot {
  label: string;
  count: string;
  labelColor: string;
  countColor: string;
  avatarColors: string[];
  selected?: boolean;
}

const timeSlots: TimeSlot[] = [
  {
    label: "3월 23일 (월) 오후 3:00 ~ 5:00",
    count: "5/5",
    labelColor: "#166534",
    countColor: "#22c55e",
    avatarColors: ["#c7d2fe", "#93c5fd", "#86efac", "#fca5a5", "#fde68a"],
    selected: true,
  },
  {
    label: "3월 24일 (화) 오후 2:00 ~ 4:00",
    count: "5/5",
    labelColor: "#166534",
    countColor: "#22c55e",
    avatarColors: ["#c7d2fe", "#93c5fd", "#86efac", "#fca5a5", "#fde68a"],
    selected: true,
  },
  {
    label: "3월 25일 (수) 오전 10:00 ~ 12:00",
    count: "4/5",
    labelColor: "#64748b",
    countColor: "#94a3b8",
    avatarColors: ["#c7d2fe", "#93c5fd", "#86efac", "#fca5a5"],
  },
  {
    label: "3월 25일 (수) 오후 7:00 ~ 9:00",
    count: "2/5",
    labelColor: "#64748b",
    countColor: "#94a3b8",
    avatarColors: ["#c7d2fe", "#fca5a5"],
  },
];

export default function CalendarPane() {
  const [selected, setSelected] = useState<Set<number>>(new Set([0, 1]));
  const year = 2026;
  const month = 3;
  const daysInMonth = new Date(year, month, 0).getDate();
  const firstDay = new Date(year, month - 1, 1).getDay();
  const days = Array.from({ length: daysInMonth }, (_, i) => i + 1);
  const blanks = Array.from({ length: firstDay }, (_, i) => i);

  const toggleSlot = (idx: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  return (
    <div
      style={{
        width: 414,
        height: 733,
        borderRadius: 20,
        border: "1px solid #e2e8f0",
        boxShadow: "0 4px 3.5px rgba(0,0,0,0.25)",
        background: "#fff",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        fontFamily: "Pretendard Variable, Pretendard, sans-serif",
      }}
    >
      {/* Header - gray bg matching .pen */}
      <div
        style={{
          background: "#f2f4f7",
          borderRadius: "20px 20px 0 0",
          padding: "16px 20px",
          borderBottom: "1px solid #e2e8f0",
        }}
      >
        <span
          style={{
            fontSize: 26,
            fontWeight: 400,
            color: "#000000",
            letterSpacing: 0.75,
          }}
        >
          캘린더
        </span>
      </div>

      {/* Month nav */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "8px 19px",
          height: 30,
          marginTop: 12,
        }}
      >
        <div
          style={{
            width: 20,
            height: 20,
            borderRadius: 4,
            background: "rgba(100,116,139,0.2)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
          }}
        >
          <ChevronLeft style={{ width: 14, height: 14, color: "#64748b" }} />
        </div>
        <span
          style={{
            fontSize: 16,
            fontWeight: "normal",
            color: "#1e293b",
            fontFamily: "Inter, sans-serif",
          }}
        >
          매듭 {year}년 {month}월
        </span>
        <div
          style={{
            width: 20,
            height: 20,
            borderRadius: 4,
            background: "rgba(100,116,139,0.2)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
          }}
        >
          <ChevronRight style={{ width: 14, height: 14, color: "#64748b" }} />
        </div>
      </div>

      {/* Calendar grid */}
      <div style={{ padding: "0 19px" }}>
        {/* Weekday headers */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(7, 1fr)",
            textAlign: "center",
            marginTop: 8,
          }}
        >
          {["일", "월", "화", "수", "목", "금", "토"].map((d) => (
            <span
              key={d}
              style={{
                fontSize: 12,
                fontWeight: "normal",
                color: "#94a3b8",
                padding: "6px 0",
                width: 50,
              }}
            >
              {d}
            </span>
          ))}
        </div>

        {/* Day cells */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(7, 50px)",
            justifyContent: "space-between",
          }}
        >
          {blanks.map((b) => (
            <div key={`b-${b}`} style={{ height: 52 }} />
          ))}
          {days.map((day) => {
            const isSelected = day === selectedDay;
            const isHighlighted = highlightedDays.has(day);
            const avail = availabilityData[day];
            return (
              <div
                key={day}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  height: 52,
                  width: 50,
                  borderRadius: isSelected || isHighlighted ? 8 : 0,
                  cursor: "pointer",
                  background: isSelected
                    ? "#4f46e5"
                    : isHighlighted
                      ? "#e0e7ff"
                      : "transparent",
                }}
              >
                <span
                  style={{
                    fontSize: 13,
                    fontWeight: "normal",
                    color: isSelected ? "#ffffff" : "#334155",
                    lineHeight: 1.4,
                  }}
                >
                  {day}
                </span>
                {avail?.top && (
                  <span
                    style={{
                      fontSize: 9,
                      fontWeight: "normal",
                      color: isSelected && avail.top.count === avail.top.total
                        ? "#22c55e"
                        : availColor(avail.top.count, avail.top.total),
                      lineHeight: 1.2,
                      fontFamily: "Inter, sans-serif",
                    }}
                  >
                    {avail.top.count}/{avail.top.total}
                  </span>
                )}
                {avail?.bottom && (
                  <span
                    style={{
                      fontSize: 9,
                      fontWeight: "normal",
                      color: isSelected
                        ? "#ffffff"
                        : availColor(avail.bottom.count, avail.bottom.total),
                      lineHeight: 1.2,
                      fontFamily: "Inter, sans-serif",
                    }}
                  >
                    {avail.bottom.count}/{avail.bottom.total}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Divider */}
      <div
        style={{
          height: 1,
          background: "#e2e8f0",
          margin: "8px 19px 0",
        }}
      />

      {/* Bottom section */}
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          padding: "10px 19px 19px",
          overflow: "hidden",
        }}
      >
        <span
          style={{
            fontSize: 15,
            fontWeight: "normal",
            color: "#1e293b",
            fontFamily: "Inter, sans-serif",
          }}
        >
          모두가 가능한 시간대
        </span>
        <span
          style={{
            fontSize: 11,
            fontWeight: "normal",
            color: "#94a3b8",
            marginTop: 2,
            marginBottom: 8,
          }}
        >
          3월 23일 ~ 25일 기준
        </span>

        {/* Time slots */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 4,
          }}
        >
          {timeSlots.map((slot, idx) => {
            const isChecked = selected.has(idx);
            const isActive = slot.selected;
            return (
              <div
                key={idx}
                onClick={() => toggleSlot(idx)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "0 12px",
                  height: 38,
                  borderRadius: 12,
                  background: isActive ? "#f0fdf4" : "#f8fafc",
                  border: isActive
                    ? "1.5px solid #22c55e"
                    : "1px solid #cbd5e1",
                  cursor: "pointer",
                  boxShadow: isActive
                    ? "0 1px 3.5px rgba(79, 70, 229, 0.13)"
                    : "none",
                }}
              >
                {/* Checkbox */}
                <div
                  style={{
                    width: 20,
                    height: 20,
                    borderRadius: 4,
                    background: isChecked ? "#4f46e5" : "#ffffff",
                    border: isChecked
                      ? "none"
                      : "1.5px solid #cbd5e1",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}
                >
                  {isChecked && (
                    <Check
                      style={{ width: 14, height: 14, color: "#ffffff" }}
                    />
                  )}
                </div>
                {/* Label */}
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: "normal",
                    color: slot.labelColor,
                    fontFamily: "Inter, sans-serif",
                    whiteSpace: "nowrap",
                  }}
                >
                  {slot.label}
                </span>
                {/* Spacer */}
                <div style={{ flex: 1 }} />
                {/* Count */}
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: "normal",
                    color: slot.countColor,
                    fontFamily: "Inter, sans-serif",
                  }}
                >
                  {slot.count}
                </span>
                {/* Avatar circles */}
                <div
                  style={{
                    display: "flex",
                    marginLeft: 4,
                  }}
                >
                  {slot.avatarColors.map((color, i) => (
                    <div
                      key={i}
                      style={{
                        width: 18,
                        height: 18,
                        borderRadius: "50%",
                        background: color,
                        marginLeft: i > 0 ? -6 : 0,
                      }}
                    />
                  ))}
                </div>
              </div>
            );
          })}
        </div>

        {/* Selection count */}
        <div style={{ marginTop: 8 }}>
          <span
            style={{
              fontSize: 12,
              fontWeight: "normal",
              color: "#4f46e5",
            }}
          >
            {selected.size}개 선택됨
          </span>
        </div>

        {/* Submit button */}
        <div style={{ marginTop: "auto" }}>
          <button
            style={{
              width: "100%",
              height: 40,
              background: "#4f46e5",
              color: "#ffffff",
              fontSize: 14,
              fontWeight: "normal",
              borderRadius: 12,
              border: "none",
              cursor: "pointer",
              fontFamily: "Inter, sans-serif",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 8,
            }}
          >
            <Vote style={{ width: 18, height: 18, color: "#ffffff" }} />
            투표 제출
          </button>
        </div>
      </div>
    </div>
  );
}
