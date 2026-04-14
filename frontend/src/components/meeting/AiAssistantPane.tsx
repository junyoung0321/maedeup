"use client";

import { useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { Sparkles, Send, Square, MessageCircle, CalendarDays, MapPin, Users, CheckCircle2, ClipboardList } from "lucide-react";
import { useAgentWebSocket } from "@/hooks/useAgentWebSocket";
import { useAuth } from "@/hooks/useAuth";
import { MeetingContext } from "@/contexts/MeetingContext";
import { apiFetch } from "@/lib/api";
import type { ContextMode } from "@/types";

const PANE_TYPE_MAP: Record<string, ContextMode> = {
  schedule: "schedule",
  place: "place",
  done: "done",
  agent: "agent",
};

function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

export default function AiAssistantPane() {
  const [input, setInput] = useState("");
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
  const [selectedPlaceId, setSelectedPlaceId] = useState<string | null>(null);
  const [confirmedPlace, setConfirmedPlace] = useState<{ name: string; address: string } | null>(null);
  const [isConfirmingPlace, setIsConfirmingPlace] = useState(false);
  const [isPlaceConfirmed, setIsPlaceConfirmed] = useState(false);
  const [placeConfirmError, setPlaceConfirmError] = useState<string | null>(null);
  const [isAiLoading, setIsAiLoading] = useState(false);
  const aiLoadingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const { user } = useAuth();
  const meetingContext = useContext(MeetingContext);

  const roomId = meetingContext?.roomId?.trim() || "1";
  const setContextMode = meetingContext?.setContextMode;
  const setSelectedPlace = meetingContext?.setSelectedPlace;
  const aiTriggerIntent = meetingContext?.aiTriggerIntent ?? null;
  const setAiTriggerIntent = meetingContext?.setAiTriggerIntent;
  const refreshCalendar = meetingContext?.refreshCalendar;

  const handlePaneSwitch = useCallback(
    (paneType: string) => {
      const mode = PANE_TYPE_MAP[paneType];
      if (mode && setContextMode) {
        setContextMode(mode);
      }
    },
    [setContextMode],
  );

  const websocketOptions = useMemo(
    () => ({ onPaneSwitch: handlePaneSwitch }),
    [handlePaneSwitch],
  );

  const {
    messages,
    sendMessage,
    status,
    voteCard,
    voteUpdate,
    placeRecommendation,
    maedeupCard,
    autoTrigger,
    dismissAutoTrigger,
    meetingSummary,
  } = useAgentWebSocket(roomId, user?.name ?? "나", websocketOptions);

  const [autoTriggerBanner, setAutoTriggerBanner] = useState<string | null>(null);

  const activeMeetingId = confirmedMeetingId ?? voteCard?.meeting_id ?? null;

  useEffect(() => {
    if (voteCard) {
      refreshCalendar?.();
    }

    setSelectedSlotId(voteCard?.time_options[0]?.slot_id ?? null);
    setIsScheduleConfirmed(false);
    setScheduleConfirmError(null);
    setIsConfirmingSchedule(false);
    setConfirmedMeetingId(voteCard?.meeting_id ?? null);
    setConfirmedSlot(null);
    setVotedOptionIndex(null);
    setVoteCounts({});
    setTotalVoters(0);
    setIsVoting(false);
    setVoteError(null);
  }, [refreshCalendar, voteCard]);

  useEffect(() => {
    if (!voteUpdate) {
      return;
    }
    if (activeMeetingId !== null && voteUpdate.meeting_id !== activeMeetingId) {
      return;
    }

    setVoteCounts(voteUpdate.votes);
    setTotalVoters(voteUpdate.total_voters);
    setVoteError(null);
  }, [activeMeetingId, voteUpdate]);

  useEffect(() => {
    setSelectedPlaceId(null);
    setConfirmedPlace(null);
    setIsPlaceConfirmed(false);
    setPlaceConfirmError(null);
    setIsConfirmingPlace(false);
  }, [placeRecommendation]);

  // aiTriggerIntent는 더 이상 자동 메시지를 보내지 않음
  // 채팅방 자체가 일정 조율 목적이므로 AI가 알아서 관찰하다 개입
  useEffect(() => {
    if (aiTriggerIntent) {
      setAiTriggerIntent?.(null);
    }
  }, [aiTriggerIntent, setAiTriggerIntent]);

  // 소셜 채팅에서 AI 자동 트리거가 감지되면 배너 표시
  useEffect(() => {
    if (!autoTrigger) {
      return;
    }
    // 자동 트리거는 배너 없이 조용히 처리 (AI가 필요할 때만 응답)
    dismissAutoTrigger();
  }, [autoTrigger, dismissAutoTrigger]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, voteCard, placeRecommendation, maedeupCard, meetingSummary, isAiLoading]);

  // Set isAiLoading to false when an assistant message arrives
  useEffect(() => {
    if (messages.length > 0 && messages[messages.length - 1]?.role === "assistant") {
      setIsAiLoading(false);
      if (aiLoadingTimeoutRef.current) {
        clearTimeout(aiLoadingTimeoutRef.current);
        aiLoadingTimeoutRef.current = null;
      }
    }
  }, [messages]);

  // Reset loading when WS reconnects (don't treat connecting as loading)
  useEffect(() => {
    if (status === "open") {
      // WS 연결 완료 시, 메시지가 없으면 로딩 해제
      if (messages.length === 0) {
        setIsAiLoading(false);
      }
    }
  }, [status, messages.length]);

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (aiLoadingTimeoutRef.current) {
        clearTimeout(aiLoadingTimeoutRef.current);
      }
    };
  }, []);

  const handleStopAi = () => {
    setIsAiLoading(false);
    if (aiLoadingTimeoutRef.current) {
      clearTimeout(aiLoadingTimeoutRef.current);
      aiLoadingTimeoutRef.current = null;
    }
  };

  const handleSend = () => {
    const nextInput = input.trim();
    if (!nextInput) {
      return;
    }

    sendMessage(nextInput);
    setInput("");
    setIsAiLoading(true);

    // Auto-cancel after 30 seconds
    if (aiLoadingTimeoutRef.current) {
      clearTimeout(aiLoadingTimeoutRef.current);
    }
    aiLoadingTimeoutRef.current = setTimeout(() => {
      setIsAiLoading(false);
      aiLoadingTimeoutRef.current = null;
    }, 30_000);
  };

  const handleConfirmSchedule = async () => {
    if (!voteCard || !selectedSlotId) {
      return;
    }

    const selectedSlot = voteCard.time_options.find((option) => option.slot_id === selectedSlotId);
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
          vote_options: voteCard.time_options.map((option) => ({
            slot_id: option.slot_id,
            label: option.label,
            start_at: option.start_at,
            end_at: option.end_at,
          })),
        }),
      });

      setConfirmedMeetingId(result.id);
      setConfirmedSlot({
        label: selectedSlot.label,
        start_at: selectedSlot.start_at,
        end_at: selectedSlot.end_at,
      });
      setIsScheduleConfirmed(true);
      refreshCalendar?.();
    } catch (error) {
      setScheduleConfirmError(getErrorMessage(error, "일정 확정에 실패했습니다."));
    } finally {
      setIsConfirmingSchedule(false);
    }
  };

  const handleVote = async (optionIndex: number) => {
    if (!activeMeetingId || votedOptionIndex !== null) {
      return;
    }

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
  };

  const handleConfirmPlace = async (placeId: string) => {
    if (!placeRecommendation || !confirmedMeetingId) {
      return;
    }

    const place = placeRecommendation.recommendations.find((item) => item.place_id === placeId);
    if (!place) {
      setPlaceConfirmError("선택한 장소 정보를 찾을 수 없습니다.");
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
    } catch (error) {
      setPlaceConfirmError(getErrorMessage(error, "장소 확정에 실패했습니다."));
      setSelectedPlaceId(null);
    } finally {
      setIsConfirmingPlace(false);
    }
  };

  return (
    <div
      style={{
        width: 414,
        height: 733,
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
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "16px 20px",
          background: "linear-gradient(135deg, #837cff, #6eb3ff)",
          borderBottom: "1px solid #e2e8f0",
        }}
      >
        <Sparkles style={{ width: 20, height: 20, color: "#ffffff" }} />
        <span
          style={{
            fontSize: 26,
            fontWeight: 400,
            color: "#ffffff",
            letterSpacing: 0.75,
          }}
        >
          AI 어시스턴트
        </span>
      </div>

      {autoTriggerBanner && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "8px 16px",
            background: "linear-gradient(135deg, #4f46e5, #0891b2)",
            color: "#fff",
            fontSize: 13,
            fontWeight: 500,
            animation: "fadeIn 0.3s ease-in",
          }}
        >
          <Sparkles style={{ width: 14, height: 14 }} />
          <span style={{ flex: 1 }}>{autoTriggerBanner}</span>
          <button
            onClick={() => setAutoTriggerBanner(null)}
            style={{
              background: "none",
              border: "none",
              color: "#fff",
              cursor: "pointer",
              padding: 0,
              fontSize: 14,
              lineHeight: 1,
            }}
          >
            &times;
          </button>
        </div>
      )}

      <div
        ref={scrollRef}
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "14px 20px",
          display: "flex",
          flexDirection: "column",
          gap: 14,
        }}
      >
        {meetingSummary && (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 12,
              padding: 16,
              borderRadius: 16,
              background: "linear-gradient(135deg, #7c3aed 0%, #a855f7 50%, #c084fc 100%)",
              color: "#ffffff",
              fontFamily: "Pretendard Variable, Pretendard, sans-serif",
              boxShadow: "0 4px 14px rgba(124, 58, 237, 0.18)",
              animation: "fadeIn 0.4s ease-out",
            }}
          >
            <style>{`
              @keyframes fadeIn {
                from { opacity: 0; transform: translateY(-8px); }
                to { opacity: 1; transform: translateY(0); }
              }
              @keyframes summaryPulse {
                0%, 100% { box-shadow: 0 4px 14px rgba(124, 58, 237, 0.18); }
                50% { box-shadow: 0 6px 20px rgba(124, 58, 237, 0.3); }
              }
            `}</style>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <ClipboardList style={{ width: 18, height: 18, color: "#ffffff" }} />
              <span style={{ fontSize: 13, fontWeight: 700, color: "rgba(255,255,255,0.9)" }}>
                현재 대화 정리
              </span>
            </div>
            <div
              style={{
                display: "grid",
                gap: 8,
                padding: 14,
                borderRadius: 12,
                background: "rgba(255,255,255,0.15)",
                border: "1px solid rgba(255,255,255,0.2)",
              }}
            >
              {meetingSummary.date && (
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <CalendarDays style={{ width: 14, height: 14, color: "#e9d5ff", flexShrink: 0 }} />
                  <span style={{ fontSize: 14, fontWeight: 500 }}>
                    날짜: {meetingSummary.date}
                  </span>
                </div>
              )}
              {meetingSummary.place && (
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <MapPin style={{ width: 14, height: 14, color: "#e9d5ff", flexShrink: 0 }} />
                  <span style={{ fontSize: 14, fontWeight: 500 }}>
                    장소: {meetingSummary.place}
                  </span>
                </div>
              )}
              {meetingSummary.headcount && (
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Users style={{ width: 14, height: 14, color: "#e9d5ff", flexShrink: 0 }} />
                  <span style={{ fontSize: 14, fontWeight: 500 }}>
                    인원: {meetingSummary.headcount}
                  </span>
                </div>
              )}
              {meetingSummary.meeting_type && (
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Sparkles style={{ width: 14, height: 14, color: "#e9d5ff", flexShrink: 0 }} />
                  <span style={{ fontSize: 14, fontWeight: 500 }}>
                    유형: {meetingSummary.meeting_type}
                  </span>
                </div>
              )}
              {meetingSummary.notes && meetingSummary.notes.length > 0 && (
                <div style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 2 }}>
                  {meetingSummary.notes.map((note, i) => (
                    <span key={i} style={{ fontSize: 13, fontWeight: 400, color: "rgba(255,255,255,0.85)" }}>
                      · {note}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {messages.length === 0 && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "8px 14px",
              background: "#eef2ff",
              borderRadius: 18,
            }}
          >
            <MessageCircle style={{ width: 16, height: 16, color: "#4f46e5" }} />
            <span style={{ fontSize: 15, fontWeight: 400, color: "#4f46e5", fontFamily: "Inter, sans-serif" }}>
              AI 어시스턴트에게 모임 일정이나 장소를 물어보세요
            </span>
          </div>
        )}

        {voteCard && (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 14,
              padding: 18,
              borderRadius: 18,
              background: "#f1f5f9",
              border: "1px solid #cbd5e1",
              color: "#1e293b",
              fontFamily: "Pretendard Variable, Pretendard, sans-serif",
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
                <span style={{ fontSize: 12, fontWeight: 600, color: "#4f46e5" }}>
                  투표 카드
                </span>
                <span style={{ fontSize: 19, fontWeight: 700, color: "#1e293b" }}>
                  {voteCard.title}
                </span>
              </div>
            </div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                padding: "10px 12px",
                borderRadius: 14,
                background: "#ffffff",
                border: "1px solid #e2e8f0",
              }}
            >
              <Users style={{ width: 16, height: 16, color: "#4f46e5" }} />
              <span style={{ fontSize: 14, fontWeight: 500, color: "#1e293b" }}>
                총 {voteCard.headcount}명 기준으로 가능한 시간을 선택하세요
              </span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
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
                      gap: 10,
                      padding: "14px 16px",
                      borderRadius: 14,
                      border: isSelected ? "1.5px solid #4f46e5" : "1px solid #cbd5e1",
                      background: isSelected ? "#eef2ff" : "#ffffff",
                      boxShadow: isSelected ? "0 6px 18px rgba(79, 70, 229, 0.12)" : "none",
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
                        fontSize: 15,
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
                      <span style={{ marginLeft: 6, color: "#94a3b8", fontSize: 13 }}>
                        ({optionVotes}표 / {totalVoters > 0 ? `${totalVoters}명` : "투표 중"})
                      </span>
                    </button>
                    <button
                      onClick={() => handleVote(optionIndex)}
                      disabled={isVoteDisabled}
                      style={{
                        padding: "8px 14px",
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
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {isScheduleConfirmed ? (
                <div
                  style={{
                    padding: "12px 14px",
                    borderRadius: 14,
                    background: "#ecfdf5",
                    border: "1px solid #86efac",
                    color: "#166534",
                    fontSize: 15,
                    fontWeight: 700,
                  }}
                >
                  ✓ 일정이 확정되었습니다
                </div>
              ) : (
                <button
                  onClick={handleConfirmSchedule}
                  disabled={selectedSlotId === null || isConfirmingSchedule}
                  style={{
                    width: "100%",
                    padding: "14px 16px",
                    borderRadius: 14,
                    border: "none",
                    background: selectedSlotId === null || isConfirmingSchedule ? "#cbd5e1" : "#4f46e5",
                    color: "#ffffff",
                    cursor: selectedSlotId === null || isConfirmingSchedule ? "not-allowed" : "pointer",
                    fontFamily: "Pretendard Variable, Pretendard, sans-serif",
                    fontSize: 15,
                    fontWeight: 700,
                  }}
                >
                  {isConfirmingSchedule ? "확정 중..." : "일정 확정하기"}
                </button>
              )}
              {scheduleConfirmError && (
                <span style={{ fontSize: 13, fontWeight: 500, color: "#dc2626" }}>
                  {scheduleConfirmError}
                </span>
              )}
              {voteError && (
                <span style={{ fontSize: 13, fontWeight: 500, color: "#dc2626" }}>
                  {voteError}
                </span>
              )}
            </div>
          </div>
        )}

        {placeRecommendation && (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 14,
              padding: 18,
              borderRadius: 18,
              background: "#f1f5f9",
              border: "1px solid #cbd5e1",
              color: "#1e293b",
              fontFamily: "Pretendard Variable, Pretendard, sans-serif",
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
                <MapPin style={{ width: 20, height: 20, color: "#4f46e5" }} />
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: "#4f46e5" }}>
                  장소 추천
                </span>
                <span style={{ fontSize: 19, fontWeight: 700, color: "#1e293b" }}>
                  {placeRecommendation.place_hint} 추천 장소
                </span>
              </div>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
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
                      padding: "14px 16px",
                      borderRadius: 16,
                      background: isSelected ? "#eef2ff" : "#ffffff",
                      border: isSelected ? "1.5px solid #4f46e5" : "1px solid #e2e8f0",
                      boxShadow: isSelected ? "0 6px 18px rgba(79, 70, 229, 0.12)" : "0 4px 14px rgba(15, 23, 42, 0.05)",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                      <span
                        onClick={() => {
                          setSelectedPlace?.({
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
                          });
                          setContextMode?.("place");
                        }}
                        style={{ fontSize: 17, fontWeight: 700, color: "#1e293b", cursor: "pointer" }}
                      >
                        {place.name}
                      </span>
                      <span
                        style={{
                          padding: "4px 10px",
                          borderRadius: 999,
                          background: "#eef2ff",
                          color: "#4f46e5",
                          fontSize: 13,
                          fontWeight: 700,
                          flexShrink: 0,
                        }}
                      >
                        {Math.round(place.score * 100)}%
                      </span>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontSize: 14, fontWeight: 500, color: "#475569" }}>
                        {place.category}
                      </span>
                      {typeof distanceMeters === "number" && distanceMeters > 0 && (
                        <span style={{ fontSize: 12, color: "#94a3b8", fontWeight: 500 }}>
                          {distanceMeters >= 1000
                            ? `${(distanceMeters / 1000).toFixed(1)}km`
                            : `${distanceMeters}m`}
                        </span>
                      )}
                    </div>
                    <span style={{ fontSize: 14, lineHeight: 1.5, color: "#1e293b" }}>
                      {place.address}
                    </span>
                    {isPlaceConfirmed && isSelected ? (
                      <div
                        style={{
                          padding: "8px 12px",
                          borderRadius: 10,
                          background: "#ecfdf5",
                          border: "1px solid #86efac",
                          color: "#166534",
                          fontSize: 13,
                          fontWeight: 700,
                        }}
                      >
                        ✓ 장소가 확정되었습니다
                      </div>
                    ) : !isPlaceConfirmed && confirmedMeetingId ? (
                      <button
                        onClick={() => handleConfirmPlace(place.place_id)}
                        disabled={isConfirmingPlace}
                        style={{
                          padding: "8px 14px",
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
                    ) : null}
                  </div>
                );
              })}
            </div>
            {placeConfirmError && (
              <span style={{ fontSize: 13, fontWeight: 500, color: "#dc2626" }}>
                {placeConfirmError}
              </span>
            )}
          </div>
        )}

        {(maedeupCard || (confirmedSlot && confirmedPlace)) && (() => {
          const displayTime = confirmedSlot ?? maedeupCard?.selected_time;
          const displayPlace = confirmedPlace ?? maedeupCard?.selected_place;
          const title = maedeupCard?.title ?? `${maedeupCard?.meeting_type ?? "모임"} 매듭 카드`;

          return (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 16,
                padding: 20,
                borderRadius: 20,
                background: "linear-gradient(135deg, #4f46e5 0%, #6366f1 100%)",
                color: "#ffffff",
                fontFamily: "Pretendard Variable, Pretendard, sans-serif",
                boxShadow: "0 10px 24px rgba(79, 70, 229, 0.22)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <CheckCircle2 style={{ width: 24, height: 24, color: "#ffffff" }} />
                <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  <span style={{ fontSize: 12, fontWeight: 700, color: "rgba(255,255,255,0.82)" }}>
                    최종 확정
                  </span>
                  <span style={{ fontSize: 21, fontWeight: 700, color: "#ffffff" }}>
                    {title}
                  </span>
                </div>
              </div>
              <div
                style={{
                  display: "grid",
                  gap: 10,
                  padding: 16,
                  borderRadius: 16,
                  background: "rgba(255,255,255,0.14)",
                  border: "1px solid rgba(255,255,255,0.18)",
                }}
              >
                {maedeupCard && (
                  <>
                    <span style={{ fontSize: 15, lineHeight: 1.5 }}>
                      {maedeupCard.meeting_type} · {maedeupCard.date_hint}
                    </span>
                    <span style={{ fontSize: 15, lineHeight: 1.5 }}>
                      참석 인원 {maedeupCard.headcount}명
                    </span>
                  </>
                )}
                {displayTime && (
                  <span style={{ fontSize: 15, lineHeight: 1.5 }}>
                    시간 {displayTime.label}
                  </span>
                )}
                {displayPlace && (
                  <>
                    <span style={{ fontSize: 15, lineHeight: 1.5 }}>
                      장소 {displayPlace.name}
                    </span>
                    <span style={{ fontSize: 14, lineHeight: 1.5, color: "rgba(255,255,255,0.84)" }}>
                      {displayPlace.address}
                    </span>
                  </>
                )}
              </div>
            </div>
          );
        })()}

        {messages.map((msg, index) => {
          const isMe = msg.role === "user";
          const rawSender = isMe ? (msg.sender ?? user?.name ?? "나") : (msg.sender ?? "AI 어시스턴트");
          const senderLabel = rawSender === "LangGraph" ? "매듭 AI" : rawSender;

          return (
            <div
              key={msg.id ?? index}
              style={{
                display: "flex",
                flexDirection: isMe ? "row-reverse" : "row",
                gap: 8,
                alignItems: "flex-end",
              }}
            >
              {!isMe && (
                <div
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: "50%",
                    background: "#818cf8",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "#fff",
                    fontSize: 12,
                    fontWeight: 300,
                    flexShrink: 0,
                  }}
                >
                  {senderLabel.charAt(0)}
                </div>
              )}
              <div
                style={{
                  maxWidth: "75%",
                  display: "flex",
                  flexDirection: "column",
                  alignItems: isMe ? "flex-end" : "flex-start",
                }}
              >
                {!isMe && (
                  <span style={{ fontSize: 11, color: "#94a3b8", marginBottom: 4 }}>
                    {senderLabel}
                  </span>
                )}
                <div
                  style={{
                    padding: "10px 16px",
                    borderRadius: 16,
                    ...(isMe
                      ? {
                          borderBottomRightRadius: 6,
                          background: "#4f46e5",
                          color: "#ffffff",
                        }
                      : {
                          borderBottomLeftRadius: 6,
                          background: "#f1f5f9",
                          color: "#000000",
                        }),
                    fontSize: 17,
                    fontWeight: 300,
                    lineHeight: 1.5,
                    whiteSpace: "pre-wrap" as const,
                  }}
                >
                  {msg.content}
                </div>
              </div>
            </div>
          );
        })}

        {isAiLoading && messages.length > 0 && (
          <div
            style={{
              display: "flex",
              flexDirection: "row",
              gap: 8,
              alignItems: "flex-end",
            }}
          >
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: "50%",
                background: "#818cf8",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#fff",
                fontSize: 12,
                fontWeight: 300,
                flexShrink: 0,
              }}
            >
              AI
            </div>
            <div
              style={{
                padding: "12px 18px",
                borderRadius: 16,
                borderBottomLeftRadius: 6,
                background: "#f1f5f9",
                display: "flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              <style>{`
                @keyframes aiTypingDot {
                  0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
                  40% { opacity: 1; transform: scale(1); }
                }
              `}</style>
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: "#4f46e5",
                  display: "inline-block",
                  animation: "aiTypingDot 1.4s infinite ease-in-out",
                  animationDelay: "0s",
                }}
              />
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: "#4f46e5",
                  display: "inline-block",
                  animation: "aiTypingDot 1.4s infinite ease-in-out",
                  animationDelay: "0.2s",
                }}
              />
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: "#4f46e5",
                  display: "inline-block",
                  animation: "aiTypingDot 1.4s infinite ease-in-out",
                  animationDelay: "0.4s",
                }}
              />
            </div>
          </div>
        )}

        {messages.length === 0 && (
          <div
            style={{
              background: "linear-gradient(135deg, #4f46e5 0%, #7c3aed 50%, #a855f7 100%)",
              borderRadius: 16,
              padding: 20,
              display: "flex",
              flexDirection: "column",
              gap: 12,
              marginTop: 4,
              boxShadow: "0 4px 14px rgba(79, 70, 229, 0.13)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Sparkles style={{ width: 20, height: 20, color: "#ffffff" }} />
              <span style={{ fontSize: 12, fontWeight: 600, color: "#ffffff", fontFamily: "Inter, sans-serif" }}>
                AI 어시스턴트
              </span>
            </div>
            <span style={{ fontSize: 18, fontWeight: 600, color: "#ffffff", fontFamily: "Pretendard Variable, Pretendard, sans-serif" }}>
              {isAiLoading ? "분석 중..." : "일정 조율을 시작하겠습니다"}
            </span>
            <span
              style={{
                fontSize: 13,
                fontWeight: 300,
                color: "#ffffff",
                lineHeight: 1.5,
                whiteSpace: "pre-wrap",
                fontFamily: "Pretendard Variable, Pretendard, sans-serif",
              }}
            >
              {isAiLoading
                ? "채팅 내용을 분석하여 모임원들의\n가능한 시간대를 정리하고 있어요."
                : "메시지를 보내 일정 조율을 시작해보세요."}
            </span>
            <div style={{ width: "100%", height: 1, background: "rgba(255,255,255,0.19)" }} />
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: isAiLoading ? "#fbbf24" : "#34d399",
                  flexShrink: 0,
                }}
              />
              <span style={{ fontSize: 12, fontWeight: 300, color: "#ffffff", fontFamily: "Pretendard Variable, Pretendard, sans-serif" }}>
                {status === "connecting"
                  ? "연결 중..."
                  : isAiLoading
                    ? "AI가 응답 중..."
                    : "연결됨 · 메시지를 기다리는 중"}
              </span>
            </div>
          </div>
        )}
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: 12,
          background: "linear-gradient(135deg, #837cff, #6eb3ff)",
          borderTop: "1px solid #e2e8f0",
        }}
      >
        <input
          type="text"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => event.key === "Enter" && !event.shiftKey && !isAiLoading && handleSend()}
          disabled={isAiLoading}
          placeholder={isAiLoading ? "AI가 응답 중..." : "AI에게 질문하세요"}
          style={{
            flex: 1,
            padding: "10px 16px",
            background: isAiLoading ? "#f1f5f9" : "#ffffff",
            borderRadius: 60,
            border: "1.5px solid #a2f4fd",
            outline: "none",
            fontSize: 15,
            color: "#1e293b",
            fontFamily: "Pretendard Variable, Pretendard, sans-serif",
            boxShadow: "0 2px 3.5px rgba(0,0,0,0.15)",
            opacity: isAiLoading ? 0.7 : 1,
            cursor: isAiLoading ? "not-allowed" : "text",
          }}
        />
        <button
          onClick={isAiLoading ? handleStopAi : handleSend}
          title={isAiLoading ? "응답 정지" : "메시지 보내기"}
          style={{
            width: 40,
            height: 40,
            borderRadius: "50%",
            background: isAiLoading ? "#ef4444" : "#ffffff",
            border: "none",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
            flexShrink: 0,
            boxShadow: "0 2px 3.5px rgba(0,0,0,0.15)",
            transition: "background 0.2s ease",
          }}
        >
          {isAiLoading ? (
            <Square style={{ width: 14, height: 14, color: "#ffffff", fill: "#ffffff" }} />
          ) : (
            <Send style={{ width: 16, height: 16, color: "#837cff" }} />
          )}
        </button>
      </div>
    </div>
  );
}
