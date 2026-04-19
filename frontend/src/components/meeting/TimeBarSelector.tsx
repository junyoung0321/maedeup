"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronLeft, Clock } from "lucide-react";
import { apiFetch } from "@/lib/api";

const HOUR_START = 9;
const HOUR_END = 22;
const SLOT_MINUTES = 30;
const TOTAL_SLOTS = ((HOUR_END - HOUR_START) * 60) / SLOT_MINUTES; // 26 slots

const CELL_WIDTH = 12;
const CELL_HEIGHT = 28;
const NAME_WIDTH = 56;
const HEADER_HEIGHT = 20;

interface MemberBusyPeriod {
  start: string;
  end: string;
}

interface TimeBarSelectorProps {
  date: string; // "YYYY-MM-DD"
  roomId: string;
  onConfirm: (startAt: string, endAt: string) => void;
  onBack?: () => void;
}

function slotToTime(slotIndex: number): string {
  const totalMinutes = HOUR_START * 60 + slotIndex * SLOT_MINUTES;
  const h = Math.floor(totalMinutes / 60);
  const m = totalMinutes % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

function formatTimeLabel(time: string): string {
  const [h, m] = time.split(":").map(Number);
  const ampm = h < 12 ? "오전" : "오후";
  const displayH = h <= 12 ? h : h - 12;
  return `${ampm} ${displayH}:${String(m).padStart(2, "0")}`;
}

function isBusyAtSlot(
  busyPeriods: MemberBusyPeriod[],
  date: string,
  slotIndex: number,
): boolean {
  const slotStartMinutes = HOUR_START * 60 + slotIndex * SLOT_MINUTES;
  const slotEndMinutes = slotStartMinutes + SLOT_MINUTES;

  for (const period of busyPeriods) {
    const pStart = new Date(period.start);
    const pEnd = new Date(period.end);
    // Convert to minutes from midnight in local time
    const pStartMinutes = pStart.getHours() * 60 + pStart.getMinutes();
    const pEndMinutes = pEnd.getHours() * 60 + pEnd.getMinutes();
    // Check date match (simple check: same date string in local)
    const pDateStr = `${pStart.getFullYear()}-${String(pStart.getMonth() + 1).padStart(2, "0")}-${String(pStart.getDate()).padStart(2, "0")}`;

    if (pDateStr === date) {
      // All-day event (spans midnight to midnight or beyond)
      if (pEndMinutes === 0 && pStartMinutes === 0) return true;
      if (pStartMinutes < slotEndMinutes && pEndMinutes > slotStartMinutes) return true;
    }
    // Handle events that span from previous day
    if (pDateStr < date && pEnd.toISOString().startsWith(date)) {
      if (pEndMinutes > slotStartMinutes) return true;
    }
  }
  return false;
}

export default function TimeBarSelector({ date, roomId, onConfirm, onBack }: TimeBarSelectorProps) {
  const [memberData, setMemberData] = useState<Record<string, MemberBusyPeriod[]> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectionStart, setSelectionStart] = useState<number | null>(null);
  const [selectionEnd, setSelectionEnd] = useState<number | null>(null);
  const [isConfirming, setIsConfirming] = useState(false);

  // Fetch member busy periods for the specific date
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    const [y, m] = date.split("-").map(Number);
    apiFetch<{
      free_slots: unknown[];
      dates: Record<string, unknown>;
      member_busy_periods?: Record<string, MemberBusyPeriod[]>;
    }>(`/api/v1/calendar/free-slots?room_id=${roomId}&year=${y}&month=${m}&detail_date=${date}`)
      .then((data) => {
        if (cancelled) return;
        if (data.member_busy_periods) {
          setMemberData(data.member_busy_periods);
        } else {
          // Fallback: no detail data available, show empty (all available)
          setMemberData({});
        }
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "가용성 조회에 실패했습니다.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, [date, roomId]);

  const members = useMemo(() => {
    if (!memberData) return [];
    return Object.entries(memberData).map(([name, periods]) => ({ name, periods }));
  }, [memberData]);

  // Compute "전원" aggregate row
  const aggregateAvailability = useMemo(() => {
    if (members.length === 0) return Array(TOTAL_SLOTS).fill(true);
    return Array.from({ length: TOTAL_SLOTS }, (_, slotIdx) =>
      members.every((m) => !isBusyAtSlot(m.periods, date, slotIdx))
    );
  }, [members, date]);

  // AI recommended range: longest streak where all members are available
  // Only show if there are actual members with calendar data, and cap at 4 hours (8 slots)
  const recommendedRange = useMemo(() => {
    if (members.length === 0) return null; // No members → no recommendation
    const MAX_RECOMMEND_SLOTS = 8; // 4 hours max
    let bestStart = -1, bestLen = 0, curStart = -1, curLen = 0;
    for (let i = 0; i < TOTAL_SLOTS; i++) {
      if (aggregateAvailability[i]) {
        if (curStart === -1) curStart = i;
        curLen++;
        if (curLen > bestLen) { bestStart = curStart; bestLen = curLen; }
      } else {
        curStart = -1; curLen = 0;
      }
    }
    if (bestLen < 2) return null;
    // Cap the recommended range
    const cappedLen = Math.min(bestLen, MAX_RECOMMEND_SLOTS);
    return { start: bestStart, end: bestStart + cappedLen - 1 };
  }, [aggregateAvailability]);

  const handleSlotClick = useCallback((slotIndex: number) => {
    if (selectionStart === null) {
      setSelectionStart(slotIndex);
      setSelectionEnd(null);
    } else if (selectionEnd === null) {
      if (slotIndex >= selectionStart) {
        setSelectionEnd(slotIndex);
      } else {
        // Clicked before start: restart
        setSelectionStart(slotIndex);
        setSelectionEnd(null);
      }
    } else {
      // Already have a selection: restart
      setSelectionStart(slotIndex);
      setSelectionEnd(null);
    }
  }, [selectionStart, selectionEnd]);

  const handleConfirm = useCallback(async () => {
    if (selectionStart === null || selectionEnd === null) return;
    setIsConfirming(true);
    const startTime = slotToTime(selectionStart);
    const endTime = slotToTime(selectionEnd + 1); // +1 because end is inclusive
    const startAt = `${date}T${startTime}:00`;
    const endAt = `${date}T${endTime}:00`;
    try {
      await onConfirm(startAt, endAt);
    } finally {
      setIsConfirming(false);
    }
  }, [selectionStart, selectionEnd, date, onConfirm]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    const currentSlot = selectionEnd ?? selectionStart ?? 0;
    if (e.key === "ArrowRight" && currentSlot < TOTAL_SLOTS - 1) {
      handleSlotClick(currentSlot + 1);
      e.preventDefault();
    } else if (e.key === "ArrowLeft" && currentSlot > 0) {
      handleSlotClick(currentSlot - 1);
      e.preventDefault();
    } else if (e.key === "Enter" && selectionStart !== null && selectionEnd !== null) {
      handleConfirm();
      e.preventDefault();
    }
  }, [selectionStart, selectionEnd, handleSlotClick, handleConfirm]);

  // Format selected range for display
  const selectionLabel = selectionStart !== null && selectionEnd !== null
    ? `${formatTimeLabel(slotToTime(selectionStart))} ~ ${formatTimeLabel(slotToTime(selectionEnd + 1))}`
    : selectionStart !== null
      ? `${formatTimeLabel(slotToTime(selectionStart))} ~ (끝 시간 선택)`
      : null;

  // Parse date for display
  const [, monthStr, dayStr] = date.split("-");
  const dayOfWeek = ["일", "월", "화", "수", "목", "금", "토"][new Date(date).getDay()];
  const dateLabel = `${Number(monthStr)}월 ${Number(dayStr)}일 (${dayOfWeek})`;

  if (loading) {
    return (
      <div style={{
        padding: "24px 18px",
        borderRadius: 18,
        background: "#f1f5f9",
        border: "1px solid #cbd5e1",
        textAlign: "center",
        fontFamily: "Pretendard Variable, Pretendard, sans-serif",
      }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: "#4f46e5", marginBottom: 8 }}>
          가용성 조회 중...
        </div>
        <div style={{ fontSize: 13, color: "#64748b" }}>
          멤버 일정을 확인하고 있어요
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{
        padding: "18px",
        borderRadius: 18,
        background: "#fef2f2",
        border: "1px solid #fecaca",
        fontFamily: "Pretendard Variable, Pretendard, sans-serif",
      }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: "#dc2626", marginBottom: 4 }}>
          가용성 조회 실패
        </div>
        <div style={{ fontSize: 13, color: "#7f1d1d" }}>{error}</div>
      </div>
    );
  }

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 12,
        padding: 18,
        borderRadius: 18,
        background: "#f1f5f9",
        border: "1px solid #cbd5e1",
        fontFamily: "Pretendard Variable, Pretendard, sans-serif",
      }}
      onKeyDown={handleKeyDown}
      tabIndex={0}
    >
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        {onBack && (
          <button
            onClick={onBack}
            style={{ border: "none", background: "transparent", cursor: "pointer", padding: 4, display: "flex" }}
          >
            <ChevronLeft style={{ width: 18, height: 18, color: "#4f46e5" }} />
          </button>
        )}
        <div style={{ width: 36, height: 36, borderRadius: 12, background: "#e0e7ff", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Clock style={{ width: 18, height: 18, color: "#4f46e5" }} />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: "#4f46e5" }}>시간 선택</span>
          <span style={{ fontSize: 15, fontWeight: 700, color: "#1e293b" }}>{dateLabel}</span>
        </div>
      </div>

      {/* Time grid */}
      <div style={{ overflowX: "auto", paddingBottom: 4 }}>
        <div style={{ display: "inline-block", minWidth: "100%", position: "relative" }}>
          {/* Hour labels */}
          <div style={{ display: "flex", marginLeft: NAME_WIDTH, marginBottom: 2 }}>
            {Array.from({ length: HOUR_END - HOUR_START }, (_, i) => (
              <div
                key={i}
                style={{
                  width: CELL_WIDTH * 2,
                  fontSize: 10,
                  fontWeight: 500,
                  color: "#94a3b8",
                  textAlign: "left",
                  flexShrink: 0,
                }}
              >
                {HOUR_START + i}
              </div>
            ))}
          </div>

          {/* Member rows (read-only: show each member's availability, NOT clickable) */}
          {members.map((member) => (
            <div key={member.name} style={{ display: "flex", alignItems: "center", marginBottom: 2 }}>
              <div style={{
                width: NAME_WIDTH,
                fontSize: 11,
                fontWeight: 500,
                color: "#475569",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
                flexShrink: 0,
                paddingRight: 4,
              }}>
                {member.name}
              </div>
              <div style={{ display: "flex" }}>
                {Array.from({ length: TOTAL_SLOTS }, (_, slotIdx) => {
                  const isBusy = isBusyAtSlot(member.periods, date, slotIdx);
                  const isRecommended = recommendedRange &&
                    slotIdx >= recommendedRange.start && slotIdx <= recommendedRange.end;

                  return (
                    <div
                      key={slotIdx}
                      style={{
                        width: CELL_WIDTH,
                        height: CELL_HEIGHT,
                        background: isBusy ? "#e2e8f0" : "#bbf7d0",
                        borderLeft: slotIdx % 2 === 0 ? "1px solid rgba(0,0,0,0.06)" : "none",
                        borderBottom: "1px solid rgba(0,0,0,0.04)",
                        flexShrink: 0,
                        outline: isRecommended && !isBusy ? "1px solid #3B82F6" : "none",
                        outlineOffset: -1,
                      }}
                      title={`${member.name} ${slotToTime(slotIdx)} ${isBusy ? "불가" : "가능"}`}
                    />
                  );
                })}
              </div>
            </div>
          ))}

          {/* Aggregate "전원" row — the ONLY clickable row for selecting meeting time */}
          {members.length > 0 && (
            <div style={{ borderTop: "1.5px solid #94a3b8", marginTop: 2, paddingTop: 2, display: "flex", alignItems: "center" }}>
              <div style={{
                width: NAME_WIDTH,
                fontSize: 11,
                fontWeight: 700,
                color: "#1e293b",
                flexShrink: 0,
                paddingRight: 4,
              }}>
                전원
              </div>
              <div style={{ display: "flex" }}>
                {aggregateAvailability.map((available, slotIdx) => {
                  const isInSelection = selectionStart !== null &&
                    ((selectionEnd !== null && slotIdx >= selectionStart && slotIdx <= selectionEnd) ||
                     (selectionEnd === null && slotIdx === selectionStart));

                  return (
                    <div
                      key={slotIdx}
                      onClick={() => handleSlotClick(slotIdx)}
                      style={{
                        width: CELL_WIDTH,
                        height: CELL_HEIGHT,
                        background: !available ? "#e2e8f0" : isInSelection ? "#6366f1" : "#22c55e",
                        borderLeft: slotIdx % 2 === 0 ? "1px solid rgba(0,0,0,0.06)" : "none",
                        cursor: "pointer",
                        flexShrink: 0,
                      }}
                      title={`전원 ${slotToTime(slotIdx)} ${available ? "가능" : "불가"}`}
                    />
                  );
                })}
              </div>
            </div>
          )}

          {/* Selection overlay — vertical band spanning all rows to visualize chosen range */}
          {selectionStart !== null && (
            <div
              style={{
                position: "absolute",
                left: NAME_WIDTH + selectionStart * CELL_WIDTH,
                top: HEADER_HEIGHT,
                bottom: 0,
                width:
                  ((selectionEnd !== null ? selectionEnd - selectionStart + 1 : 1) *
                    CELL_WIDTH),
                background: "rgba(99, 102, 241, 0.22)",
                border: "2px solid #4f46e5",
                borderRadius: 6,
                pointerEvents: "none",
              }}
            />
          )}
        </div>
      </div>

      {/* Legend */}
      <div style={{ display: "flex", gap: 12, fontSize: 11, color: "#64748b" }}>
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ width: 12, height: 12, borderRadius: 3, background: "#bbf7d0", display: "inline-block" }} /> 가능
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ width: 12, height: 12, borderRadius: 3, background: "#e2e8f0", display: "inline-block" }} /> 불가
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ width: 12, height: 12, borderRadius: 3, background: "#818cf8", display: "inline-block" }} /> 선택
        </span>
        {recommendedRange && (
          <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <span style={{ width: 12, height: 12, borderRadius: 3, border: "1.5px solid #3B82F6", display: "inline-block" }} /> 추천
          </span>
        )}
      </div>

      {/* Recommended range hint */}
      {recommendedRange && !selectionLabel && (
        <div style={{
          padding: "8px 12px",
          borderRadius: 10,
          background: "#eff6ff",
          border: "1px solid #bfdbfe",
          fontSize: 13,
          fontWeight: 500,
          color: "#1d4ed8",
        }}>
          추천: {formatTimeLabel(slotToTime(recommendedRange.start))} ~ {formatTimeLabel(slotToTime(recommendedRange.end + 1))} ({members.length}명 전원 가능)
        </div>
      )}

      {/* Selection label */}
      {selectionLabel && (
        <div style={{
          padding: "8px 12px",
          borderRadius: 10,
          background: "#eef2ff",
          border: "1px solid #c7d2fe",
          fontSize: 13,
          fontWeight: 600,
          color: "#4f46e5",
        }}>
          {selectionLabel}
        </div>
      )}

      {/* Help text */}
      {selectionStart === null && (
        <div style={{ fontSize: 12, color: "#94a3b8", textAlign: "center" }}>
          시작 시간을 클릭한 후 끝 시간을 클릭하세요
        </div>
      )}

      {/* Confirm button */}
      <button
        onClick={handleConfirm}
        disabled={selectionStart === null || selectionEnd === null || isConfirming}
        style={{
          width: "100%",
          padding: "12px 14px",
          borderRadius: 14,
          border: "none",
          background: selectionStart === null || selectionEnd === null || isConfirming ? "#cbd5e1" : "#4f46e5",
          color: "#ffffff",
          cursor: selectionStart === null || selectionEnd === null || isConfirming ? "not-allowed" : "pointer",
          fontFamily: "Pretendard Variable, Pretendard, sans-serif",
          fontSize: 14,
          fontWeight: 700,
        }}
      >
        {isConfirming ? "확정 중..." : selectionLabel ? `${selectionLabel}로 확정` : "시간을 선택해주세요"}
      </button>
    </div>
  );
}
