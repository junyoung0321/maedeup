"use client";

import { useCallback, useEffect, useState } from "react";
import { MapPin } from "lucide-react";
import { apiFetch } from "@/lib/api";
import type { PlaceResult } from "@/types";
import type { PlaceRecommendationPayload } from "@/hooks/useAgentWebSocket";

function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
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

  // Reset state when new recommendation arrives
  useEffect(() => {
    setSelectedPlaceId(null);
    setConfirmedPlace(null);
    setIsPlaceConfirmed(false);
    setPlaceConfirmError(null);
    setIsConfirmingPlace(false);
  }, [placeRecommendation]);

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
          <span style={{ fontSize: 12, fontWeight: 600, color: "#4f46e5" }}>장소 추천</span>
          <span style={{ fontSize: 17, fontWeight: 700, color: "#1e293b" }}>{placeRecommendation.place_hint} 추천 장소</span>
        </div>
      </div>
      {/* A5-2: 멤버별 PersonalData 인용 reasoning. 시드 있으면 "수현님 채식·홍대 비선호 ✨ 반영" 톤,
          없으면 익명 그룹 톤 ("멤버 중 채식주의자가 있어요"). 빈/공백 문자열이면 표시 안 함. */}
      {placeRecommendation.group_constraints_summary?.trim() && (
        <div style={{
          padding: "10px 13px",
          borderRadius: 12,
          background: "#eef2ff",
          border: "1px solid #c7d2fe",
          fontSize: 13,
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
              {place.reason && (
                <div
                  style={{
                    display: "flex",
                    gap: 6,
                    padding: "8px 10px",
                    borderRadius: 10,
                    background: "#fef3c7",
                    border: "1px solid #fde68a",
                    fontSize: 12,
                    lineHeight: 1.5,
                    color: "#78350f",
                    fontWeight: 500,
                  }}
                >
                  <span style={{ flexShrink: 0 }}>✨</span>
                  <span>{place.reason}</span>
                </div>
              )}
              {isPlaceConfirmed && isSelected ? (
                <div style={{ padding: "8px 12px", borderRadius: 10, background: "#ecfdf5", border: "1px solid #86efac", color: "#166534", fontSize: 13, fontWeight: 700 }}>
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
                <span style={{ fontSize: 12, color: "#94a3b8", fontStyle: "italic" }}>
                  일정을 먼저 확정하면 장소를 선택할 수 있어요
                </span>
              )}
            </div>
          );
        })}
      </div>
      {placeConfirmError && <span style={{ fontSize: 13, fontWeight: 500, color: "#dc2626" }}>{placeConfirmError}</span>}
    </div>
  );
}
