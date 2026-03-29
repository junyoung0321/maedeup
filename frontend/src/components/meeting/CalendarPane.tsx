"use client";

import { useState, useEffect } from "react";
import { ChevronLeft, ChevronRight, Check, Vote } from "lucide-react";
import { API_BASE_URL } from "@/lib/api";

/* ── Types ─────────────────────────────────────────────── */
interface DayAvail {
  count: number;
  total: number;
  available: string[];
  busy: string[];
  unconnected: string[];
}

interface TimeSlot {
  label: string;
  count: string;
  labelColor: string;
  countColor: string;
  avatarColors: string[];
  selected?: boolean;
}

interface ApiFreeSlot {
  label: string;
  available_count: number;
  total_count: number;
  is_recommended?: boolean;
}

interface CalendarApiResponse {
  dates: Record<string, DayAvail>; // key: "YYYY-MM-DD"
  free_slots: ApiFreeSlot[];
}

/* ── Helpers ────────────────────────────────────────────── */
const AVATAR_PALETTE = [
  "#c7d2fe", "#93c5fd", "#86efac", "#fca5a5", "#fde68a", "#fbcfe8", "#a5f3fc",
];

function availColor(count: number, total: number): string {
  if (count === total) return "#22c55e";
  if (count > 0) return "#eab308";
  return "#ef4444";
}

function getToken(): string | null {
  try {
    return localStorage.getItem("auth_token");
  } catch {
    return null;
  }
}

function mapFreeSlot(slot: ApiFreeSlot): TimeSlot {
  const isFull = slot.available_count === slot.total_count;
  return {
    label: slot.label,
    count: `${slot.available_count}/${slot.total_count}`,
    labelColor: isFull ? "#166534" : "#64748b",
    countColor: isFull ? "#22c55e" : "#94a3b8",
    avatarColors: AVATAR_PALETTE.slice(0, slot.available_count),
    selected: slot.is_recommended,
  };
}

/* ── Component ──────────────────────────────────────────── */
export default function CalendarPane() {
  const [selected, setSelected] = useState<Set<number>>(new Set([0, 1]));
  const [availabilityData, setAvailabilityData] = useState<Record<number, DayAvail>>({});
  const [timeSlots, setTimeSlots] = useState<TimeSlot[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [year, setYear] = useState(new Date().getFullYear());
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  const [dateRangeLabel, setDateRangeLabel] = useState<string>("");
  const [clickedDay, setClickedDay] = useState<number | null>(null);

  const daysInMonth = new Date(year, month, 0).getDate();
  const firstDay = new Date(year, month - 1, 1).getDay();
  const days = Array.from({ length: daysInMonth }, (_, i) => i + 1);
  const blanks = Array.from({ length: firstDay }, (_, i) => i);

  const highlightedDays = new Set(
    Object.entries(availabilityData)
      .filter(([, avail]) => avail.count > 0)
      .map(([day]) => Number(day))
  );

  const goPrev = () => {
    setClickedDay(null);
    if (month === 1) { setYear((y) => y - 1); setMonth(12); }
    else setMonth((m) => m - 1);
  };
  const goNext = () => {
    setClickedDay(null);
    if (month === 12) { setYear((y) => y + 1); setMonth(1); }
    else setMonth((m) => m + 1);
  };

  useEffect(() => {
    setLoading(true);
    setError(false);
    setAvailabilityData({});
    setTimeSlots([]);

    const token = getToken();
    fetch(`${API_BASE_URL}/api/v1/calendar/free-slots?room_id=room-1&year=${year}&month=${month}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((res) => {
        if (!res.ok) throw new Error();
        return res.json() as Promise<CalendarApiResponse>;
      })
      .then((data) => {
        const dayMap: Record<number, DayAvail> = {};
        for (const [dateStr, avail] of Object.entries(data.dates)) {
          const day = parseInt(dateStr.split("-")[2], 10);
          dayMap[day] = {
            count: avail.count,
            total: avail.total,
            available: avail.available ?? [],
            busy: avail.busy ?? [],
            unconnected: avail.unconnected ?? [],
          };
        }
        setAvailabilityData(dayMap);
        setTimeSlots(data.free_slots.map(mapFreeSlot));

        const dateKeys = Object.keys(data.dates).sort();
        if (dateKeys.length >= 2) {
          const d1 = parseInt(dateKeys[0].split("-")[2], 10);
          const d2 = parseInt(dateKeys[dateKeys.length - 1].split("-")[2], 10);
          setDateRangeLabel(`${month}월 ${d1}일 ~ ${d2}일 기준`);
        } else if (dateKeys.length === 1) {
          setDateRangeLabel(`${month}월 ${parseInt(dateKeys[0].split("-")[2], 10)}일 기준`);
        } else {
          setDateRangeLabel(`${month}월 기준`);
        }

        setLoading(false);
      })
      .catch(() => {
        setError(true);
        setDateRangeLabel(`${month}월 기준`);
        setLoading(false);
      });
  }, [year, month]);

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
        minHeight: 733,
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
      {/* Header */}
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
          onClick={goPrev}
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
          onClick={goNext}
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
            const isHighlighted = highlightedDays.has(day);
            const avail = availabilityData[day];
            const todayDate = new Date();
            const isToday =
              year === todayDate.getFullYear() &&
              month === todayDate.getMonth() + 1 &&
              day === todayDate.getDate();
            const isClicked = day === clickedDay;
            return (
              <div
                key={day}
                onClick={() => setClickedDay(isClicked ? null : day)}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  height: 52,
                  width: 50,
                  borderRadius: isHighlighted || isToday || isClicked ? 8 : 0,
                  cursor: "pointer",
                  background: isHighlighted ? "#e0e7ff" : "transparent",
                  border: isToday || isClicked ? "2px solid #4f46e5" : undefined,
                }}
              >
                <span
                  style={{
                    fontSize: 13,
                    fontWeight: "normal",
                    color: "#334155",
                    lineHeight: 1.4,
                  }}
                >
                  {day}
                </span>
                {avail && (
                  <span
                    style={{
                      fontSize: 9,
                      fontWeight: "normal",
                      color: availColor(avail.count, avail.total),
                      lineHeight: 1.2,
                      fontFamily: "Inter, sans-serif",
                    }}
                  >
                    {avail.count}/{avail.total}
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
        {/* 날짜 클릭 시 멤버 현황 */}
        {clickedDay !== null && (
          <div
            style={{
              marginBottom: 10,
              padding: "10px 12px",
              borderRadius: 10,
              background: "#f8fafc",
              border: "1px solid #e2e8f0",
            }}
          >
            <span
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: "#1e293b",
                display: "block",
                marginBottom: 6,
                fontFamily: "Inter, sans-serif",
              }}
            >
              {month}월 {clickedDay}일 멤버 현황
            </span>
            {(availabilityData[clickedDay]?.available ?? []).length > 0 && (
              <div style={{ display: "flex", gap: 4, marginBottom: 3, flexWrap: "wrap" }}>
                <span style={{ fontSize: 11, color: "#94a3b8" }}>✅</span>
                <span style={{ fontSize: 11, color: "#16a34a", fontFamily: "Inter, sans-serif" }}>
                  {availabilityData[clickedDay]!.available!.join(", ")}
                </span>
              </div>
            )}
            {(availabilityData[clickedDay]?.busy ?? []).length > 0 && (
              <div style={{ display: "flex", gap: 4, marginBottom: 3, flexWrap: "wrap" }}>
                <span style={{ fontSize: 11, color: "#94a3b8" }}>❌</span>
                <span style={{ fontSize: 11, color: "#ef4444", fontFamily: "Inter, sans-serif" }}>
                  {availabilityData[clickedDay]!.busy!.join(", ")}
                </span>
              </div>
            )}
            {(availabilityData[clickedDay]?.unconnected ?? []).length > 0 && (
              <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                <span style={{ fontSize: 11, color: "#94a3b8" }}>🔗</span>
                <span style={{ fontSize: 11, color: "#94a3b8", fontFamily: "Inter, sans-serif" }}>
                  {availabilityData[clickedDay]!.unconnected!.join(", ")}
                </span>
              </div>
            )}
            {(availabilityData[clickedDay]?.available ?? []).length === 0 &&
              (availabilityData[clickedDay]?.busy ?? []).length === 0 &&
              (availabilityData[clickedDay]?.unconnected ?? []).length === 0 && (
              <span style={{ fontSize: 11, color: "#94a3b8", fontFamily: "Inter, sans-serif" }}>
                멤버 정보 없음
              </span>
            )}
          </div>
        )}

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
          {dateRangeLabel}
        </span>

        {/* Loading / Error / Time slots */}
        {loading ? (
          <div
            style={{
              flex: 1,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#94a3b8",
              fontSize: 13,
            }}
          >
            불러오는 중...
          </div>
        ) : error ? (
          <div
            style={{
              flex: 1,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#ef4444",
              fontSize: 13,
            }}
          >
            캘린더 데이터를 불러올 수 없습니다
          </div>
        ) : (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 4,
              overflowY: "auto",
              maxHeight: 180,
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
                      border: isChecked ? "none" : "1.5px solid #cbd5e1",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                    }}
                  >
                    {isChecked && (
                      <Check style={{ width: 14, height: 14, color: "#ffffff" }} />
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
                  <div style={{ display: "flex", marginLeft: 4 }}>
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
        )}

        {/* Selection count */}
        {!loading && !error && (
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
        )}

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
