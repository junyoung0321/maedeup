"use client";

import { useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { apiFetch } from "@/lib/api";

interface EventRead {
  id: number;
  title: string;
  starts_at: string;
}

interface MyCalendarEvent {
  id: string;
  title: string;
  starts_at: string;
  ends_at: string;
  all_day: boolean;
}

interface MyCalendarResponse {
  events: MyCalendarEvent[];
  connected: boolean;
}

type EventSource = "app" | "google";

interface CalendarEvent {
  id: string;
  title: string;
  date: string;
  color: string;
  source: EventSource;
}

const EVENT_PALETTE = [
  "#4f46e5", "#7c3aed", "#0891b2", "#059669",
  "#ea580c", "#dc2626", "#16a34a", "#db2777",
];

function colorForTitle(title: string): string {
  let hash = 0;
  for (let i = 0; i < title.length; i++) {
    hash = (hash * 31 + title.charCodeAt(i)) >>> 0;
  }
  return EVENT_PALETTE[hash % EVENT_PALETTE.length];
}

function toLocalDateString(iso: string): string {
  const d = new Date(iso);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export default function MiniCalendar() {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [appEvents, setAppEvents] = useState<CalendarEvent[]>([]);
  const [gcalEvents, setGcalEvents] = useState<CalendarEvent[]>([]);
  const [gcalConnected, setGcalConnected] = useState<boolean | null>(null);

  // App events: fetched once
  useEffect(() => {
    apiFetch<EventRead[]>("/api/v1/events/")
      .then((data) => {
        setAppEvents(
          data.map((ev) => ({
            id: `app-${ev.id}`,
            title: ev.title,
            date: toLocalDateString(ev.starts_at),
            color: colorForTitle(ev.title),
            source: "app",
          })),
        );
      })
      .catch(() => setAppEvents([]));
  }, []);

  // Google Calendar events: refetch on month change
  useEffect(() => {
    apiFetch<MyCalendarResponse>(`/api/v1/calendar/my-events?year=${year}&month=${month}`)
      .then((res) => {
        setGcalConnected(res.connected);
        setGcalEvents(
          res.events.map((ev) => ({
            id: `gcal-${ev.id}`,
            title: ev.title,
            date: toLocalDateString(ev.starts_at),
            color: colorForTitle(ev.title),
            source: "google",
          })),
        );
      })
      .catch(() => {
        setGcalConnected(false);
        setGcalEvents([]);
      });
  }, [year, month]);

  const events = useMemo(() => [...appEvents, ...gcalEvents], [appEvents, gcalEvents]);

  const daysInMonth = new Date(year, month, 0).getDate();
  const firstDay = new Date(year, month - 1, 1).getDay();
  const days = Array.from({ length: daysInMonth }, (_, i) => i + 1);

  const todayYear = now.getFullYear();
  const todayMonth = now.getMonth() + 1;
  const todayDay = now.getDate();
  const today = year === todayYear && month === todayMonth ? todayDay : -1;

  const goPrev = () => {
    if (month === 1) { setYear((y) => y - 1); setMonth(12); }
    else setMonth((m) => m - 1);
  };
  const goNext = () => {
    if (month === 12) { setYear((y) => y + 1); setMonth(1); }
    else setMonth((m) => m + 1);
  };

  const prevMonthDays = new Date(year, month - 1, 0).getDate();
  const prevDays = Array.from(
    { length: firstDay },
    (_, i) => prevMonthDays - firstDay + 1 + i
  );

  const totalCells = firstDay + daysInMonth;
  const nextDaysCount = totalCells % 7 === 0 ? 0 : 7 - (totalCells % 7);
  const nextDays = Array.from({ length: nextDaysCount }, (_, i) => i + 1);

  const eventsByDay = useMemo(() => {
    const map: Record<number, { title: string; color: string }[]> = {};
    events.forEach((ev) => {
      const [evYear, evMonth, evDayStr] = ev.date.split("-");
      if (Number(evYear) === year && Number(evMonth) === month) {
        const d = parseInt(evDayStr, 10);
        if (!map[d]) map[d] = [];
        map[d].push({ title: ev.title, color: ev.color });
      }
    });
    return map;
  }, [events, year, month]);

  const weekdays = ["일", "월", "화", "수", "목", "금", "토"];

  const getWeekdayColor = (idx: number) => {
    if (idx === 0) return "#ef4444";
    if (idx === 6) return "#3b82f6";
    return "#94a3b8";
  };

  const getDayColor = (day: number) => {
    const dow = (firstDay + day - 1) % 7;
    if (dow === 0) return "#ef4444";
    if (dow === 6) return "#3b82f6";
    return "#1e293b";
  };

  // Build rows of 7 cells
  const allCells: { type: "prev" | "current" | "next"; day: number }[] = [];
  prevDays.forEach((d) => allCells.push({ type: "prev", day: d }));
  days.forEach((d) => allCells.push({ type: "current", day: d }));
  nextDays.forEach((d) => allCells.push({ type: "next", day: d }));

  const rows: typeof allCells[] = [];
  for (let i = 0; i < allCells.length; i += 7) {
    rows.push(allCells.slice(i, i + 7));
  }

  return (
    <div
      className="bg-white rounded-[20px] flex flex-col border border-[#e2e8f0] shadow-[0_4px_3px_rgba(0,0,0,0.25)]"
      style={{ height: 620 }}
    >
      {/* Month navigation */}
      <div className="flex items-center justify-between px-5 py-4">
        <button onClick={goPrev} className="p-1 hover:bg-[#f1f5f9] rounded-lg transition-colors">
          <ChevronLeft className="w-5 h-5 text-[#64748b]" />
        </button>
        <span className="text-[20px] font-bold text-[#1e293b]">
          {year}년 {month}월
        </span>
        <button onClick={goNext} className="p-1 hover:bg-[#f1f5f9] rounded-lg transition-colors">
          <ChevronRight className="w-5 h-5 text-[#64748b]" />
        </button>
      </div>

      {/* Weekday header */}
      <div className="grid grid-cols-7 text-center px-4 pb-1">
        {weekdays.map((d, i) => (
          <span
            key={d}
            className="text-[13px] font-semibold py-2"
            style={{ color: getWeekdayColor(i) }}
          >
            {d}
          </span>
        ))}
      </div>

      {/* Calendar grid - rows with equal height */}
      <div className="flex flex-col flex-1 px-3 pb-4">
        {rows.map((row, rowIdx) => (
          <div key={rowIdx} className="grid grid-cols-7 flex-1">
            {row.map((cell, colIdx) => {
              const isToday = cell.type === "current" && cell.day === today;
              const events = cell.type === "current" ? eventsByDay[cell.day] : undefined;
              const isPrevNext = cell.type !== "current";

              return (
                <div
                  key={`${rowIdx}-${colIdx}`}
                  className={`flex flex-col items-center pt-2 cursor-pointer ${
                    isToday ? "bg-[#ede9fe] rounded-lg" : ""
                  }`}
                >
                  <span
                    className={`text-[14px] ${
                      isToday
                        ? "text-[#4f46e5] font-bold"
                        : isPrevNext
                        ? "text-[#cbd5e1] font-medium"
                        : "font-medium"
                    }`}
                    style={
                      !isToday && !isPrevNext
                        ? { color: getDayColor(cell.day) }
                        : undefined
                    }
                  >
                    {cell.day}
                  </span>
                  {events && (
                    <div className="flex flex-col items-center mt-1 w-full">
                      {events.slice(0, 2).map((ev, i) => (
                        <span
                          key={i}
                          className="text-[11px] font-semibold truncate max-w-full leading-tight"
                          style={{ color: ev.color }}
                        >
                          {ev.title}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
