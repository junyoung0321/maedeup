"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { CalendarDays, MapPin, Users, CheckCircle2, ChevronDown, ChevronUp } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { useMeeting } from "@/contexts/MeetingContext";
import type { PlaceResult } from "@/types";

function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

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

interface VoteCardSectionProps {
  mode?: "all" | "vote-only" | "place-only";
}

export default function VoteCardSection({ mode = "all" }: VoteCardSectionProps) {
  const {
    voteCard,
    voteUpdate,
    placeRecommendation,
    roomId,
    refreshCalendar,
    setSelectedPlace,
    setContextMode,
  } = useMeeting();

  // Schedule vote state
  const [selectedSlotId, setSelectedSlotId] = useState<string | null>(null);
  const [votedOptionIndex, setVotedOptionIndex] = useState<number | null>(null);
  const [voteCounts, setVoteCounts] = useState<Record<string, number>>({});
  const [totalVoters, setTotalVoters] = useState(0);
  const [isVoting, setIsVoting] = useState(false);
  const [voteError, setVoteError] = useState<string | null>(null);
  const [isConfirmingSchedule, setIsConfirmingSchedule] = useState(false);
  const [isScheduleConfirmed, setIsScheduleConfirmed] = useState(false);
  const [scheduleConfirmError, setScheduleConfirmError] = useState<string | null>(null);
  const [confirmedMeetingId, setConfirmedMeetingId] = useState<number | null>(null);
  const [confirmedSlot, setConfirmedSlot] = useState<{ label: string; start_at: string; end_at: string } | null>(null);

  // Place vote state
  const [selectedPlaceId, setSelectedPlaceId] = useState<string | null>(null);
  const [confirmedPlace, setConfirmedPlace] = useState<{ name: string; address: string } | null>(null);
  const [isConfirmingPlace, setIsConfirmingPlace] = useState(false);
  const [isPlaceConfirmed, setIsPlaceConfirmed] = useState(false);
  const [placeConfirmError, setPlaceConfirmError] = useState<string | null>(null);

  // 방장 판정: GET /rooms/{id}로 created_by 조회 후 JWT sub와 비교.
  const [hostUserId, setHostUserId] = useState<number | null>(null);
  const currentUserId = useMemo(() => getCurrentUserIdFromToken(), []);
  const isHost = currentUserId !== null && hostUserId === currentUserId;
  const [showConfirmPopup, setShowConfirmPopup] = useState(false);
  const [pendingPlaceId, setPendingPlaceId] = useState<string | null>(null);
  const [placeCollapsed, setPlaceCollapsed] = useState(false);

  useEffect(() => {
    if (!roomId) return;
    let cancelled = false;
    apiFetch<{ created_by: number }>(`/api/v1/rooms/${roomId}`)
      .then((room) => {
        if (!cancelled) setHostUserId(room.created_by);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [roomId]);

  const activeMeetingId = confirmedMeetingId ?? voteCard?.meeting_id ?? null;

  // Reset schedule state when new vote card arrives
  useEffect(() => {
    if (!voteCard) return;
    setSelectedSlotId(voteCard.time_options[0]?.slot_id ?? null);
    setIsScheduleConfirmed(false);
    setScheduleConfirmError(null);
    setIsConfirmingSchedule(false);
    setConfirmedMeetingId(voteCard.meeting_id ?? null);
    setConfirmedSlot(null);
    setVotedOptionIndex(null);
    setVoteCounts({});
    setTotalVoters(0);
    setIsVoting(false);
    setVoteError(null);
  }, [voteCard]);

  // Sync vote updates
  useEffect(() => {
    if (!voteUpdate) return;
    if (activeMeetingId !== null && voteUpdate.meeting_id !== activeMeetingId) return;
    setVoteCounts(voteUpdate.votes);
    setTotalVoters(voteUpdate.total_voters);
    setVoteError(null);
  }, [activeMeetingId, voteUpdate]);

  // Reset place state when new recommendation arrives
  useEffect(() => {
    setSelectedPlaceId(null);
    setConfirmedPlace(null);
    setIsPlaceConfirmed(false);
    setPlaceConfirmError(null);
    setIsConfirmingPlace(false);
  }, [placeRecommendation]);

  const handleVote = useCallback(async (optionIndex: number) => {
    if (!activeMeetingId || votedOptionIndex !== null) return;
    setIsVoting(true);
    setVoteError(null);
    try {
      const result = await apiFetch<{
        meeting_id: number;
        votes: Record<string, number>;
        total_voters: number;
        selected_option_index: number;
      }>(`/api/v1/meetings/${activeMeetingId}/vote`, {
        method: "POST",
        body: JSON.stringify({ option_index: optionIndex }),
      });
      setConfirmedMeetingId(result.meeting_id);
      setVotedOptionIndex(result.selected_option_index);
      setVoteCounts(result.votes);
      setTotalVoters(result.total_voters);
    } catch (error) {
      setVoteError(getErrorMessage(error, "투표에 실패했습니다."));
    } finally {
      setIsVoting(false);
    }
  }, [activeMeetingId, votedOptionIndex]);

  const handleConfirmSchedule = useCallback(async () => {
    if (!voteCard || !selectedSlotId) return;
    const selectedSlot = voteCard.time_options.find((o) => o.slot_id === selectedSlotId);
    if (!selectedSlot) {
      setScheduleConfirmError("선택한 일정 정보를 찾을 수 없습니다.");
      return;
    }
    const parsedRoomId = Number.parseInt(roomId, 10);
    if (Number.isNaN(parsedRoomId)) {
      setScheduleConfirmError("방 정보를 확인할 수 없습니다.");
      return;
    }
    setIsConfirmingSchedule(true);
    setScheduleConfirmError(null);
    try {
      const result = await apiFetch<{ id: number }>("/api/v1/meetings/confirm", {
        method: "POST",
        body: JSON.stringify({
          room_id: parsedRoomId,
          title: voteCard.title,
          scheduled_at: selectedSlot.start_at,
          end_at: selectedSlot.end_at,
          location_name: null,
          // Eng review fix: attach meeting_id so the backend promotes the
          // existing pending MeetingSchedule instead of creating a fresh one.
          meeting_id: activeMeetingId ?? undefined,
          vote_options: voteCard.time_options.map((o) => ({
            slot_id: o.slot_id,
            label: o.label,
            start_at: o.start_at,
            end_at: o.end_at,
          })),
        }),
      });
      setConfirmedMeetingId(result.id);
      setConfirmedSlot({ label: selectedSlot.label, start_at: selectedSlot.start_at, end_at: selectedSlot.end_at });
      setIsScheduleConfirmed(true);
      refreshCalendar();
      // 장소도 이미 확정되어 있으면 → 2초 후 생성완료
      if (isPlaceConfirmed) {
        setTimeout(() => setContextMode("done"), 2000);
      }
    } catch (error) {
      setScheduleConfirmError(getErrorMessage(error, "일정 확정에 실패했습니다."));
    } finally {
      setIsConfirmingSchedule(false);
    }
  }, [voteCard, selectedSlotId, roomId, refreshCalendar]);

  const handleConfirmPlace = useCallback(async (placeId: string) => {
    if (!placeRecommendation) return;
    const place = placeRecommendation.recommendations.find((item) => item.place_id === placeId);
    if (!place) {
      setPlaceConfirmError("선택한 장소 정보를 찾을 수 없습니다.");
      return;
    }

    // meetingId가 없으면 (아직 일정 미확정) 장소 상세 보기로 전환
    if (!confirmedMeetingId) {
      handlePlaceClick(place);
      return;
    }

    setSelectedPlaceId(placeId);
    setIsConfirmingPlace(true);
    setPlaceConfirmError(null);
    try {
      await apiFetch<{ id: number }>(`/api/v1/meetings/${confirmedMeetingId}/place`, {
        method: "PATCH",
        body: JSON.stringify({
          place_id: place.place_id,
          name: place.name,
          address: place.address,
          url: place.url,
        }),
      });
      setConfirmedPlace({ name: place.name, address: place.address });
      setIsPlaceConfirmed(true);
      // 일정 + 장소 둘 다 확정 → 2초 후 생성완료 페이지로 이동
      if (isScheduleConfirmed) {
        setTimeout(() => setContextMode("done"), 2000);
      }
    } catch (error) {
      setPlaceConfirmError(getErrorMessage(error, "장소 확정에 실패했습니다."));
      setSelectedPlaceId(null);
    } finally {
      setIsConfirmingPlace(false);
    }
  }, [placeRecommendation, confirmedMeetingId]);

  const handlePlaceClick = useCallback((place: { place_id: string; name: string; address: string; phone?: string; url: string; x?: string; y?: string; category: string; distance_m?: number; score: number }) => {
    const placeResult: PlaceResult = {
      id: place.place_id,
      name: place.name,
      address: place.address,
      phone: place.phone ?? "",
      url: place.url,
      x: place.x ?? "",
      y: place.y ?? "",
      category: place.category,
      distance_m: place.distance_m,
      score: place.score,
    };
    setSelectedPlace(placeResult);
    setContextMode("place");
  }, [setSelectedPlace, setContextMode]);

  const showVote = mode !== "place-only" && !!voteCard;
  const showPlace = mode !== "vote-only" && !!placeRecommendation;

  if (!showVote && !showPlace) return null;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 14,
        padding: "0 4px",
        fontFamily: "Pretendard Variable, Pretendard, sans-serif",
      }}
    >
      {/* Schedule Vote Card */}
      {showVote && (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 14,
            padding: 18,
            borderRadius: 18,
            background: "#f1f5f9",
            border: "1px solid #cbd5e1",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: 14,
                background: "#e0e7ff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <CalendarDays style={{ width: 20, height: 20, color: "#4f46e5" }} />
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: "#4f46e5" }}>투표 카드</span>
              <span style={{ fontSize: 17, fontWeight: 700, color: "#1e293b" }}>{voteCard.title}</span>
            </div>
          </div>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "8px 12px",
              borderRadius: 14,
              background: "#ffffff",
              border: "1px solid #e2e8f0",
            }}
          >
            <Users style={{ width: 16, height: 16, color: "#4f46e5" }} />
            <span style={{ fontSize: 13, fontWeight: 500, color: "#1e293b" }}>
              총 {voteCard.headcount ?? "-"}명 기준
            </span>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {voteCard.time_options.map((option, optionIndex) => {
              const isSelected = selectedSlotId === option.slot_id;
              const optionVotes = voteCounts[String(optionIndex)] ?? 0;
              const isVoteDisabled = !activeMeetingId || votedOptionIndex !== null || isVoting;
              return (
                <div
                  key={option.slot_id}
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: 8,
                    padding: "12px 14px",
                    borderRadius: 14,
                    border: isSelected ? "1.5px solid #4f46e5" : "1px solid #cbd5e1",
                    background: isSelected ? "#eef2ff" : "#ffffff",
                  }}
                >
                  <button
                    onClick={() => setSelectedSlotId(option.slot_id)}
                    style={{
                      width: "100%",
                      textAlign: "left",
                      border: "none",
                      background: "transparent",
                      color: "#1e293b",
                      cursor: "pointer",
                      fontFamily: "Pretendard Variable, Pretendard, sans-serif",
                      fontSize: 14,
                      fontWeight: isSelected ? 600 : 500,
                      padding: 0,
                    }}
                  >
                    <span>{option.label}</span>
                    {option.is_holiday && (
                      <span style={{ marginLeft: 6, padding: "2px 6px", borderRadius: 6, background: "#fef2f2", color: "#dc2626", fontSize: 11, fontWeight: 600 }}>
                        {option.holiday_name || "공휴일"}
                      </span>
                    )}
                    {option.is_weekend && !option.is_holiday && (
                      <span style={{ marginLeft: 6, padding: "2px 6px", borderRadius: 6, background: "#eff6ff", color: "#2563eb", fontSize: 11, fontWeight: 600 }}>
                        주말
                      </span>
                    )}
                    <span style={{ marginLeft: 6, color: "#94a3b8", fontSize: 12 }}>
                      ({optionVotes}표 / {totalVoters > 0 ? `${totalVoters}명` : "투표 중"})
                    </span>
                  </button>
                  <button
                    onClick={() => handleVote(optionIndex)}
                    disabled={isVoteDisabled}
                    style={{
                      padding: "7px 12px",
                      borderRadius: 10,
                      border: "none",
                      background: isVoteDisabled ? "#cbd5e1" : "#4f46e5",
                      color: "#ffffff",
                      fontSize: 13,
                      fontWeight: 600,
                      cursor: isVoteDisabled ? "not-allowed" : "pointer",
                      alignSelf: "flex-start",
                      fontFamily: "Pretendard Variable, Pretendard, sans-serif",
                    }}
                  >
                    {votedOptionIndex === optionIndex ? "투표 완료" : "투표하기"}
                  </button>
                </div>
              );
            })}
          </div>

          {/* Confirm / status */}
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {isScheduleConfirmed ? (
              <div style={{ padding: "10px 14px", borderRadius: 14, background: "#ecfdf5", border: "1px solid #86efac", color: "#166534", fontSize: 14, fontWeight: 700 }}>
                ✓ 일정이 확정되었습니다
              </div>
            ) : votedOptionIndex !== null ? (
              isHost ? (
                <button
                  onClick={() => setShowConfirmPopup(true)}
                  disabled={selectedSlotId === null || isConfirmingSchedule}
                  style={{
                    width: "100%",
                    padding: "12px 14px",
                    borderRadius: 14,
                    border: "none",
                    background: selectedSlotId === null || isConfirmingSchedule ? "#cbd5e1" : "#4f46e5",
                    color: "#ffffff",
                    cursor: selectedSlotId === null || isConfirmingSchedule ? "not-allowed" : "pointer",
                    fontFamily: "Pretendard Variable, Pretendard, sans-serif",
                    fontSize: 14,
                    fontWeight: 700,
                  }}
                >
                  {isConfirmingSchedule ? "확정 중..." : "일정 확정하기"}
                </button>
              ) : (
                <div
                  style={{
                    padding: "10px 14px",
                    borderRadius: 14,
                    background: "#eef2ff",
                    border: "1px solid #c7d2fe",
                    color: "#4338ca",
                    fontSize: 13,
                    fontWeight: 600,
                    textAlign: "center",
                  }}
                >
                  ⏳ 방장이 확정하기를 기다리는 중이에요
                </div>
              )
            ) : (
              <div style={{ padding: "8px 14px", borderRadius: 14, background: "#f1f5f9", color: "#64748b", fontSize: 13, fontWeight: 500, textAlign: "center" }}>
                투표 후 일정을 확정할 수 있어요
              </div>
            )}
            {scheduleConfirmError && <span style={{ fontSize: 13, fontWeight: 500, color: "#dc2626" }}>{scheduleConfirmError}</span>}
            {voteError && <span style={{ fontSize: 13, fontWeight: 500, color: "#dc2626" }}>{voteError}</span>}
          </div>

          {/* Host 확정 팝업 */}
          {showConfirmPopup && (() => {
            const selectedSlot = voteCard?.time_options.find((o) => o.slot_id === selectedSlotId);
            return (
              <div
                onClick={() => !isConfirmingSchedule && setShowConfirmPopup(false)}
                style={{
                  position: "fixed",
                  inset: 0,
                  zIndex: 100,
                  background: "rgba(0,0,0,0.4)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  padding: 20,
                }}
              >
                <div
                  onClick={(e) => e.stopPropagation()}
                  style={{
                    width: "100%",
                    maxWidth: 380,
                    background: "#ffffff",
                    borderRadius: 16,
                    padding: "24px 22px",
                    boxShadow: "0 20px 60px rgba(0,0,0,0.2)",
                    display: "flex",
                    flexDirection: "column",
                    gap: 14,
                    fontFamily: "Pretendard Variable, Pretendard, sans-serif",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <CalendarDays size={20} style={{ color: "#4f46e5" }} />
                    <h3 style={{ margin: 0, fontSize: 17, fontWeight: 700, color: "#1e1b4b" }}>
                      이 일정으로 확정할까요?
                    </h3>
                  </div>
                  <div style={{ padding: "12px 14px", background: "#f8fafc", borderRadius: 10, fontSize: 14, color: "#334155", fontWeight: 600 }}>
                    {selectedSlot?.label ?? "선택된 시간"}
                  </div>
                  <p style={{ margin: 0, fontSize: 12, color: "#64748b", lineHeight: 1.5 }}>
                    확정하면 다른 멤버에게도 알림이 가고, 되돌리려면 따로 작업이 필요해요.
                  </p>
                  <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
                    <button
                      onClick={() => setShowConfirmPopup(false)}
                      disabled={isConfirmingSchedule}
                      style={{
                        flex: 1,
                        padding: "10px 14px",
                        borderRadius: 10,
                        border: "1px solid #e2e8f0",
                        background: "#ffffff",
                        color: "#475569",
                        fontSize: 13,
                        fontWeight: 600,
                        cursor: isConfirmingSchedule ? "not-allowed" : "pointer",
                        fontFamily: "inherit",
                      }}
                    >
                      취소
                    </button>
                    <button
                      onClick={async () => {
                        await handleConfirmSchedule();
                        setShowConfirmPopup(false);
                      }}
                      disabled={isConfirmingSchedule}
                      style={{
                        flex: 1,
                        padding: "10px 14px",
                        borderRadius: 10,
                        border: "none",
                        background: isConfirmingSchedule ? "#a5b4fc" : "#4f46e5",
                        color: "#ffffff",
                        fontSize: 13,
                        fontWeight: 700,
                        cursor: isConfirmingSchedule ? "not-allowed" : "pointer",
                        fontFamily: "inherit",
                      }}
                    >
                      {isConfirmingSchedule ? "확정 중…" : "확정하기"}
                    </button>
                  </div>
                </div>
              </div>
            );
          })()}
        </div>
      )}

      {/* Place Recommendation Card */}
      {showPlace && placeRecommendation && (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 14,
            padding: 18,
            borderRadius: 18,
            background: "#f1f5f9",
            border: "1px solid #cbd5e1",
          }}
        >
          <button
            onClick={() => setPlaceCollapsed((v) => !v)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              width: "100%",
              background: "transparent",
              border: "none",
              cursor: "pointer",
              padding: 0,
              textAlign: "left",
            }}
          >
            <div style={{ width: 40, height: 40, borderRadius: 14, background: "#e0e7ff", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              <MapPin style={{ width: 20, height: 20, color: "#4f46e5" }} />
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 2, flex: 1 }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: "#4f46e5" }}>장소 추천</span>
              <span style={{ fontSize: 17, fontWeight: 700, color: "#1e293b" }}>{placeRecommendation.place_hint} 추천 장소</span>
            </div>
            {placeCollapsed
              ? <ChevronDown style={{ width: 20, height: 20, color: "#94a3b8", flexShrink: 0 }} />
              : <ChevronUp style={{ width: 20, height: 20, color: "#94a3b8", flexShrink: 0 }} />
            }
          </button>
          {!placeCollapsed && (<><div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {placeRecommendation.recommendations.map((place) => {
              const isSelected = selectedPlaceId === place.place_id;
              const distanceMeters = place.distance_m;
              return (
                <div
                  key={place.place_id}
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: 8,
                    padding: "12px 14px",
                    borderRadius: 16,
                    background: isSelected ? "#eef2ff" : "#ffffff",
                    border: isSelected ? "1.5px solid #4f46e5" : "1px solid #e2e8f0",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                    <span onClick={() => handlePlaceClick(place)} style={{ fontSize: 16, fontWeight: 700, color: "#1e293b", cursor: "pointer" }}>
                      {place.name}
                    </span>
                    <span style={{ padding: "4px 10px", borderRadius: 999, background: "#eef2ff", color: "#4f46e5", fontSize: 13, fontWeight: 700, flexShrink: 0 }}>
                      {Math.round(place.score * 100)}%
                    </span>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontSize: 13, fontWeight: 500, color: "#475569" }}>{place.category}</span>
                    {typeof distanceMeters === "number" && distanceMeters > 0 && (
                      <span style={{ fontSize: 12, color: "#94a3b8", fontWeight: 500 }}>
                        {distanceMeters >= 1000 ? `${(distanceMeters / 1000).toFixed(1)}km` : `${distanceMeters}m`}
                      </span>
                    )}
                  </div>
                  <span style={{ fontSize: 13, lineHeight: 1.5, color: "#1e293b" }}>{place.address}</span>
                  {isPlaceConfirmed && isSelected ? (
                    <div style={{ padding: "8px 12px", borderRadius: 10, background: "#ecfdf5", border: "1px solid #86efac", color: "#166534", fontSize: 13, fontWeight: 700 }}>
                      ✓ 장소가 확정되었습니다
                    </div>
                  ) : !isPlaceConfirmed && confirmedMeetingId ? (
                    isHost ? (
                      <button
                        onClick={() => setPendingPlaceId(place.place_id)}
                        disabled={isConfirmingPlace}
                        style={{
                          padding: "7px 12px",
                          borderRadius: 10,
                          border: "none",
                          background: isConfirmingPlace && isSelected ? "#cbd5e1" : "#4f46e5",
                          color: "#ffffff",
                          fontSize: 13,
                          fontWeight: 600,
                          cursor: isConfirmingPlace ? "not-allowed" : "pointer",
                          alignSelf: "flex-start",
                          fontFamily: "Pretendard Variable, Pretendard, sans-serif",
                        }}
                      >
                        {isConfirmingPlace && isSelected ? "확정 중..." : "이 장소로 확정"}
                      </button>
                    ) : (
                      <span style={{ fontSize: 12, color: "#6366f1", fontWeight: 600, alignSelf: "flex-start" }}>
                        ⏳ 방장이 확정하기를 기다리는 중이에요
                      </span>
                    )
                  ) : !isPlaceConfirmed && !confirmedMeetingId ? (
                    <span style={{ fontSize: 12, color: "#94a3b8", fontStyle: "italic" }}>
                      일정을 먼저 확정하면 장소를 선택할 수 있어요
                    </span>
                  ) : null}
                </div>
              );
            })}
          </div>
          {placeConfirmError && <span style={{ fontSize: 13, fontWeight: 500, color: "#dc2626" }}>{placeConfirmError}</span>}
          </>)}

          {/* Host 장소 확정 팝업 */}
          {pendingPlaceId && (() => {
            const pendingPlace = placeRecommendation?.recommendations.find((p) => p.place_id === pendingPlaceId);
            return (
              <div
                onClick={() => !isConfirmingPlace && setPendingPlaceId(null)}
                style={{
                  position: "fixed",
                  inset: 0,
                  zIndex: 100,
                  background: "rgba(0,0,0,0.4)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  padding: 20,
                }}
              >
                <div
                  onClick={(e) => e.stopPropagation()}
                  style={{
                    width: "100%",
                    maxWidth: 380,
                    background: "#ffffff",
                    borderRadius: 16,
                    padding: "24px 22px",
                    boxShadow: "0 20px 60px rgba(0,0,0,0.2)",
                    display: "flex",
                    flexDirection: "column",
                    gap: 14,
                    fontFamily: "Pretendard Variable, Pretendard, sans-serif",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <MapPin size={20} style={{ color: "#4f46e5" }} />
                    <h3 style={{ margin: 0, fontSize: 17, fontWeight: 700, color: "#1e1b4b" }}>
                      이 장소로 확정할까요?
                    </h3>
                  </div>
                  <div style={{ padding: "12px 14px", background: "#f8fafc", borderRadius: 10, display: "flex", flexDirection: "column", gap: 4 }}>
                    <span style={{ fontSize: 14, color: "#1e293b", fontWeight: 700 }}>
                      {pendingPlace?.name ?? "선택된 장소"}
                    </span>
                    {pendingPlace?.address && (
                      <span style={{ fontSize: 12, color: "#64748b" }}>{pendingPlace.address}</span>
                    )}
                  </div>
                  <p style={{ margin: 0, fontSize: 12, color: "#64748b", lineHeight: 1.5 }}>
                    확정하면 다른 멤버에게도 알림이 가고, 되돌리려면 따로 작업이 필요해요.
                  </p>
                  <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
                    <button
                      onClick={() => setPendingPlaceId(null)}
                      disabled={isConfirmingPlace}
                      style={{
                        flex: 1,
                        padding: "10px 14px",
                        borderRadius: 10,
                        border: "1px solid #e2e8f0",
                        background: "#ffffff",
                        color: "#475569",
                        fontSize: 13,
                        fontWeight: 600,
                        cursor: isConfirmingPlace ? "not-allowed" : "pointer",
                        fontFamily: "inherit",
                      }}
                    >
                      취소
                    </button>
                    <button
                      onClick={async () => {
                        const id = pendingPlaceId;
                        if (!id) return;
                        await handleConfirmPlace(id);
                        setPendingPlaceId(null);
                      }}
                      disabled={isConfirmingPlace}
                      style={{
                        flex: 1,
                        padding: "10px 14px",
                        borderRadius: 10,
                        border: "none",
                        background: isConfirmingPlace ? "#a5b4fc" : "#4f46e5",
                        color: "#ffffff",
                        fontSize: 13,
                        fontWeight: 700,
                        cursor: isConfirmingPlace ? "not-allowed" : "pointer",
                        fontFamily: "inherit",
                      }}
                    >
                      {isConfirmingPlace ? "확정 중…" : "확정하기"}
                    </button>
                  </div>
                </div>
              </div>
            );
          })()}
        </div>
      )}
    </div>
  );
}
