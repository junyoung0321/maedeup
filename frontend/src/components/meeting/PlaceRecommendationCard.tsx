"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { MapPin } from "lucide-react";
import { apiFetch } from "@/lib/api";
import type { PlaceResult } from "@/types";
import type { PlaceRecommendationPayload } from "@/hooks/useAgentWebSocket";

function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

// PR-Z2 (Q5 hybrid): JWT sub → 숫자 user_id 추출. ScheduleRecommendationCard와 동일 패턴.
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

interface PlaceRecommendationCardProps {
  placeRecommendation: PlaceRecommendationPayload;
  meetingId: number | null;
  roomId: string;
  onPlaceConfirmed?: () => void;
  onPlaceClick?: (place: PlaceResult) => void;
  onContextModeDone?: () => void;
}

export default function PlaceRecommendationCard({
  placeRecommendation,
  meetingId,
  roomId,
  onPlaceConfirmed,
  onPlaceClick,
  onContextModeDone,
}: PlaceRecommendationCardProps) {
  const [selectedPlaceId, setSelectedPlaceId] = useState<string | null>(null);
  const [confirmedPlace, setConfirmedPlace] = useState<{ name: string; address: string } | null>(null);
  const [isConfirmingPlace, setIsConfirmingPlace] = useState(false);
  const [isPlaceConfirmed, setIsPlaceConfirmed] = useState(false);
  const [placeConfirmError, setPlaceConfirmError] = useState<string | null>(null);

  // PR-Z2 (Q5 hybrid): 선호 기준 토글 로딩/에러 상태. 응답은 WS broadcast로 자동 갱신.
  const [isRefreshingPreference, setIsRefreshingPreference] = useState(false);
  const [preferenceRefreshError, setPreferenceRefreshError] = useState<string | null>(null);
  const currentUserId = useMemo(() => getCurrentUserIdFromToken(), []);

  // Reset state when new recommendation arrives
  useEffect(() => {
    setSelectedPlaceId(null);
    setConfirmedPlace(null);
    setIsPlaceConfirmed(false);
    setPlaceConfirmError(null);
    setIsConfirmingPlace(false);
    setPreferenceRefreshError(null);
  }, [placeRecommendation]);

  // PR-Z2 (Q5 hybrid): refresh API 호출 — ScheduleRecommendationCard와 동일 시그니처.
  const refreshRecommendations = useCallback(
    async (
      mid: number,
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
          vote_card: unknown;
          place_recommendation: PlaceRecommendationPayload | null;
          narrator: string;
          cached: boolean;
        }>(`/api/v1/meetings/${mid}/recommendations/refresh`, {
          method: "POST",
          body: JSON.stringify({
            scope,
            preference_source: source,
            requester_user_id: currentUserId,
          }),
        });
        // 성공: WebSocket broadcast로 placeRecommendation 자동 갱신.
      } catch (err) {
        const message = err instanceof Error ? err.message : "추천 갱신 실패";
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

  const handlePlaceClick = useCallback((place: {
    place_id: string; name: string; address: string; phone?: string;
    url: string; x?: string; y?: string; category: string;
    distance_m?: number; score: number;
  }) => {
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
    onPlaceClick?.(placeResult);
  }, [onPlaceClick]);

  const handleConfirmPlace = useCallback(async (placeId: string) => {
    const place = placeRecommendation.recommendations.find((item) => item.place_id === placeId);
    if (!place) {
      setPlaceConfirmError("선택한 장소 정보를 찾을 수 없습니다.");
      return;
    }

    // meetingId가 없으면 장소 상세 보기로 전환
    if (!meetingId) {
      handlePlaceClick(place);
      return;
    }

    setSelectedPlaceId(placeId);
    setIsConfirmingPlace(true);
    setPlaceConfirmError(null);
    try {
      await apiFetch<{ id: number }>(`/api/v1/meetings/${meetingId}/place`, {
        method: "PATCH",
        body: JSON.stringify({
          place: place.name,
          place_id: place.place_id,
          name: place.name,
          address: place.address,
          url: place.url,
        }),
      });
      setConfirmedPlace({ name: place.name, address: place.address });
      setIsPlaceConfirmed(true);
      onPlaceConfirmed?.();
      // 2초 후 완료 전환
      if (onContextModeDone) {
        setTimeout(() => onContextModeDone(), 2000);
      }
    } catch (error) {
      setPlaceConfirmError(getErrorMessage(error, "장소 확정에 실패했습니다."));
      setSelectedPlaceId(null);
    } finally {
      setIsConfirmingPlace(false);
    }
  }, [placeRecommendation, meetingId, handlePlaceClick, onPlaceConfirmed, onContextModeDone]);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 14,
        padding: 18,
        borderRadius: 18,
        background: "#f1f5f9",
        border: "1px solid #cbd5e1",
        fontFamily: "Pretendard Variable, Pretendard, sans-serif",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <div style={{ width: 40, height: 40, borderRadius: 14, background: "#e0e7ff", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <MapPin style={{ width: 20, height: 20, color: "#4f46e5" }} />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
          <span style={{ fontSize: 18, fontWeight: 600, color: "#4f46e5" }}>장소 추천</span>
          <span style={{ fontSize: 26, fontWeight: 700, color: "#1e293b" }}>{placeRecommendation.place_hint} 추천 장소</span>
        </div>
      </div>

      {/* PR-Z2 (Q5 hybrid): 추천 기준 토글. preference_toggle_enabled=true + meetingId 있을 때만. */}
      {placeRecommendation.preference_toggle_enabled && meetingId !== null && (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <div style={{
            display: "flex", alignItems: "center", gap: 6,
            padding: 3, borderRadius: 10,
            background: "#e0e7ff", border: "1px solid #c7d2fe",
            alignSelf: "flex-start",
          }}>
            {(["group", "speaker"] as const).map((source) => {
              const active = (placeRecommendation.preference_source ?? "group") === source;
              const label = source === "group" ? "그룹 다수결" : "내 선호";
              return (
                <button
                  key={source}
                  type="button"
                  onClick={() => {
                    if (active || isRefreshingPreference) return;
                    refreshRecommendations(meetingId, "place_recommendation", source);
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

      {/* A5-2: 멤버별 PersonalData 인용 reasoning. 시드 있으면 "수현님 채식·홍대 비선호 ✨ 반영" 톤,
          없으면 익명 그룹 톤 ("멤버 중 채식주의자가 있어요"). 빈/공백 문자열이면 표시 안 함. */}
      {placeRecommendation.group_constraints_summary?.trim() && (
        <div style={{
          padding: "10px 13px",
          borderRadius: 12,
          background: "#eef2ff",
          border: "1px solid #c7d2fe",
          fontSize: 20,
          fontWeight: 500,
          lineHeight: 1.5,
          color: "#4338ca",
        }}>
          {placeRecommendation.group_constraints_summary.trim()}
        </div>
      )}
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
                padding: "12px 14px",
                borderRadius: 16,
                background: isSelected ? "#eef2ff" : "#ffffff",
                border: isSelected ? "1.5px solid #4f46e5" : "1px solid #e2e8f0",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                <span onClick={() => handlePlaceClick(place)} style={{ fontSize: 24, fontWeight: 700, color: "#1e293b", cursor: "pointer" }}>
                  {place.name}
                </span>
                <span style={{ padding: "4px 10px", borderRadius: 999, background: "#eef2ff", color: "#4f46e5", fontSize: 20, fontWeight: 700, flexShrink: 0 }}>
                  {Math.round(place.score * 100)}%
                </span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontSize: 20, fontWeight: 500, color: "#475569" }}>{place.category}</span>
                {typeof distanceMeters === "number" && distanceMeters > 0 && (
                  <span style={{ fontSize: 18, color: "#94a3b8", fontWeight: 500 }}>
                    {distanceMeters >= 1000 ? `${(distanceMeters / 1000).toFixed(1)}km` : `${distanceMeters}m`}
                  </span>
                )}
              </div>
              <span style={{ fontSize: 20, lineHeight: 1.5, color: "#1e293b" }}>{place.address}</span>
              {isPlaceConfirmed && isSelected ? (
                <div style={{ padding: "8px 12px", borderRadius: 10, background: "#ecfdf5", border: "1px solid #86efac", color: "#166534", fontSize: 20, fontWeight: 700 }}>
                  ✓ 장소가 확정되었습니다
                </div>
              ) : meetingId ? (
                <button
                  onClick={() => handleConfirmPlace(place.place_id)}
                  disabled={isConfirmingPlace}
                  style={{
                    padding: "7px 12px",
                    borderRadius: 10,
                    border: "none",
                    background: isConfirmingPlace && isSelected ? "#cbd5e1" : "#4f46e5",
                    color: "#ffffff",
                    fontSize: 20,
                    fontWeight: 600,
                    cursor: isConfirmingPlace ? "not-allowed" : "pointer",
                    alignSelf: "flex-start",
                    fontFamily: "Pretendard Variable, Pretendard, sans-serif",
                  }}
                >
                  {isConfirmingPlace && isSelected ? "확정 중..." : "이 장소로 확정"}
                </button>
              ) : (
                <span style={{ fontSize: 18, color: "#94a3b8", fontStyle: "italic" }}>
                  일정을 먼저 확정하면 장소를 선택할 수 있어요
                </span>
              )}
            </div>
          );
        })}
      </div>
      {placeConfirmError && <span style={{ fontSize: 20, fontWeight: 500, color: "#dc2626" }}>{placeConfirmError}</span>}
    </div>
  );
}
