"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { CalendarDays, ChevronDown, ChevronUp, Check } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { useMeeting } from "@/contexts/MeetingContext";
import type { VoteCardPayload, VoteUpdatePayload } from "@/hooks/useAgentWebSocket";

function splitLabelParts(label: string): { date: string; time: string | null; trail: string | null } {
  const match = label.match(/^(.*?)\s*((?:오전|오후)?\s*\d{1,2}:\d{2}(?:\s*[~\-]\s*(?:오전|오후)?\s*\d{1,2}:\d{2})?)(\s*\([^)]*\))?\s*$/);
  if (!match) return { date: label, time: null, trail: null };
  const date = match[1]?.trim() ?? "";
  const time = match[2]?.trim() ?? null;
  const trail = match[3]?.trim() ?? null;
  if (!date || !time) return { date: label, time: null, trail: null };
  return { date, time, trail };
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
    voteAwaitingTimeMeetingId,
    requestTimeChange,
    setContextMode,
    voteUpdate,
  } = useMeeting();
  const voteCard = voteCardProp ?? contextVoteCard;
  const isAwaitingTimeChange = !!voteCard && voteAwaitingTimeMeetingId === voteCard.meeting_id;

  const [selectedSlotId, setSelectedSlotId] = useState<string | null>(null);
  const [showAlternatives, setShowAlternatives] = useState(false);
  const [isConfirming, setIsConfirming] = useState(false);
  const [isConfirmed, setIsConfirmed] = useState(false);
  const [confirmedLabel, setConfirmedLabel] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  // PR-Y2 (Q16=C): F1 fallback 시 슬롯별 불참자 토글. 한 번에 하나만 펼침 (다른 슬롯 열면 현재 슬롯 닫힘).
  const [expandedUnavailableSlotId, setExpandedUnavailableSlotId] = useState<string | null>(null);

  const [hostUserId, setHostUserId] = useState<number | null>(null);
  const [hostLoading, setHostLoading] = useState(true);
  const currentUserId = useMemo(() => getCurrentUserIdFromToken(), []);
  // hostLoading 중에는 일단 호스트 UI 표시 (낙관적 렌더) — API 응답 후 비호스트 확인 시 전환.
  // race condition 방지: 카드 mount 직후 API 완료 전에 "시간대 변경" 버튼이 미노출되는 문제 해소.
  const isHost = hostLoading ? currentUserId !== null : (currentUserId !== null && hostUserId === currentUserId);

  // vote 실시간 집계 state (voteUpdate WS 구독)
  const [voteCounts, setVoteCounts] = useState<Record<string, number>>({});
  const [totalVoters, setTotalVoters] = useState(0);
  const [votedOptionIndex, setVotedOptionIndex] = useState<number | null>(null);

  // PR-Z2 (Q5 hybrid): 선호 기준 토글 상태.
  // 토글 클릭 → refresh API 호출 → 응답은 WebSocket으로 broadcast 되므로 별도 state 갱신 불필요.
  // 자체 로딩/에러 상태만 관리.
  const [isRefreshingPreference, setIsRefreshingPreference] = useState(false);
  const [preferenceRefreshError, setPreferenceRefreshError] = useState<string | null>(null);

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
    setExpandedUnavailableSlotId(null);
    setPreferenceRefreshError(null);
    // 새 voteCard 도착 시 vote 집계 초기화 + 본인 기존 vote 반영
    setVoteCounts({});
    setTotalVoters(0);
    setVotedOptionIndex(voteCard.current_user_vote ?? null);
  }, [voteCard]);

  // voteUpdate WS 이벤트 → vote 집계 동기화 (VoteCardSection.tsx 패턴 포팅)
  useEffect(() => {
    if (!voteUpdate) return;
    if (voteCard && voteUpdate.meeting_id !== voteCard.meeting_id) return;
    setVoteCounts(voteUpdate.votes);
    setTotalVoters(voteUpdate.total_voters);
    if (voteUpdate.user_votes && currentUserId !== null) {
      const myVote = voteUpdate.user_votes[String(currentUserId)];
      setVotedOptionIndex(myVote !== undefined ? myVote : null);
    }
  }, [voteCard, currentUserId, voteUpdate]);

  // PR-Z2 (Q5 hybrid): refresh API 호출 — viewer === requester(자기 자신)만 호출.
  // 응답은 WebSocket으로 broadcast되어 voteCard가 자동 갱신되므로 별도 setter 불필요.
  const refreshRecommendations = useCallback(
    async (
      meetingId: number,
      scope: "vote_card" | "place_recommendation" | "both",
      source: "group" | "speaker",
    ) => {
      if (currentUserId === null) {
        setPreferenceRefreshError("로그인이 필요합니다.");
        return;
      }
      setIsRefreshingPreference(true);
      setPreferenceRefreshError(null);
      try {
        await apiFetch<{
          vote_card: VoteCardPayload | null;
          place_recommendation: unknown;
          narrator: string;
          cached: boolean;
        }>(`/api/v1/meetings/${meetingId}/recommendations/refresh`, {
          method: "POST",
          body: JSON.stringify({
            scope,
            preference_source: source,
            requester_user_id: currentUserId,
          }),
        });
        // 성공: WebSocket broadcast로 voteCard 자동 갱신.
      } catch (err) {
        const message = err instanceof Error ? err.message : "추천 갱신 실패";
        // 백엔드 detail 매핑 (PR-Z1 보고서).
        let userMessage = message;
        if (/permission_denied|not_a_room_member/i.test(message)) {
          userMessage = "토글 권한이 없어요 (발화자 또는 방장만 가능).";
        } else if (/toggle_disabled/i.test(message)) {
          userMessage = "현재는 토글할 수 있는 조건이 아니에요.";
        } else if (/daily_limit_exceeded/i.test(message)) {
          userMessage = "일일 한도(100회)를 초과했어요.";
        } else if (/meeting_not_found/i.test(message)) {
          userMessage = "모임을 찾을 수 없어요.";
        }
        setPreferenceRefreshError(userMessage);
      } finally {
        setIsRefreshingPreference(false);
      }
    },
    [currentUserId],
  );

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

  const handleRequestTimeChange = useCallback(() => {
    if (!voteCard || !selectedSlotId) return;
    if (typeof voteCard.meeting_id !== "number") return;
    const slot = voteCard.time_options.find((o) => o.slot_id === selectedSlotId);
    if (!slot) return;
    requestTimeChange(slot, voteCard.meeting_id);  // 호스트 본인 화면 즉시 전환
    setContextMode("schedule");
    // 전 멤버에게 TimeBar 진입 브로드캐스트 (fire-and-forget). 실패해도 호스트
    // 로컬 전환은 유지 — 협업 진입만 best-effort.
    const date = slot.start_at.split("T")[0];
    if (roomId && date) {
      apiFetch(`/api/v1/rooms/${roomId}/timebar-open`, {
        method: "POST",
        body: JSON.stringify({ meeting_id: voteCard.meeting_id, date }),
      }).catch(() => {
        /* 브로드캐스트 실패 무시 */
      });
    }
  }, [voteCard, selectedSlotId, requestTimeChange, setContextMode, roomId]);

  if (!voteCard) return null;

  const best = voteCard.time_options[0];
  const alternatives = voteCard.time_options.slice(1);
  const dateGroups = groupByDate(voteCard.time_options);
  const isMultiDate =
    voteCard.calendar_strategy === "multi_date_vote" &&
    Object.keys(dateGroups).length > 1;
  const isMajorityFallback = voteCard.calendar_strategy === "majority_fallback";
  const headcount = voteCard.headcount;
  const selectedSlot = voteCard.time_options.find((o) => o.slot_id === selectedSlotId);

  // PR-Y2 (F1 fallback): 슬롯별 가능자 배지 색상 — 비율이 낮을수록 더 강한 경고색.
  const renderAvailabilityBadge = (opt: VoteCardPayload["time_options"][number]) => {
    if (typeof opt.available_count !== "number" || typeof opt.total_count !== "number" || opt.total_count <= 0) {
      return null;
    }
    const ratio = opt.available_count / opt.total_count;
    // 전원 가능: 초록 / 1명 부족: 주의(앰버) / 그 외: 경고(레드톤)
    let bg = "#dcfce7";
    let color = "#166534";
    if (ratio < 1 && ratio >= 0.66) {
      bg = "#fef3c7";
      color = "#92400e";
    } else if (ratio < 0.66) {
      bg = "#fee2e2";
      color = "#991b1b";
    }
    return (
      <span style={{
        fontSize: 17, padding: "2px 6px", borderRadius: 6,
        background: bg, color, fontWeight: 600, whiteSpace: "nowrap",
      }}>
        {opt.available_count}/{opt.total_count}명 가능
      </span>
    );
  };

  // PR-Y2 (Q16=C): 슬롯별 불참자 토글. 익명 카운트 → 클릭 시 실명 펼침.
  const renderUnavailableToggle = (opt: VoteCardPayload["time_options"][number]) => {
    const unavailable = opt.unavailable_users ?? [];
    if (unavailable.length === 0) return null;
    const isExpanded = expandedUnavailableSlotId === opt.slot_id;
    return (
      <div style={{ marginTop: 6, display: "flex", flexDirection: "column", gap: 4 }}>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            setExpandedUnavailableSlotId((prev) => (prev === opt.slot_id ? null : opt.slot_id));
          }}
          style={{
            display: "inline-flex", alignItems: "center", gap: 4,
            background: "transparent", border: "none", padding: 0,
            color: "#64748b", fontSize: 17, fontWeight: 500, cursor: "pointer",
            fontFamily: "Pretendard Variable, Pretendard, sans-serif",
            alignSelf: "flex-start",
          }}
          aria-expanded={isExpanded}
        >
          <span aria-hidden="true">👤</span>
          <span>{unavailable.length}명 불참</span>
          {isExpanded
            ? <ChevronUp style={{ width: 12, height: 12 }} />
            : <ChevronDown style={{ width: 12, height: 12 }} />
          }
        </button>
        {isExpanded && (
          <span style={{ fontSize: 17, color: "#475569", lineHeight: 1.5 }}>
            불참: {unavailable.join(", ")}
          </span>
        )}
      </div>
    );
  };

  if (isConfirmed) {
    return (
      <div style={{
        display: "flex", flexDirection: "column", gap: 10, padding: 16,
        borderRadius: 16, background: "#ecfdf5", border: "1px solid #86efac",
        fontFamily: "Pretendard Variable, Pretendard, sans-serif",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Check style={{ width: 20, height: 20, color: "#16a34a" }} />
          <span style={{ fontSize: 23, fontWeight: 700, color: "#166534" }}>일정이 확정되었습니다</span>
        </div>
        <span style={{ fontSize: 21, fontWeight: 600, color: "#15803d" }}>{confirmedLabel}</span>
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
        <span style={{ fontSize: 20, fontWeight: 600, color: "#4f46e5" }}>AI 일정 추천</span>
        {totalVoters > 0 && (
          <span style={{ fontSize: 18, color: "#94a3b8", marginLeft: 4 }}>
            투표 {totalVoters}/{voteCard.headcount ?? "?"}명
          </span>
        )}
      </div>

      {/* PR-Z2 (Q5 hybrid): 추천 기준 토글.
          백엔드가 preference_toggle_enabled=true로 발행한 경우에만 노출.
          현재 활성 출처(preference_source)에 따라 버튼 강조. */}
      {voteCard.preference_toggle_enabled && typeof voteCard.meeting_id === "number" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <div style={{
            display: "flex", alignItems: "center", gap: 6,
            padding: 3, borderRadius: 10,
            background: "#eef2ff", border: "1px solid #c7d2fe",
            alignSelf: "flex-start",
          }}>
            {(["group", "speaker"] as const).map((source) => {
              const active = (voteCard.preference_source ?? "group") === source;
              const label = source === "group" ? "그룹 다수결" : "내 선호";
              return (
                <button
                  key={source}
                  type="button"
                  onClick={() => {
                    if (active || isRefreshingPreference) return;
                    if (typeof voteCard.meeting_id !== "number") return;
                    refreshRecommendations(voteCard.meeting_id, "vote_card", source);
                  }}
                  disabled={active || isRefreshingPreference}
                  style={{
                    padding: "5px 12px", borderRadius: 8, border: "none",
                    background: active ? "#4f46e5" : "transparent",
                    color: active ? "#ffffff" : "#4338ca",
                    fontSize: 18, fontWeight: 600,
                    cursor: active || isRefreshingPreference ? "default" : "pointer",
                    opacity: isRefreshingPreference && !active ? 0.5 : 1,
                    fontFamily: "Pretendard Variable, Pretendard, sans-serif",
                  }}
                  aria-pressed={active}
                >
                  {label}
                </button>
              );
            })}
            {isRefreshingPreference && (
              <span style={{ fontSize: 17, color: "#4338ca", marginLeft: 4 }}>
                갱신 중...
              </span>
            )}
          </div>
          {preferenceRefreshError && (
            <span style={{ fontSize: 18, color: "#dc2626", fontWeight: 500 }}>
              {preferenceRefreshError}
            </span>
          )}
        </div>
      )}

      {/* PR-Y2 (F1 fallback): 다수결 추천 안내 배너 */}
      {isMajorityFallback && (
        <div
          role="status"
          style={{
            display: "flex", alignItems: "flex-start", gap: 8,
            padding: "10px 12px", borderRadius: 10,
            background: "#fffbeb", border: "1px solid #fcd34d",
            fontSize: 18, fontWeight: 500, color: "#92400e", lineHeight: 1.5,
          }}
        >
          <span aria-hidden="true" style={{ fontSize: 21, lineHeight: 1 }}>⚠️</span>
          <span>전원 가능한 시간이 없어요. 가장 많이 가능한 시간 3개를 보여드려요.</span>
        </div>
      )}

      {/* Multi-date: show per-date availability */}
      {isMultiDate && (
        <div style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 20, color: "#475569" }}>
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
                    fontSize: 17, padding: "2px 6px", borderRadius: 6,
                    background: "#dcfce7", color: "#166534", fontWeight: 600,
                  }}>
                    {headcount}명 가능
                  </span>
                )}
                {isBestDate && (
                  <span style={{ fontSize: 17, color: "#4f46e5", fontWeight: 600 }}>추천</span>
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
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
          <span style={{ fontSize: 23, fontWeight: 700, color: "#1e293b" }}>
            {(() => {
              const parts = splitLabelParts(best.label);
              return (
                <>
                  <span>{parts.date}</span>
                  {parts.time && (
                    <span style={{ marginLeft: 6, color: "#9ca3af", fontSize: 18, fontWeight: 500 }}>
                      {parts.time}
                    </span>
                  )}
                  {parts.trail && (
                    <span style={{ marginLeft: 6, color: "#9ca3af", fontSize: 18, fontWeight: 500 }}>
                      {parts.trail}
                    </span>
                  )}
                </>
              );
            })()}
          </span>
          <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
            {renderAvailabilityBadge(best)}
            <span style={{
              fontSize: 17, padding: "3px 8px", borderRadius: 8,
              background: "#4f46e5", color: "#fff", fontWeight: 600,
            }}>
              추천
            </span>
            <span style={{ fontSize: 18, color: "#94a3b8" }}>
              ({voteCounts[String(0)] ?? 0}표{totalVoters > 0 ? ` / ${totalVoters}명` : ""})
            </span>
            {votedOptionIndex === 0 && (
              <span style={{
                fontSize: 17, padding: "2px 7px", borderRadius: 6,
                background: "#dcfce7", color: "#166534", fontWeight: 600,
              }}>
                ✓ 내가 투표
              </span>
            )}
          </div>
        </div>
        {best.is_holiday && (
          <span style={{ fontSize: 17, color: "#dc2626", fontWeight: 600 }}>{best.holiday_name || "공휴일"}</span>
        )}
        {best.is_weekend && !best.is_holiday && (
          <span style={{ fontSize: 17, color: "#2563eb", fontWeight: 600 }}>주말</span>
        )}
        {renderUnavailableToggle(best)}
      </div>

      {/* Alternatives toggle */}
      {alternatives.length > 0 && (
        <>
          <button
            onClick={() => setShowAlternatives((v) => !v)}
            style={{
              display: "flex", alignItems: "center", gap: 4,
              background: "transparent", border: "none", cursor: "pointer",
              color: "#64748b", fontSize: 18, fontWeight: 500, padding: 0,
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
              {alternatives.map((opt, idx) => {
                const optionIndex = idx + 1;
                return (
                  <div
                    key={opt.slot_id}
                    onClick={() => setSelectedSlotId(opt.slot_id)}
                    style={{
                      padding: "10px 12px", borderRadius: 10,
                      background: selectedSlotId === opt.slot_id ? "#eef2ff" : "#ffffff",
                      border: selectedSlotId === opt.slot_id ? "1.5px solid #4f46e5" : "1px solid #e2e8f0",
                      cursor: "pointer", fontSize: 21, fontWeight: 500, color: "#334155",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                      <span>
                        {opt.label}
                        {opt.is_holiday && <span style={{ marginLeft: 6, fontSize: 17, color: "#dc2626" }}>{opt.holiday_name || "공휴일"}</span>}
                        {opt.is_weekend && !opt.is_holiday && <span style={{ marginLeft: 6, fontSize: 17, color: "#2563eb" }}>주말</span>}
                      </span>
                      <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
                        {renderAvailabilityBadge(opt)}
                        <span style={{ fontSize: 18, color: "#94a3b8" }}>
                          ({voteCounts[String(optionIndex)] ?? 0}표{totalVoters > 0 ? ` / ${totalVoters}명` : ""})
                        </span>
                        {votedOptionIndex === optionIndex && (
                          <span style={{
                            fontSize: 17, padding: "2px 7px", borderRadius: 6,
                            background: "#dcfce7", color: "#166534", fontWeight: 600,
                          }}>
                            ✓ 내가 투표
                          </span>
                        )}
                      </div>
                    </div>
                    {renderUnavailableToggle(opt)}
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

      {/* Action area — host: 두 버튼 stack, host & awaiting: placeholder */}
      {isAwaitingTimeChange ? (
        <div style={{
          width: "100%", padding: "11px 14px", borderRadius: 12,
          background: "#f1f5f9", color: "#64748b", fontSize: 20, fontWeight: 500,
          textAlign: "center", fontFamily: "Pretendard Variable, Pretendard, sans-serif",
        }}>
          시간대 합의 중...
        </div>
      ) : isHost ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <button
              onClick={handleConfirm}
              disabled={!selectedSlotId || isConfirming}
              style={{
                width: "100%", padding: "11px 14px", borderRadius: 12, border: "none",
                background: !selectedSlotId || isConfirming ? "#cbd5e1" : "#4f46e5",
                color: "#fff", fontSize: 21, fontWeight: 700, cursor: !selectedSlotId || isConfirming ? "not-allowed" : "pointer",
                fontFamily: "Pretendard Variable, Pretendard, sans-serif",
              }}
            >
              {isConfirming ? "확정 중..." : selectedSlot ? `${selectedSlot.label}로 확정` : "시간을 선택해주세요"}
            </button>
          <button
            onClick={handleRequestTimeChange}
            disabled={!selectedSlotId || isConfirming}
            style={{
              width: "100%", padding: "11px 14px", borderRadius: 12,
              border: "1px solid #cbd5e1", background: "#ffffff",
              color: "#475569", fontSize: 21, fontWeight: 700,
              cursor: !selectedSlotId || isConfirming ? "not-allowed" : "pointer",
              fontFamily: "Pretendard Variable, Pretendard, sans-serif",
            }}
          >
            시간대 변경
          </button>
        </div>
      ) : (
        <button
          onClick={handleConfirm}
          disabled={!selectedSlotId || isConfirming}
          style={{
            width: "100%", padding: "11px 14px", borderRadius: 12, border: "none",
            background: !selectedSlotId || isConfirming ? "#cbd5e1" : "#4f46e5",
            color: "#fff", fontSize: 21, fontWeight: 700, cursor: !selectedSlotId || isConfirming ? "not-allowed" : "pointer",
            fontFamily: "Pretendard Variable, Pretendard, sans-serif",
          }}
        >
          {isConfirming ? "확정 중..." : selectedSlot ? `${selectedSlot.label}로 확정` : "시간을 선택해주세요"}
        </button>
      )}
      {error && <span style={{ fontSize: 18, color: "#dc2626", fontWeight: 500 }}>{error}</span>}
    </div>
  );
}
