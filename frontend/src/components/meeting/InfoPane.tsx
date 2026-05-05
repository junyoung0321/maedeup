"use client";

import { useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronDown, ChevronUp, CalendarDays } from "lucide-react";
import CalendarPane from "@/components/meeting/CalendarPane";
import FinalizationProposalCard from "@/components/meeting/FinalizationProposalCard";
import PlaceDetailPane from "@/components/meeting/PlaceDetailPane";
import VoteCardSection from "@/components/meeting/VoteCardSection";
import TimeBarSelector from "@/components/meeting/TimeBarSelector";
import { useMeeting } from "@/contexts/MeetingContext";
import { fs } from "@/lib/responsive";
import type { PlaceResult } from "@/types";

// Removed fixed dimensions — uses flex layout from parent

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

export default function InfoPane() {
  const {
    selectedPlace,
    setSelectedPlace,
    roomId,
    voteCard,
    placeRecommendation,
    infoPanePhase,
    confirmedDate,
    confirmedMeetingId,
    setContextMode,
    confirmDate,
    confirmTime,
    confirmPlace,
    setInfoPanePhase,
    sendMessageToAi,
    refreshCalendar,
    finalizationProposal,
    finalizationPending,
    calendarEventForSelf,
    calendarMemberCount,
    setCalendarSyncStatus,
  } = useMeeting();

  const currentUserId = useMemo(() => getCurrentUserIdFromToken(), []);

  const [calendarCollapsed, setCalendarCollapsed] = useState(false);

  const hasSelectedPlace = selectedPlace !== null;
  // Non-phased flow: place-only (no vote card, just place recommendation, not manually started)
  const isPlaceOnlyFlow = !voteCard && placeRecommendation !== null && infoPanePhase === "idle";
  // Phased flow: vote card present OR user manually started the flow
  const isPhasedFlow = voteCard !== null || infoPanePhase !== "idle";

  const handlePlaceClick = (place: PlaceResult) => {
    setSelectedPlace(place);
    setContextMode("place");
  };

  const handleTimeConfirm = async (startAt: string, endAt: string) => {
    // Call /meetings/confirm to promote pending meeting
    const { apiFetch } = await import("@/lib/api");
    const parsedRoomId = Number.parseInt(roomId, 10);
    if (Number.isNaN(parsedRoomId)) return;

    try {
      const result = await apiFetch<{
        id: number;
        calendar_event_for_self?: boolean;
        calendar_member_count?: number;
      }>("/api/v1/meetings/confirm", {
        method: "POST",
        body: JSON.stringify({
          room_id: parsedRoomId,
          title: voteCard?.title ?? "모임",
          scheduled_at: startAt,
          end_at: endAt,
          location_name: null,
          vote_options: voteCard?.time_options?.map((o) => ({
            slot_id: o.slot_id,
            label: o.label,
            start_at: o.start_at,
            end_at: o.end_at,
          })) ?? [],
          meeting_id: confirmedMeetingId ?? undefined,
        }),
      });
      confirmTime(startAt, endAt, result.id);
      setCalendarSyncStatus(
        result.calendar_event_for_self ?? false,
        result.calendar_member_count ?? 0,
      );
      refreshCalendar();
    } catch (error) {
      console.error("Failed to confirm meeting:", error);
    }
  };

  const handlePlaceConfirmed = () => {
    confirmPlace();
    setTimeout(() => setContextMode("done"), 2000);
  };

  const handleFinalizationConfirm = async (
    proposalId: string,
    slot: { start_at: string; end_at: string; label: string },
  ) => {
    const { apiFetch } = await import("@/lib/api");
    const parsedRoomId = Number.parseInt(roomId, 10);
    if (Number.isNaN(parsedRoomId)) return;
    const result = await apiFetch<{
      id: number;
      calendar_event_for_self?: boolean;
      calendar_member_count?: number;
    }>("/api/v1/meetings/confirm", {
      method: "POST",
      body: JSON.stringify({
        room_id: parsedRoomId,
        title: slot.label,
        scheduled_at: slot.start_at,
        end_at: slot.end_at,
        proposal_id: proposalId,
      }),
    });
    confirmTime(slot.start_at, slot.end_at, result.id);
    setCalendarSyncStatus(
      result.calendar_event_for_self ?? false,
      result.calendar_member_count ?? 0,
    );
    refreshCalendar();
  };

  return (
    <div
      style={{
        flex: 1,
        minWidth: 0,
        display: "flex",
        flexDirection: "column",
        overflowY: "auto",
        overflowX: "hidden",
        borderRadius: 20,
        border: "1px solid #e2e8f0",
        boxShadow: "0 4px 3.5px rgba(0,0,0,0.25)",
        background: "#f8fafc",
      }}
    >
      {/* Place detail view (from place click) */}
      {hasSelectedPlace ? (
        <>
          <div style={{ padding: "8px 0" }}>
            <button
              onClick={() => setSelectedPlace(null)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 4,
                padding: "8px 16px",
                margin: "0 8px 8px",
                border: "none",
                background: "transparent",
                color: "#4f46e5",
                fontSize: fs(14, 12),
                fontWeight: 500,
                cursor: "pointer",
                fontFamily: "Pretendard Variable, Pretendard, sans-serif",
              }}
            >
              <ChevronLeft style={{ width: 16, height: 16 }} />
              돌아가기
            </button>
            <PlaceDetailPane
              place={selectedPlace}
              roomId={roomId}
              meetingId={confirmedMeetingId}
              onConfirmed={() => {
                handlePlaceConfirmed();
                setSelectedPlace(null);
              }}
            />
          </div>
        </>
      ) : (
        <>
          {/* Calendar — collapsible. 장소 카드가 뜨면 기본 접힘. */}
          <div style={{ margin: "0 4px" }}>
            <button
              type="button"
              onClick={() => setCalendarCollapsed((v) => !v)}
              style={{
                width: "100%",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "8px 14px",
                borderRadius: 12,
                border: "1px solid #e2e8f0",
                background: "#f8fafc",
                cursor: "pointer",
                marginBottom: calendarCollapsed ? 0 : 8,
                fontFamily: "Pretendard Variable, Pretendard, sans-serif",
              }}
              aria-expanded={!calendarCollapsed}
              aria-label={calendarCollapsed ? "캘린더 펼치기" : "캘린더 접기"}
            >
              <span style={{ display: "flex", alignItems: "center", gap: 8, color: "#334155", fontSize: fs(13, 11), fontWeight: 600 }}>
                <CalendarDays style={{ width: 16, height: 16 }} />
                캘린더
              </span>
              {calendarCollapsed ? (
                <ChevronDown style={{ width: 16, height: 16, color: "#64748b" }} />
              ) : (
                <ChevronUp style={{ width: 16, height: 16, color: "#64748b" }} />
              )}
            </button>
            {!calendarCollapsed && <CalendarPane />}
          </div>

          {/* Phase-based content below calendar */}
          {isPhasedFlow ? (
            <div style={{ padding: "8px 0" }}>
              {/* Phase: idle → 날짜 선택 안내 */}
              {infoPanePhase === "idle" && voteCard && (
                <div style={{
                  padding: "16px 18px",
                  margin: "0 4px",
                  borderRadius: 18,
                  background: "#eef2ff",
                  border: "1px solid #c7d2fe",
                  textAlign: "center",
                  fontFamily: "Pretendard Variable, Pretendard, sans-serif",
                }}>
                  <div style={{ fontSize: fs(15, 12), fontWeight: 700, color: "#4f46e5", marginBottom: 6 }}>
                    {voteCard.title}
                  </div>
                  <div style={{ fontSize: fs(13, 11), color: "#475569" }}>
                    캘린더에서 파란 테두리 날짜를 클릭해서 날짜를 선택하세요
                  </div>
                  <div style={{ fontSize: fs(12, 10.5), color: "#94a3b8", marginTop: 4 }}>
                    {voteCard.headcount}명 기준 · {voteCard.time_options.length}개 날짜 추천
                  </div>
                </div>
              )}

              {/* Phase: dateSelected → CalendarPane의 DateCard가 보여줌 (여기서 추가 UI 불필요) */}

              {/* Phase: dateConfirmed → TimeBarSelector */}
              {infoPanePhase === "dateConfirmed" && confirmedDate && (
                <div style={{ padding: "0 4px" }}>
                  <TimeBarSelector
                    date={confirmedDate}
                    roomId={roomId}
                    onConfirm={handleTimeConfirm}
                    onBack={() => setInfoPanePhase("dateSelected")}
                  />
                </div>
              )}

              {/* Phase: timeConfirmed → 장소 추천 카드는 AI 패널에만 렌더.
                  여기서 카드 중복 렌더 제거. 사용자가 AI 패널 카드의 장소명 클릭 시
                  setSelectedPlace 호출 → 위쪽 PlaceDetailPane이 자동 열림. */}

              {/* Phase: placeConfirmed/done */}
              {(infoPanePhase === "placeConfirmed" || infoPanePhase === "done") && (
                <div style={{
                  padding: "24px 18px",
                  margin: "0 4px",
                  borderRadius: 18,
                  background: "#ecfdf5",
                  border: "1px solid #86efac",
                  textAlign: "center",
                  fontFamily: "Pretendard Variable, Pretendard, sans-serif",
                }}>
                  <div style={{ fontSize: fs(16, 13), fontWeight: 700, color: "#166534" }}>
                    ✓ 모임이 확정되었습니다!
                  </div>
                  {calendarEventForSelf === true && (
                    <div style={{
                      marginTop: 8,
                      fontSize: fs(13, 11),
                      color: "#047857",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: 6,
                    }}>
                      <CalendarDays size={fs(14, 12)} strokeWidth={2} />
                      <span>
                        내 구글 캘린더에 추가됨
                        {calendarMemberCount > 1 && ` · 참여자 ${calendarMemberCount}명`}
                      </span>
                    </div>
                  )}
                  {calendarEventForSelf === false && (
                    <div style={{
                      marginTop: 8,
                      fontSize: fs(12, 10),
                      color: "#6b7280",
                    }}>
                      구글 캘린더 연동을 켜면 다음 모임부터 자동 추가됩니다
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : null}
          {/* Non-phased place-only 카드도 AI 패널에서만 렌더. InfoPane은 calendar+detail만. */}
        </>
      )}
    </div>
  );
}
