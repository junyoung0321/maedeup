"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Bell, User, ChevronLeft, ChevronRight } from "lucide-react";
import MobileTabBar from "@/components/ui/MobileTabBar";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";

interface MeetingListItem {
  id: number;
  room_id: number;
  title: string;
  scheduled_at: string;
  end_at?: string | null;
  location_name?: string | null;
}

const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];
const BAR_COLORS = ["#4f46e5", "#22c55e", "#f59e0b", "#ec4899", "#06b6d4", "#8b5cf6"];
const EVENT_COLORS = [
  { bg: "#4f46e520", color: "#4f46e5" },
  { bg: "#22c55e20", color: "#16a34a" },
  { bg: "#f59e0b20", color: "#d97706" },
  { bg: "#ec489920", color: "#be185d" },
  { bg: "#06b6d420", color: "#0891b2" },
  { bg: "#8b5cf620", color: "#7c3aed" },
];

function buildCalendarRows(year: number, month: number) {
  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const rows: number[][] = [];
  let day = 1 - firstDay;
  while (day <= daysInMonth) {
    const row: number[] = [];
    for (let col = 0; col < 7; col++, day++) {
      row.push(day > 0 && day <= daysInMonth ? day : 0);
    }
    rows.push(row);
  }
  return rows;
}

function formatUpcomingDate(iso: string) {
  const d = new Date(iso);
  const days = ["일", "월", "화", "수", "목", "금", "토"];
  const month = d.getMonth() + 1;
  const day = d.getDate();
  const dow = days[d.getDay()];
  const h = d.getHours();
  const m = d.getMinutes();
  const period = h < 12 ? "오전" : "오후";
  const hh = h % 12 || 12;
  return `${month}월 ${day}일 (${dow}) ${period} ${hh}:${String(m).padStart(2, "0")}`;
}

export default function CalendarPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [meetings, setMeetings] = useState<MeetingListItem[]>([]);

  const now = new Date();
  const [viewYear, setViewYear] = useState(now.getFullYear());
  const [viewMonth, setViewMonth] = useState(now.getMonth());

  const todayDay =
    now.getMonth() === viewMonth && now.getFullYear() === viewYear
      ? now.getDate()
      : -1;

  useEffect(() => {
    if (authLoading || !user) return;
    apiFetch<MeetingListItem[]>("/api/v1/meetings/")
      .then(setMeetings)
      .catch(() => null);
  }, [authLoading, user]);

  function prevMonth() {
    if (viewMonth === 0) { setViewYear(y => y - 1); setViewMonth(11); }
    else setViewMonth(m => m - 1);
  }

  function nextMonth() {
    if (viewMonth === 11) { setViewYear(y => y + 1); setViewMonth(0); }
    else setViewMonth(m => m + 1);
  }

  const rows = buildCalendarRows(viewYear, viewMonth);

  const eventsByDay: Record<number, { label: string; colorIdx: number }> = {};
  meetings.forEach((m, i) => {
    const d = new Date(m.scheduled_at);
    if (d.getFullYear() === viewYear && d.getMonth() === viewMonth) {
      const day = d.getDate();
      if (!eventsByDay[day]) {
        const label = m.title.length > 4 ? m.title.slice(0, 4) : m.title;
        eventsByDay[day] = { label, colorIdx: i % EVENT_COLORS.length };
      }
    }
  });

  const upcoming = meetings
    .filter(m => new Date(m.scheduled_at) >= now)
    .sort((a, b) => new Date(a.scheduled_at).getTime() - new Date(b.scheduled_at).getTime())
    .slice(0, 5);

  return (
    <div
      style={{
        width: "100%",
        height: "844px",
        display: "flex",
        flexDirection: "column",
        background: "#f8fafc",
        fontFamily: "Pretendard, sans-serif",
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
        <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 20, fontWeight: 700, color: "#ffffff" }}>매듭</span>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <Bell size={22} color="#ffffff" strokeWidth={2} style={{ cursor: "pointer" }} onClick={() => router.push("/m/notifications")} />
          <User size={22} color="#ffffff" strokeWidth={2} style={{ cursor: "pointer" }} onClick={() => router.push("/m/profile")} />
        </div>
      </div>

      {/* Content */}
      <div style={{ flex: 1, padding: 20, display: "flex", flexDirection: "column", gap: 20, overflowY: "auto" }}>
        {/* Month nav */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <ChevronLeft size={20} color="#64748b" strokeWidth={2} style={{ cursor: "pointer" }} onClick={prevMonth} />
          <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 18, fontWeight: 700, color: "#1e293b" }}>
            {viewYear}년 {viewMonth + 1}월
          </span>
          <ChevronRight size={20} color="#64748b" strokeWidth={2} style={{ cursor: "pointer" }} onClick={nextMonth} />
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
                color: i === 0 ? "#ef4444" : i === 6 ? "#3b82f6" : "#64748b",
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
          {rows.map((row, rowIdx) => (
            <div key={rowIdx} style={{ display: "flex" }}>
              {row.map((day, colIdx) => {
                const isToday = day === todayDay;
                const ev = day > 0 ? eventsByDay[day] : undefined;
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
                      ...(isToday ? { background: "#4f46e5", borderRadius: 8 } : {}),
                    }}
                  >
                    {day > 0 && (
                      <>
                        <span
                          style={{
                            fontFamily: "Pretendard, sans-serif",
                            fontSize: 12,
                            fontWeight: 500,
                            textAlign: "center",
                            color: isToday
                              ? "#ffffff"
                              : colIdx === 0
                              ? "#ef4444"
                              : colIdx === 6
                              ? "#3b82f6"
                              : "#374151",
                          }}
                        >
                          {day}
                        </span>
                        {ev && (
                          <div
                            style={{
                              borderRadius: 4,
                              padding: "1px 4px",
                              fontFamily: "Pretendard, sans-serif",
                              fontSize: 9,
                              fontWeight: 500,
                              background: EVENT_COLORS[ev.colorIdx].bg,
                              color: EVENT_COLORS[ev.colorIdx].color,
                              whiteSpace: "nowrap",
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                            }}
                          >
                            {ev.label}
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
          <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 16, fontWeight: 700, color: "#1e293b" }}>
            다가오는 모임
          </span>
          {upcoming.length === 0 ? (
            <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 13, color: "#94a3b8" }}>
              예정된 모임이 없습니다
            </span>
          ) : (
            upcoming.map((item, idx) => (
              <div
                key={item.id}
                onClick={() => router.push(`/m/meeting/detail?roomId=${item.room_id}`)}
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
                <div style={{ width: 4, alignSelf: "stretch", borderRadius: 2, background: BAR_COLORS[idx % BAR_COLORS.length] }} />
                <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 14, fontWeight: 600, color: "#1e293b" }}>
                    {item.title}
                  </span>
                  <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 12, fontWeight: 400, color: "#64748b" }}>
                    {formatUpcomingDate(item.scheduled_at)}
                  </span>
                  {item.location_name && (
                    <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 11, fontWeight: 400, color: "#94a3b8" }}>
                      {item.location_name}
                    </span>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Tab bar */}
      <MobileTabBar active="캘린더" />
    </div>
  );
}
