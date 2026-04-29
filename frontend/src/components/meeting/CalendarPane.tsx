"use client";

import { useEffect, useMemo, useState } from "react";
import { Ban, ChevronLeft, ChevronRight } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { useMeetingOptional } from "@/contexts/MeetingContext";
import MiniTimeBar from "@/components/meeting/MiniTimeBar";
import { fs } from "@/lib/responsive";

function getCurrentUserIdFromToken(): number | null {
  if (typeof window === "undefined") return null;
  const token = localStorage.getItem("auth_token");
  if (!token) return null;
  try {
    const payloadPart = token.split(".")[1];
    if (!payloadPart) return null;
    const normalized = payloadPart.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
    const decoded = JSON.parse(atob(padded));
    if (decoded?.sub) {
      const asNum = Number(decoded.sub);
      if (Number.isFinite(asNum)) return asNum;
    }
  } catch {
    /* ignore */
  }
  return null;
}

/* ── Types ─────────────────────────────────────────────── */
interface DayAvail {
  count: number;
  total: number;
  available: string[];
  busy: string[];
  unconnected: string[];
}

interface CalendarApiResponse {
  dates: Record<string, DayAvail>;
}

/* ── Helpers ────────────────────────────────────────────── */

function availColor(count: number, total: number): string {
  if (count === total) return "#22c55e";
  if (count > 0) return "#eab308";
  return "#ef4444";
}

/* ── Component ──────────────────────────────────────────── */
export default function CalendarPane() {
  const meeting = useMeetingOptional();
  const roomId = meeting?.roomId || "room-1";
  const calendarRefreshTrigger = meeting?.calendarRefreshTrigger ?? 0;
  const aiHighlightedDates = meeting?.highlightedDates ?? [];
  const setInfoPanePhase = meeting?.setInfoPanePhase;
  const confirmDate = meeting?.confirmDate;
  const infoPanePhase = meeting?.infoPanePhase;
  const candidateSlots = meeting?.candidateSlots ?? [];
  const peerDateSelections = meeting?.peerDateSelections ?? {};
  const sendDateSelection = meeting?.sendDateSelection ?? null;
  const unavailabilityByUser = meeting?.unavailabilityByUser ?? {};
  const sendUnavailableToggle = meeting?.sendUnavailableToggle ?? null;
  const currentUserId = useMemo(() => getCurrentUserIdFromToken(), []);
  const [availabilityData, setAvailabilityData] = useState<Record<number, DayAvail>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [year, setYear] = useState(new Date().getFullYear());
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  const [clickedDay, setClickedDay] = useState<number | null>(null);
  const [blockMode, setBlockMode] = useState(false);

  // 날짜 문자열 → 그 날 불가능 처리한 user_id 수. 내 것도 포함.
  const unavailableCountByDate: Record<string, number> = {};
  const myUnavailableDates = new Set<string>();
  for (const [uidStr, dates] of Object.entries(unavailabilityByUser)) {
    const uid = Number(uidStr);
    for (const d of dates) {
      unavailableCountByDate[d] = (unavailableCountByDate[d] ?? 0) + 1;
      if (uid === currentUserId) myUnavailableDates.add(d);
    }
  }

  const daysInMonth = new Date(year, month, 0).getDate();
  const firstDay = new Date(year, month - 1, 1).getDay();
  const days = Array.from({ length: daysInMonth }, (_, i) => i + 1);
  const blanks = Array.from({ length: firstDay }, (_, i) => i);

  const highlightedDays = new Set(
    Object.entries(availabilityData)
      .filter(([, avail]) => avail.count > 0)
      .map(([day]) => Number(day))
  );

  // AI candidate slot dates for this month (blue border overlay)
  const aiHighlightedDaySet = new Set(
    aiHighlightedDates
      .filter((d) => {
        const [y, m] = d.split("-").map(Number);
        return y === year && m === month;
      })
      .map((d) => Number(d.split("-")[2])),
  );

  // 각 일(day)별 피어 선택 목록. 해당 월에 속한 것만.
  const peerSelectionsByDay: Record<number, Array<{ key: string; name: string; color: string }>> = {};
  const PEER_COLORS = ["#f59e0b", "#10b981", "#ec4899", "#8b5cf6", "#14b8a6", "#ef4444"];
  Object.entries(peerDateSelections).forEach(([key, sel], idx) => {
    if (!sel.date) return;
    const [py, pm, pd] = sel.date.split("-").map(Number);
    if (py !== year || pm !== month) return;
    const color = PEER_COLORS[(sel.userId ?? idx) % PEER_COLORS.length];
    if (!peerSelectionsByDay[pd]) peerSelectionsByDay[pd] = [];
    peerSelectionsByDay[pd].push({ key, name: sel.name, color });
  });

  const goPrev = () => {
    setClickedDay(null);
    if (month === 1) { setYear((y: number) => y - 1); setMonth(12); }
    else setMonth((m: number) => m - 1);
  };
  const goNext = () => {
    setClickedDay(null);
    if (month === 12) { setYear((y: number) => y + 1); setMonth(1); }
    else setMonth((m: number) => m + 1);
  };

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(false);
    setAvailabilityData({});

    apiFetch<CalendarApiResponse>(
      `/api/v1/calendar/free-slots?room_id=${roomId}&year=${year}&month=${month}`,
    )
      .then((data) => {
        if (cancelled) return;
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
        setLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        console.error("캘린더 데이터 로드 실패:", err);
        setError(true);
        setLoading(false);
      });

    return () => { cancelled = true; };
  }, [calendarRefreshTrigger, month, roomId, year]);

  return (
    <div
      style={{
        width: "100%",
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
          background: blockMode ? "#fef2f2" : "#f2f4f7",
          borderRadius: "20px 20px 0 0",
          padding: "clamp(10px, 1vw, 16px) clamp(12px, 1.2vw, 20px)",
          borderBottom: `1px solid ${blockMode ? "#fecaca" : "#e2e8f0"}`,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 8,
        }}
      >
        <span
          style={{
            fontSize: fs(26, 17),
            fontWeight: 400,
            color: "#000000",
            letterSpacing: 0.75,
          }}
        >
          캘린더
        </span>
        <button
          onClick={() => setBlockMode((v) => !v)}
          aria-pressed={blockMode}
          title={blockMode ? "불가능 모드 끄기 (날짜 선택으로 돌아가기)" : "불가능 날짜 표시 모드 켜기"}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            padding: "6px 10px",
            borderRadius: 8,
            border: `1px solid ${blockMode ? "#ef4444" : "#cbd5e1"}`,
            background: blockMode ? "#ef4444" : "#ffffff",
            color: blockMode ? "#ffffff" : "#64748b",
            fontSize: fs(12, 11),
            fontWeight: 600,
            cursor: "pointer",
            fontFamily: "inherit",
          }}
        >
          <Ban size={14} />
          {blockMode ? "불가능 모드 ON" : "불가능 날짜"}
        </button>
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
            fontSize: fs(16, 13),
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
      <div style={{ padding: "0 clamp(8px, 1vw, 19px)" }}>
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
                fontSize: fs(12, 10.5),
                fontWeight: "normal",
                color: "#94a3b8",
                padding: "6px 0",
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
            gridTemplateColumns: "repeat(7, 1fr)",
            gap: 2,
          }}
        >
          {blanks.map((b) => (
            <div key={`b-${b}`} style={{ aspectRatio: "1 / 1", minHeight: 36 }} />
          ))}
          {days.map((day) => {
            const isHighlighted = highlightedDays.has(day);
            const isAiHighlighted = aiHighlightedDaySet.has(day);
            const avail = availabilityData[day];
            const todayDate = new Date();
            const isToday =
              year === todayDate.getFullYear() &&
              month === todayDate.getMonth() + 1 &&
              day === todayDate.getDate();
            const isClicked = day === clickedDay;
            const isPast = new Date(year, month - 1, day) < new Date(todayDate.getFullYear(), todayDate.getMonth(), todayDate.getDate());

            const dateStr = `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
            const isMyBlocked = myUnavailableDates.has(dateStr);
            const blockedCount = unavailableCountByDate[dateStr] ?? 0;

            const handleDayClick = () => {
              if (isPast) return; // 과거 날짜 클릭 무시
              // 불가능 모드: 내 불가능 토글만 수행
              if (blockMode) {
                sendUnavailableToggle?.(dateStr, !isMyBlocked);
                return;
              }
              if (isClicked) {
                setClickedDay(null);
                if (setInfoPanePhase && infoPanePhase === "dateSelected") {
                  setInfoPanePhase("idle");
                }
                sendDateSelection?.(null);
              } else {
                setClickedDay(day);
                if (setInfoPanePhase && infoPanePhase === "idle") {
                  setInfoPanePhase("dateSelected");
                }
                sendDateSelection?.(dateStr);
              }
            };

            // AI highlight + availability cross-check
            const aiButBusy = isAiHighlighted && avail && avail.count === 0;
            const aiAndAvailable = isAiHighlighted && avail && avail.count > 0;

            // Border priority: 내 불가능(red) > AI available (blue) > AI busy (red dashed) > today/clicked (indigo)
            let borderStyle: string | undefined;
            if (isMyBlocked) {
              borderStyle = "2px solid #ef4444";
            } else if (aiButBusy) {
              borderStyle = "2px dashed #ef4444";
            } else if (aiAndAvailable || isAiHighlighted) {
              borderStyle = "2px solid #3B82F6";
            } else if (isToday || isClicked) {
              borderStyle = "2px solid #4f46e5";
            }

            const peersForDay = peerSelectionsByDay[day] ?? [];

            return (
              <div
                key={day}
                onClick={handleDayClick}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  aspectRatio: "1 / 1",
                  minHeight: 36,
                  width: "100%",
                  borderRadius: isHighlighted || isAiHighlighted || isToday || isClicked || isMyBlocked ? 8 : 0,
                  cursor: isPast ? "default" : "pointer",
                  background: isPast ? "transparent" : isHighlighted ? "#e0e7ff" : "transparent",
                  border: isPast ? undefined : borderStyle,
                  opacity: isPast ? 0.4 : 1,
                  position: "relative",
                }}
              >
                <span
                  style={{
                    fontSize: fs(13, 11),
                    fontWeight: "normal",
                    color: isPast ? "#cbd5e1" : "#334155",
                    lineHeight: 1.4,
                  }}
                >
                  {day}
                </span>
                {avail && (
                  <span
                    style={{
                      fontSize: fs(9, 8),
                      fontWeight: "normal",
                      color: availColor(avail.count, avail.total),
                      lineHeight: 1.2,
                      fontFamily: "Inter, sans-serif",
                    }}
                  >
                    {avail.count}/{avail.total}
                  </span>
                )}
                {(() => {
                  const othersBlocked = blockedCount - (isMyBlocked ? 1 : 0);
                  if (othersBlocked <= 0) return null;
                  return (
                    <span
                      aria-label={`${othersBlocked}명 불가능`}
                      title={`${othersBlocked}명 이 날 불가능`}
                      style={{
                        position: "absolute",
                        top: 2,
                        right: 2,
                        minWidth: 14,
                        height: 14,
                        padding: "0 3px",
                        borderRadius: 7,
                        background: "#ef4444",
                        color: "#ffffff",
                        fontSize: 9,
                        fontWeight: 700,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        lineHeight: 1,
                        fontFamily: "Inter, sans-serif",
                      }}
                    >
                      {othersBlocked}
                    </span>
                  );
                })()}
                {peersForDay.length > 0 && (
                  <div
                    style={{
                      position: "absolute",
                      bottom: 2,
                      left: 0,
                      right: 0,
                      display: "flex",
                      gap: 2,
                      justifyContent: "center",
                    }}
                    title={`${peersForDay.map((p) => p.name).join(", ")} 선택 중`}
                  >
                    {peersForDay.slice(0, 3).map((p) => (
                      <span
                        key={p.key}
                        style={{
                          width: 6,
                          height: 6,
                          borderRadius: "50%",
                          background: p.color,
                          display: "inline-block",
                          border: "1px solid #fff",
                          boxSizing: "border-box",
                        }}
                      />
                    ))}
                    {peersForDay.length > 3 && (
                      <span
                        style={{
                          fontSize: 8,
                          color: "#64748b",
                          lineHeight: 1,
                        }}
                      >
                        +{peersForDay.length - 3}
                      </span>
                    )}
                  </div>
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
          margin: "8px clamp(8px, 1vw, 19px) 0",
        }}
      />

      {/* Bottom section */}
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          padding: "10px clamp(8px, 1vw, 19px) clamp(10px, 1vw, 19px)",
          overflow: "hidden",
        }}
      >
        {/* 다른 참여자들의 실시간 날짜 선택 요약 */}
        {Object.values(peerDateSelections).some((s) => s.date) && (
          <div
            style={{
              marginBottom: 10,
              padding: "8px 12px",
              borderRadius: 10,
              background: "#fefce8",
              border: "1px solid #fde68a",
              display: "flex",
              flexDirection: "column",
              gap: 4,
            }}
          >
            <span style={{ fontSize: 11, fontWeight: 700, color: "#854d0e" }}>
              다른 참여자 선택
            </span>
            {Object.entries(peerDateSelections)
              .filter(([, s]) => s.date)
              .map(([key, s], idx) => {
                const color = PEER_COLORS[(s.userId ?? idx) % PEER_COLORS.length];
                const [, pm, pd] = (s.date ?? "--").split("-");
                return (
                  <div key={key} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <span
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: "50%",
                        background: color,
                        display: "inline-block",
                        flexShrink: 0,
                      }}
                    />
                    <span style={{ fontSize: 12, color: "#475569" }}>
                      {s.name}님이 {Number(pm)}월 {Number(pd)}일 선택 중
                    </span>
                  </div>
                );
              })}
          </div>
        )}

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
            {/* 가용 인원 요약 */}
            {availabilityData[clickedDay] && (
              <div style={{ marginTop: 6, fontSize: 12, fontWeight: 600, color: "#475569" }}>
                가능 인원: {availabilityData[clickedDay]!.available?.length ?? 0}/{availabilityData[clickedDay]!.total ?? 0}명
              </div>
            )}
            {/* 시간대별 가용성 미니바 (모든 날짜) */}
            {(() => {
              const dateStr = `${year}-${String(month).padStart(2, "0")}-${String(clickedDay).padStart(2, "0")}`;
              const isAiDate = aiHighlightedDates.includes(dateStr);
              const slotsForDay = candidateSlots.filter((s) => s.start_at.startsWith(dateStr));
              return (
                <>
                  {isAiDate && (
                    <div style={{
                      display: "inline-block",
                      padding: "2px 8px",
                      borderRadius: 6,
                      background: "#dbeafe",
                      color: "#1d4ed8",
                      fontSize: 11,
                      fontWeight: 600,
                      marginTop: 6,
                    }}>
                      AI 추천 날짜
                    </div>
                  )}
                  <MiniTimeBar
                    date={dateStr}
                    roomId={roomId}
                    aiSlots={slotsForDay.length > 0 ? slotsForDay.map((s) => ({ start_at: s.start_at, end_at: s.end_at })) : undefined}
                  />
                </>
              );
            })()}
            {/* 날짜 확정 버튼 */}
            {(() => {
              if (!confirmDate || clickedDay === null) return null;
              const clickedDateStr = `${year}-${String(month).padStart(2, "0")}-${String(clickedDay).padStart(2, "0")}`;
              const confirmedDateStr = meeting?.confirmedDate ?? null;
              const alreadyConfirmedSame = confirmedDateStr === clickedDateStr;
              const isReplacing = confirmedDateStr !== null && !alreadyConfirmedSame;
              const showButton =
                infoPanePhase === "dateSelected" ||
                (isReplacing &&
                  (infoPanePhase === "dateConfirmed" ||
                    infoPanePhase === "timeConfirmed"));
              if (!showButton || alreadyConfirmedSame) return null;

              let label = "이 날짜로 확정";
              if (isReplacing && confirmedDateStr) {
                const [, cm, cd] = confirmedDateStr.split("-");
                label = `${Number(cm)}월 ${Number(cd)}일 취소하고 이 날짜로 확정`;
              }

              return (
                <button
                  onClick={() => confirmDate(clickedDateStr)}
                  style={{
                    marginTop: 8,
                    width: "100%",
                    padding: "10px 14px",
                    borderRadius: 10,
                    border: "none",
                    background: isReplacing ? "#dc2626" : "#4f46e5",
                    color: "#ffffff",
                    cursor: "pointer",
                    fontFamily: "Pretendard Variable, Pretendard, sans-serif",
                    fontSize: 13,
                    fontWeight: 700,
                  }}
                >
                  {label}
                </button>
              );
            })()}
          </div>
        )}

        {/* Loading / Error state for calendar data */}
        {loading && (
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
        )}
        {error && !loading && (
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
        )}
      </div>
    </div>
  );
}
