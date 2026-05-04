"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronLeft, Clock } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { useMeetingOptional } from "@/contexts/MeetingContext";

const HOUR_START = 9;
const HOUR_END = 22;
const SLOT_MINUTES = 30;
const TOTAL_SLOTS = ((HOUR_END - HOUR_START) * 60) / SLOT_MINUTES; // 26 slots

const CELL_WIDTH = 12;
const CELL_HEIGHT = 28;
const NAME_WIDTH = 64;

// TODO(tech-debt): hex 색상 → 디자인 토큰(Tailwind theme) 이관 예정
const COLOR_CALENDAR_CONFLICT = "#fdba74";  // 다른 일정 겹침 (옅은 주황, orange-300)
const COLOR_AVAILABLE_IDLE = "#dcfce7";     // 미선택 가능 (연한 초록)
const COLOR_MY_PICK = "#93c5fd";            // 내가 고른 시간 (옅은 파랑, blue-300)
const COLOR_PEERS_BASE = "#38bdf8";         // 다른 분들 집계 기본 (하늘색, sky-400)
const COLOR_EVERYONE_AGREE = "#22c55e";     // 전원 row: 나 + 남 모두 고른 시간 (초록)
const COLOR_RECOMMEND_OUTLINE = "#3B82F6";
const COLOR_SELECTION_BORDER = "#3b82f6";

function isSlotInRange(slotIdx: number, start: number | null, end: number | null): boolean {
  if (start === null) return false;
  const hi = end ?? start;
  return slotIdx >= Math.min(start, hi) && slotIdx <= Math.max(start, hi);
}

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

  const { user } = useAuth();
  const myName = user?.name ?? "나";
  const meeting = useMeetingOptional();
  const peerTimeSelections = meeting?.peerTimeSelections ?? {};
  const sendTimeSelection = meeting?.sendTimeSelection ?? null;
  const myTimeSelection = meeting?.myTimeSelection ?? null;

  // 리프레시 복구: 마운트 + date 변경 시 서버가 push한 내 이전 선택이 있으면 복원.
  useEffect(() => {
    if (myTimeSelection && myTimeSelection.date === date) {
      setSelectionStart(myTimeSelection.start);
      setSelectionEnd(myTimeSelection.end);
    }
  }, [date, myTimeSelection]);

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

  // 내 busy 시간 (외부 캘린더 기반). 이름 match 안 되면 빈 배열
  const myBusyPeriods = useMemo(
    () => memberData?.[myName] ?? [],
    [memberData, myName],
  );

  // 전원 기준 가용성 (모두의 외부 캘린더가 비어있는 slot)
  const aggregateAvailability = useMemo(() => {
    if (members.length === 0) return Array(TOTAL_SLOTS).fill(true);
    return Array.from({ length: TOTAL_SLOTS }, (_, slotIdx) =>
      members.every((m) => !isBusyAtSlot(m.periods, date, slotIdx))
    );
  }, [members, date]);

  // 나 제외 다른 멤버들의 캘린더 겹침 수 (슬롯별)
  const othersBusyPerSlot = useMemo(() => {
    const others = members.filter((m) => m.name !== myName);
    if (others.length === 0) return Array(TOTAL_SLOTS).fill(0);
    return Array.from({ length: TOTAL_SLOTS }, (_, slotIdx) =>
      others.filter((m) => isBusyAtSlot(m.periods, date, slotIdx)).length,
    );
  }, [members, date, myName]);

  // 해당 날짜에 다른 참여자들이 선택한 범위들. peer별 slot 포함 여부 집계
  const peerSelectionStats = useMemo(() => {
    const relevant = Object.values(peerTimeSelections).filter((p) => p.date === date);
    const counts = new Array(TOTAL_SLOTS).fill(0);
    relevant.forEach((p) => {
      const lo = Math.min(p.start, p.end);
      const hi = Math.max(p.start, p.end);
      for (let i = lo; i <= hi; i++) {
        if (i >= 0 && i < TOTAL_SLOTS) counts[i] += 1;
      }
    });
    return { counts, totalPeers: relevant.length };
  }, [peerTimeSelections, date]);

  // 내 선택 변경 시 브로드캐스트
  useEffect(() => {
    if (!sendTimeSelection) return;
    if (selectionStart === null) {
      sendTimeSelection(date, null, null);
      return;
    }
    // 끝 선택 전 (단일 slot)도 실시간으로 보여줌
    const endVal = selectionEnd ?? selectionStart;
    sendTimeSelection(date, selectionStart, endVal);
  }, [selectionStart, selectionEnd, date, sendTimeSelection]);

  // 날짜 바뀌면 현재 선택 리셋 (이전 날짜의 선택이 새 날짜에 이어지지 않게)
  useEffect(() => {
    setSelectionStart(null);
    setSelectionEnd(null);
  }, [date]);

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

  // aria-activedescendant: 스크린리더가 현재 활성 슬롯을 알 수 있도록 aggregate row cell에 id 부여.
  // aggregate row는 members.length > 0 일 때만 렌더되므로, 없을 때 id 참조가 DOM에 존재하지 않게 가드.
  const gridId = `timebar-${date.replace(/-/g, "")}`;
  const activeSlotIdx = selectionEnd ?? selectionStart;
  const activeDescendantId =
    activeSlotIdx !== null && members.length > 0
      ? `${gridId}-agg-${activeSlotIdx}`
      : undefined;

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
        <div
          style={{ display: "inline-block", minWidth: "100%" }}
          role="grid"
          aria-label={`${dateLabel} 시간 선택`}
          aria-activedescendant={activeDescendantId}
          tabIndex={0}
          onKeyDown={handleKeyDown}
        >
          {/* Hour labels — 시각적 눈금. 스크린리더는 cell aria-label이 시간을 이미 포함하므로 숨김 */}
          <div aria-hidden="true" style={{ display: "flex", marginLeft: NAME_WIDTH, marginBottom: 2 }}>
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

          {/* Row 1: 내 시간 — 내 외부 캘린더 busy 회색 + 내가 고른 시간 인디고. 클릭 토글 */}
          <div role="row" style={{ display: "flex", alignItems: "center", marginBottom: 2 }}>
            <div
              role="rowheader"
              style={{
                width: NAME_WIDTH,
                fontSize: 11,
                fontWeight: 600,
                color: "#4f46e5",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
                flexShrink: 0,
                paddingRight: 4,
              }}
            >
              {myName}
            </div>
            {Array.from({ length: TOTAL_SLOTS }, (_, slotIdx) => {
              const isBusy = isBusyAtSlot(myBusyPeriods, date, slotIdx);
              const isMine = isSlotInRange(slotIdx, selectionStart, selectionEnd);
              const isRecommended = !!recommendedRange &&
                slotIdx >= recommendedRange.start && slotIdx <= recommendedRange.end;

              let bg: string;
              if (isMine) bg = COLOR_MY_PICK;
              else if (isBusy) bg = COLOR_CALENDAR_CONFLICT;
              else bg = COLOR_AVAILABLE_IDLE;

              const cellLabel = `내 시간 ${slotToTime(slotIdx)} ${isMine ? "내가 선택함" : isBusy ? "다른 일정" : "가능"}`;
              return (
                <div
                  key={slotIdx}
                  id={`${gridId}-mine-${slotIdx}`}
                  role="gridcell"
                  tabIndex={-1}
                  aria-selected={isMine}
                  aria-label={cellLabel}
                  onClick={() => handleSlotClick(slotIdx)}
                  style={{
                    width: CELL_WIDTH,
                    height: CELL_HEIGHT,
                    background: bg,
                    borderLeft: slotIdx % 2 === 0 ? "1px solid rgba(0,0,0,0.06)" : "none",
                    borderBottom: "1px solid rgba(0,0,0,0.04)",
                    cursor: "pointer",
                    flexShrink: 0,
                    outline: isRecommended ? `1px solid ${COLOR_RECOMMEND_OUTLINE}` : "none",
                    outlineOffset: -1,
                    boxShadow: isMine ? `inset 0 0 0 1px ${COLOR_SELECTION_BORDER}` : undefined,
                  }}
                  title={cellLabel}
                />
              );
            })}
          </div>

          {/* Row 2: 다른 분들 — 나 제외 참여자들의 선택 집계, 선택자 수에 비례한 alpha 그라데이션 */}
          <div role="row" aria-label="다른 분들 합산" style={{ display: "flex", alignItems: "center", marginBottom: 2 }}>
            <div
              role="rowheader"
              style={{
                width: NAME_WIDTH,
                fontSize: 11,
                fontWeight: 500,
                color: "#0369a1",
                flexShrink: 0,
                paddingRight: 4,
              }}
            >
              다른 분들
            </div>
            {Array.from({ length: TOTAL_SLOTS }, (_, slotIdx) => {
              const count = peerSelectionStats.counts[slotIdx];
              const total = peerSelectionStats.totalPeers;
              const hasPeer = count > 0;
              const othersBusy = othersBusyPerSlot[slotIdx] > 0;
              const alpha = total > 0 ? 0.15 + (count / total) * 0.7 : 0;
              let bg: string;
              if (hasPeer) bg = `rgba(56, 189, 248, ${alpha.toFixed(2)})`;
              else if (othersBusy) bg = COLOR_CALENDAR_CONFLICT;
              else bg = "#f1f5f9";
              const label = `다른 분들 ${slotToTime(slotIdx)} ${hasPeer ? `${count}/${total}명 선택` : othersBusy ? "다른 일정" : ""}`;
              return (
                <div
                  key={slotIdx}
                  role="gridcell"
                  tabIndex={-1}
                  aria-label={label}
                  style={{
                    width: CELL_WIDTH,
                    height: CELL_HEIGHT,
                    background: bg,
                    borderLeft: slotIdx % 2 === 0 ? "1px solid rgba(0,0,0,0.06)" : "none",
                    borderBottom: "1px solid rgba(0,0,0,0.04)",
                    flexShrink: 0,
                  }}
                  title={label}
                />
              );
            })}
          </div>

          {/* Row 3: 전원 — 내 선택/남 선택/교집합을 다른 색으로 */}
          <div role="row" aria-label="전원" style={{ borderTop: "1.5px solid #94a3b8", marginTop: 2, paddingTop: 2, display: "flex", alignItems: "center" }}>
            <div
              role="rowheader"
              style={{
                width: NAME_WIDTH,
                fontSize: 11,
                fontWeight: 700,
                color: "#1e293b",
                flexShrink: 0,
                paddingRight: 4,
              }}
            >
              전원
            </div>
            {Array.from({ length: TOTAL_SLOTS }, (_, slotIdx) => {
              const isMine = isSlotInRange(slotIdx, selectionStart, selectionEnd);
              const peerCount = peerSelectionStats.counts[slotIdx];
              const hasPeer = peerCount > 0;

              let bg: string;
              if (isMine && hasPeer) bg = COLOR_EVERYONE_AGREE;
              else if (isMine) bg = COLOR_MY_PICK;
              else if (hasPeer) bg = COLOR_PEERS_BASE;
              else if (!aggregateAvailability[slotIdx]) bg = COLOR_CALENDAR_CONFLICT;
              else bg = "#dcfce7";

              const stateLabel = isMine && hasPeer
                ? `나 + 다른 ${peerCount}명 선택`
                : isMine
                  ? "나만 선택"
                  : hasPeer
                    ? `다른 ${peerCount}명 선택`
                    : aggregateAvailability[slotIdx] ? "가능" : "다른 일정";
              const aggLabel = `전원 ${slotToTime(slotIdx)} ${stateLabel}`;

              return (
                <div
                  key={slotIdx}
                  id={`${gridId}-agg-${slotIdx}`}
                  role="gridcell"
                  tabIndex={-1}
                  aria-selected={isMine}
                  aria-label={aggLabel}
                  style={{
                    width: CELL_WIDTH,
                    height: CELL_HEIGHT,
                    background: bg,
                    borderLeft: slotIdx % 2 === 0 ? "1px solid rgba(0,0,0,0.06)" : "none",
                    cursor: "default",
                    flexShrink: 0,
                  }}
                  title={aggLabel}
                />
              );
            })}
          </div>

        </div>
      </div>

      {/* Legend */}
      <div style={{ display: "flex", gap: 10, fontSize: 11, color: "#64748b", flexWrap: "wrap" }}>
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ width: 12, height: 12, borderRadius: 3, background: COLOR_MY_PICK, display: "inline-block" }} /> 내 선택
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ width: 12, height: 12, borderRadius: 3, background: COLOR_PEERS_BASE, display: "inline-block" }} /> 다른 분들
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ width: 12, height: 12, borderRadius: 3, background: COLOR_EVERYONE_AGREE, display: "inline-block" }} /> 나+다른 분
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ width: 12, height: 12, borderRadius: 3, background: COLOR_CALENDAR_CONFLICT, display: "inline-block" }} /> 다른 일정
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
