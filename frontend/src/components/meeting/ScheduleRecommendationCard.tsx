"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { CalendarDays, ChevronDown, ChevronUp, Check } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { useMeeting } from "@/contexts/MeetingContext";
import type { VoteCardPayload } from "@/hooks/useAgentWebSocket";

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
  } catch { /* ignore */ }
  return null;
}

function groupByDate(options: VoteCardPayload["time_options"]) {
  const groups: Record<string, typeof options> = {};
  for (const opt of options) {
    const dateKey = opt.start_at.split("T")[0];
    if (!groups[dateKey]) groups[dateKey] = [];
    groups[dateKey].push(opt);
  }
  return groups;
}

interface ScheduleRecommendationCardProps {
  voteCard?: VoteCardPayload | null;
  onMeetingResolved?: (meetingId: number) => void;
}

export default function ScheduleRecommendationCard({
  voteCard: voteCardProp,
  onMeetingResolved,
}: ScheduleRecommendationCardProps = {}) {
  const {
    voteCard: contextVoteCard,
    roomId,
    refreshCalendar,
    sendMessageToAi,
    setCalendarSyncStatus,
  } = useMeeting();
  const voteCard = voteCardProp ?? contextVoteCard;

  const [selectedSlotId, setSelectedSlotId] = useState<string | null>(null);
  const [showAlternatives, setShowAlternatives] = useState(false);
  const [isConfirming, setIsConfirming] = useState(false);
  const [isConfirmed, setIsConfirmed] = useState(false);
  const [confirmedLabel, setConfirmedLabel] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [hostUserId, setHostUserId] = useState<number | null>(null);
  const [hostLoading, setHostLoading] = useState(true);
  const currentUserId = useMemo(() => getCurrentUserIdFromToken(), []);
  const isHost = currentUserId !== null && hostUserId === currentUserId;

  useEffect(() => {
    if (!roomId) return;
    let cancelled = false;
    setHostLoading(true);
    apiFetch<{ created_by: number }>(`/api/v1/rooms/${roomId}`)
      .then((room) => { if (!cancelled) setHostUserId(room.created_by); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setHostLoading(false); });
    return () => { cancelled = true; };
  }, [roomId]);

  useEffect(() => {
    if (!voteCard) return;
    setSelectedSlotId(voteCard.time_options[0]?.slot_id ?? null);
    setShowAlternatives(false);
    setIsConfirmed(false);
    setConfirmedLabel(null);
    setError(null);
  }, [voteCard]);

  const handleConfirm = useCallback(async () => {
    if (!voteCard || !selectedSlotId) return;
    const slot = voteCard.time_options.find((o) => o.slot_id === selectedSlotId);
    if (!slot) return;
    const parsedRoomId = Number.parseInt(roomId, 10);
    if (Number.isNaN(parsedRoomId)) return;

    setIsConfirming(true);
    setError(null);
    try {
      const result = await apiFetch<{
        id: number;
        calendar_event_for_self?: boolean;
        calendar_member_count?: number;
      }>("/api/v1/meetings/confirm", {
        method: "POST",
        body: JSON.stringify({
          room_id: parsedRoomId,
          title: voteCard.title,
          scheduled_at: slot.start_at,
          end_at: slot.end_at,
          location_name: null,
          meeting_id: voteCard.meeting_id ?? undefined,
          vote_options: voteCard.time_options.map((o) => ({
            slot_id: o.slot_id, label: o.label, start_at: o.start_at, end_at: o.end_at,
          })),
        }),
      });
      setIsConfirmed(true);
      setConfirmedLabel(slot.label);
      setCalendarSyncStatus(
        result.calendar_event_for_self ?? false,
        result.calendar_member_count ?? 0,
      );
      if (voteCard.meeting_id !== undefined) {
        onMeetingResolved?.(voteCard.meeting_id);
      }
      refreshCalendar();
      // 자동 안내 메시지 발송 제거: backend confirm endpoint가 assistant 메시지로 안내,
      // 또는 카드 자체에 "확정됨" 라벨로 충분. AI 패널 입력창은 사용자 ACT 5 입력 전용.
    } catch (err) {
      setError(err instanceof Error ? err.message : "일정 확정에 실패했습니다.");
    } finally {
      setIsConfirming(false);
    }
  }, [voteCard, selectedSlotId, roomId, refreshCalendar, setCalendarSyncStatus, sendMessageToAi, onMeetingResolved]);

  if (!voteCard) return null;

  const best = voteCard.time_options[0];
  const alternatives = voteCard.time_options.slice(1);
  const dateGroups = groupByDate(voteCard.time_options);
  const isMultiDate =
    voteCard.calendar_strategy === "multi_date_vote" &&
    Object.keys(dateGroups).length > 1;
  const headcount = voteCard.headcount;
  const selectedSlot = voteCard.time_options.find((o) => o.slot_id === selectedSlotId);

  if (isConfirmed) {
    return (
      <div style={{
        display: "flex", flexDirection: "column", gap: 10, padding: 16,
        borderRadius: 16, background: "#ecfdf5", border: "1px solid #86efac",
        fontFamily: "Pretendard Variable, Pretendard, sans-serif",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Check style={{ width: 20, height: 20, color: "#16a34a" }} />
          <span style={{ fontSize: 15, fontWeight: 700, color: "#166534" }}>일정이 확정되었습니다</span>
        </div>
        <span style={{ fontSize: 14, fontWeight: 600, color: "#15803d" }}>{confirmedLabel}</span>
      </div>
    );
  }

  return (
    <div style={{
      display: "flex", flexDirection: "column", gap: 12, padding: 16,
      borderRadius: 16, background: "#f8fafc", border: "1px solid #e2e8f0",
      fontFamily: "Pretendard Variable, Pretendard, sans-serif",
    }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <CalendarDays style={{ width: 18, height: 18, color: "#4f46e5" }} />
        <span style={{ fontSize: 13, fontWeight: 600, color: "#4f46e5" }}>AI 일정 추천</span>
      </div>

      {/* Multi-date: show per-date availability */}
      {isMultiDate && (
        <div style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13, color: "#475569" }}>
          {Object.entries(dateGroups).map(([dateKey, opts]) => {
            const dateLabel = opts[0].label.split(")")[0] + ")";
            const isBestDate = best.start_at.startsWith(dateKey);
            return (
              <div key={dateKey} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ fontWeight: isBestDate ? 700 : 400, color: isBestDate ? "#1e293b" : "#64748b" }}>
                  {dateLabel}
                </span>
                {headcount && (
                  <span style={{
                    fontSize: 11, padding: "2px 6px", borderRadius: 6,
                    background: "#dcfce7", color: "#166534", fontWeight: 600,
                  }}>
                    {headcount}명 가능
                  </span>
                )}
                {isBestDate && (
                  <span style={{ fontSize: 11, color: "#4f46e5", fontWeight: 600 }}>추천</span>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Best recommendation */}
      <div style={{
        padding: "12px 14px", borderRadius: 12,
        background: selectedSlotId === best.slot_id ? "#eef2ff" : "#ffffff",
        border: selectedSlotId === best.slot_id ? "1.5px solid #4f46e5" : "1px solid #e2e8f0",
        cursor: "pointer",
      }} onClick={() => setSelectedSlotId(best.slot_id)}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span style={{ fontSize: 15, fontWeight: 700, color: "#1e293b" }}>{best.label}</span>
          <span style={{
            fontSize: 11, padding: "3px 8px", borderRadius: 8,
            background: "#4f46e5", color: "#fff", fontWeight: 600,
          }}>
            추천
          </span>
        </div>
        {best.is_holiday && (
          <span style={{ fontSize: 11, color: "#dc2626", fontWeight: 600 }}>{best.holiday_name || "공휴일"}</span>
        )}
        {best.is_weekend && !best.is_holiday && (
          <span style={{ fontSize: 11, color: "#2563eb", fontWeight: 600 }}>주말</span>
        )}
      </div>

      {/* Alternatives toggle */}
      {alternatives.length > 0 && (
        <>
          <button
            onClick={() => setShowAlternatives((v) => !v)}
            style={{
              display: "flex", alignItems: "center", gap: 4,
              background: "transparent", border: "none", cursor: "pointer",
              color: "#64748b", fontSize: 12, fontWeight: 500, padding: 0,
            }}
          >
            다른 시간 {alternatives.length}개
            {showAlternatives
              ? <ChevronUp style={{ width: 14, height: 14 }} />
              : <ChevronDown style={{ width: 14, height: 14 }} />
            }
          </button>
          {showAlternatives && (
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {alternatives.map((opt) => (
                <div
                  key={opt.slot_id}
                  onClick={() => setSelectedSlotId(opt.slot_id)}
                  style={{
                    padding: "10px 12px", borderRadius: 10,
                    background: selectedSlotId === opt.slot_id ? "#eef2ff" : "#ffffff",
                    border: selectedSlotId === opt.slot_id ? "1.5px solid #4f46e5" : "1px solid #e2e8f0",
                    cursor: "pointer", fontSize: 14, fontWeight: 500, color: "#334155",
                  }}
                >
                  {opt.label}
                  {opt.is_holiday && <span style={{ marginLeft: 6, fontSize: 11, color: "#dc2626" }}>{opt.holiday_name || "공휴일"}</span>}
                  {opt.is_weekend && !opt.is_holiday && <span style={{ marginLeft: 6, fontSize: 11, color: "#2563eb" }}>주말</span>}
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* Action button */}
      <button
        onClick={handleConfirm}
        disabled={!selectedSlotId || isConfirming}
        style={{
          width: "100%", padding: "11px 14px", borderRadius: 12, border: "none",
          background: !selectedSlotId || isConfirming ? "#cbd5e1" : "#4f46e5",
          color: "#fff", fontSize: 14, fontWeight: 700, cursor: !selectedSlotId || isConfirming ? "not-allowed" : "pointer",
          fontFamily: "Pretendard Variable, Pretendard, sans-serif",
        }}
      >
        {isConfirming ? "확정 중..." : selectedSlot ? `${selectedSlot.label}로 확정` : "시간을 선택해주세요"}
      </button>
      {error && <span style={{ fontSize: 12, color: "#dc2626", fontWeight: 500 }}>{error}</span>}
    </div>
  );
}
