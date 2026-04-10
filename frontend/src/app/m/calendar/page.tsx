"use client";

import { useRouter } from "next/navigation";
import {
  Bell,
  User,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import MobileTabBar from "@/components/ui/MobileTabBar";

const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];

const EVENTS: Record<number, { label: string; bg: string; color: string }> = {
  7: { label: "회의", bg: "#818cf820", color: "#4f46e5" },
  10: { label: "팀회의", bg: "#4f46e520", color: "#4f46e5" },
  15: { label: "등산", bg: "#22c55e20", color: "#16a34a" },
  23: { label: "졸프", bg: "#f59e0b20", color: "#d97706" },
};

const TODAY = 7;

// April 2026 starts on Wednesday (index 3)
const CALENDAR_ROWS = [
  [0, 0, 0, 1, 2, 3, 4],
  [5, 6, 7, 8, 9, 10, 11],
  [12, 13, 14, 15, 16, 17, 18],
  [19, 20, 21, 22, 23, 24, 25],
  [26, 27, 28, 29, 30, 0, 0],
];

function getDayColor(day: number, colIndex: number): string {
  if (day === TODAY) return "#ffffff";
  if (colIndex === 0) return "#ef4444";
  if (colIndex === 6) return "#3b82f6";
  return "#374151";
}


const UPCOMING = [
  {
    barColor: "#4f46e5",
    title: "팀 프로젝트 회의",
    date: "4월 10일 (금) 오후 3:00",
    place: "강남역 스터디룸",
  },
  {
    barColor: "#22c55e",
    title: "주말 등산 모임",
    date: "4월 15일 (수) 오전 9:00",
    place: "북한산 입구",
  },
];

export default function CalendarPage() {
  const router = useRouter();
  return (
    <div
      style={{
        width: 390,
        height: 844,
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        background: "#f8fafc",
        fontFamily: "Pretendard, sans-serif",
        margin: "0 auto",
      }}
    >
      {/* Header */}
      <div
        style={{
          height: 56,
          minHeight: 56,
          background: "#4f46e5",
          padding: "0 20px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <span
          style={{
            fontFamily: "Pretendard, sans-serif",
            fontSize: 20,
            fontWeight: 700,
            color: "#ffffff",
          }}
        >
          매듭
        </span>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <Bell size={22} color="#ffffff" strokeWidth={2} style={{ cursor: "pointer" }} onClick={() => router.push("/m/notifications")} />
          <User size={22} color="#ffffff" strokeWidth={2} style={{ cursor: "pointer" }} onClick={() => router.push("/m/profile")} />
        </div>
      </div>

      {/* Content */}
      <div
        style={{
          flex: 1,
          padding: 20,
          display: "flex",
          flexDirection: "column",
          gap: 20,
          overflowY: "auto",
        }}
      >
        {/* Month nav */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <ChevronLeft size={20} color="#64748b" strokeWidth={2} style={{ cursor: "pointer" }} />
          <span
            style={{
              fontFamily: "Pretendard, sans-serif",
              fontSize: 18,
              fontWeight: 700,
              color: "#1e293b",
            }}
          >
            2026년 4월
          </span>
          <ChevronRight size={20} color="#64748b" strokeWidth={2} style={{ cursor: "pointer" }} />
        </div>

        {/* Weekday row */}
        <div style={{ display: "flex" }}>
          {WEEKDAYS.map((d, i) => (
            <div
              key={d}
              style={{
                flex: 1,
                textAlign: "center",
                fontFamily: "Pretendard, sans-serif",
                fontSize: 12,
                fontWeight: 600,
                color:
                  i === 0 ? "#ef4444" : i === 6 ? "#3b82f6" : "#64748b",
              }}
            >
              {d}
            </div>
          ))}
        </div>

        {/* Calendar grid */}
        <div
          style={{
            borderRadius: 16,
            background: "#ffffff",
            border: "1px solid #e5e7eb",
            padding: "12px 8px",
            display: "flex",
            flexDirection: "column",
            gap: 1,
          }}
        >
          {CALENDAR_ROWS.map((row, rowIdx) => (
            <div key={rowIdx} style={{ display: "flex" }}>
              {row.map((day, colIdx) => {
                const isToday = day === TODAY;
                const event = day > 0 ? EVENTS[day] : undefined;
                return (
                  <div
                    key={colIdx}
                    style={{
                      flex: 1,
                      height: 62,
                      padding: "4px 3px",
                      display: "flex",
                      flexDirection: "column",
                      gap: 2,
                      ...(isToday
                        ? {
                            background: "#4f46e5",
                            borderRadius: 8,
                          }
                        : {}),
                    }}
                  >
                    {day > 0 && (
                      <>
                        <span
                          style={{
                            fontFamily: "Pretendard, sans-serif",
                            fontSize: 12,
                            fontWeight: 500,
                            color: getDayColor(day, colIdx),
                            textAlign: "center",
                          }}
                        >
                          {day}
                        </span>
                        {event && (
                          <div
                            style={{
                              borderRadius: 4,
                              padding: "1px 4px",
                              fontFamily: "Pretendard, sans-serif",
                              fontSize: 9,
                              fontWeight: 500,
                              background: event.bg,
                              color: event.color,
                              whiteSpace: "nowrap",
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                            }}
                          >
                            {event.label}
                          </div>
                        )}
                      </>
                    )}
                  </div>
                );
              })}
            </div>
          ))}
        </div>

        {/* Upcoming meetings */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <span
            style={{
              fontFamily: "Pretendard, sans-serif",
              fontSize: 16,
              fontWeight: 700,
              color: "#1e293b",
            }}
          >
            다가오는 모임
          </span>

          {UPCOMING.map((item, idx) => (
            <div
              key={idx}
              onClick={() => router.push("/m/meeting/detail")}
              style={{
                borderRadius: 12,
                background: "#ffffff",
                border: "1px solid #e5e7eb",
                padding: 14,
                display: "flex",
                alignItems: "center",
                gap: 8,
                cursor: "pointer",
              }}
            >
              {/* Left bar */}
              <div
                style={{
                  width: 4,
                  alignSelf: "stretch",
                  borderRadius: 2,
                  background: item.barColor,
                }}
              />
              {/* Info */}
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 2,
                }}
              >
                <span
                  style={{
                    fontFamily: "Pretendard, sans-serif",
                    fontSize: 14,
                    fontWeight: 600,
                    color: "#1e293b",
                  }}
                >
                  {item.title}
                </span>
                <span
                  style={{
                    fontFamily: "Pretendard, sans-serif",
                    fontSize: 12,
                    fontWeight: 400,
                    color: "#64748b",
                  }}
                >
                  {item.date}
                </span>
                <span
                  style={{
                    fontFamily: "Pretendard, sans-serif",
                    fontSize: 11,
                    fontWeight: 400,
                    color: "#94a3b8",
                  }}
                >
                  {item.place}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Tab bar */}
      <MobileTabBar active="캘린더" />
    </div>
  );
}
