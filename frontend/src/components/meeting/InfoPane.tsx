"use client";

import { ChevronLeft } from "lucide-react";
import CalendarPane from "@/components/meeting/CalendarPane";
import PlaceDetailPane from "@/components/meeting/PlaceDetailPane";
import VoteCardSection from "@/components/meeting/VoteCardSection";
import PlaceRecommendationCard from "@/components/meeting/PlaceRecommendationCard";
import TimeBarSelector from "@/components/meeting/TimeBarSelector";
import { useMeeting } from "@/contexts/MeetingContext";
import { fs } from "@/lib/responsive";
import type { PlaceResult } from "@/types";

// Removed fixed dimensions — uses flex layout from parent

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
  } = useMeeting();

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
      const result = await apiFetch<{ id: number }>("/api/v1/meetings/confirm", {
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
      refreshCalendar();
      // Auto-trigger place recommendation
      if (sendMessageToAi) {
        sendMessageToAi("일정이 확정되었습니다. 장소를 추천해주세요");
      }
    } catch (error) {
      console.error("Failed to confirm meeting:", error);
    }
  };

  const handlePlaceConfirmed = () => {
    confirmPlace();
    setTimeout(() => setContextMode("done"), 2000);
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
          {/* Calendar always on top */}
          <CalendarPane />

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

              {/* Phase: timeConfirmed → PlaceRecommendationCard (or waiting) */}
              {infoPanePhase === "timeConfirmed" && (
                <div style={{ padding: "0 4px" }}>
                  {placeRecommendation ? (
                    <PlaceRecommendationCard
                      placeRecommendation={placeRecommendation}
                      meetingId={confirmedMeetingId}
                      roomId={roomId}
                      onPlaceConfirmed={handlePlaceConfirmed}
                      onPlaceClick={handlePlaceClick}
                    />
                  ) : (
                    <div style={{
                      padding: "24px 18px",
                      borderRadius: 18,
                      background: "#f1f5f9",
                      border: "1px solid #cbd5e1",
                      textAlign: "center",
                      fontFamily: "Pretendard Variable, Pretendard, sans-serif",
                    }}>
                      <div style={{ fontSize: fs(14, 12), fontWeight: 600, color: "#4f46e5", marginBottom: 8 }}>
                        장소 추천 대기 중...
                      </div>
                      <div style={{ fontSize: fs(13, 11), color: "#64748b" }}>
                        AI가 장소를 찾고 있어요
                      </div>
                    </div>
                  )}
                </div>
              )}

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
                </div>
              )}
            </div>
          ) : isPlaceOnlyFlow ? (
            /* Non-phased: place-only flow */
            <div style={{ padding: "8px 0" }}>
              <VoteCardSection />
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}
