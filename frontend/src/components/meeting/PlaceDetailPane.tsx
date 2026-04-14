"use client";

import { useEffect, useRef, useState } from "react";
import { MapPin, Phone, ExternalLink, Navigation } from "lucide-react";
import { apiFetch } from "@/lib/api";
import type { PlaceResult } from "@/types";

/* ── Kakao Maps type shim ──────────────────────────────── */
/* eslint-disable @typescript-eslint/no-explicit-any */
declare global {
  interface Window {
    kakao: any;
  }
}

interface Props {
  place: PlaceResult | null;
  roomId?: string;
}

export default function PlaceDetailPane({ place, roomId }: Props) {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<any>(null);
  const markerRef = useRef<any>(null);
  const relayoutTimerRef = useRef<number | null>(null);
  const [confirmed, setConfirmed] = useState(false);

  /* ── Kakao Map ───────────────────────────────────────── */
  useEffect(() => {
    if (!place?.x || !place?.y || !mapRef.current) return;

    const loadMap = () => {
      const kakao = window.kakao;
      if (!kakao?.maps) return;

      const lng = parseFloat(place.x);
      const lat = parseFloat(place.y);
      if (Number.isNaN(lng) || Number.isNaN(lat)) return;

      const center = new kakao.maps.LatLng(lat, lng);

      if (!mapInstanceRef.current) {
        mapInstanceRef.current = new kakao.maps.Map(mapRef.current, {
          center,
          level: 3,
        });
      } else {
        mapInstanceRef.current.setCenter(center);
      }

      if (markerRef.current) {
        markerRef.current.setMap(null);
      }

      markerRef.current = new kakao.maps.Marker({
        position: center,
        map: mapInstanceRef.current,
      });

      // Resize map after render
      relayoutTimerRef.current = window.setTimeout(() => {
        mapInstanceRef.current?.relayout();
        mapInstanceRef.current?.setCenter(center);
        relayoutTimerRef.current = null;
      }, 100);
    };

    const kakao = window.kakao;
    if (kakao?.maps?.LatLng) {
      loadMap();
    } else if (kakao?.maps) {
      kakao.maps.load(loadMap);
    }

    return () => {
      if (relayoutTimerRef.current !== null) {
        window.clearTimeout(relayoutTimerRef.current);
        relayoutTimerRef.current = null;
      }
    };
  }, [place?.x, place?.y]);

  // Reset confirmed state when place changes
  useEffect(() => {
    setConfirmed(false);
  }, [place?.id]);

  /* ── Confirm handler ─────────────────────────────────── */
  const parsedRoomId = Number.parseInt(roomId ?? "", 10);
  const hasValidRoom = Number.isFinite(parsedRoomId);

  const handleSelect = async () => {
    if (!place || !hasValidRoom) return;
    const now = new Date().toISOString();
    try {
      await apiFetch("/api/v1/events/", {
        method: "POST",
        body: JSON.stringify({
          title: place.name,
          location_name: place.address,
          latitude: place.y ? parseFloat(place.y) : null,
          longitude: place.x ? parseFloat(place.x) : null,
          starts_at: now,
          kakao_place_id: place.id,
          kakao_place_url: place.url || null,
          room_id: parsedRoomId,
        }),
      });
      setConfirmed(true);
    } catch {
      /* API unavailable */
    }
  };

  /* ── Distance display ────────────────────────────────── */
  const distanceLabel = (() => {
    if (typeof place?.distance_m !== "number" || place.distance_m <= 0) return null;
    if (place.distance_m >= 1000) return `${(place.distance_m / 1000).toFixed(1)}km`;
    return `${place.distance_m}m`;
  })();

  return (
    <div
      style={{
        width: 414,
        minHeight: 733,
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
      {/* Header */}
      <div
        style={{
          background: "#f2f4f7",
          borderRadius: "20px 20px 0 0",
          padding: "16px 20px",
          borderBottom: "1px solid #e2e8f0",
        }}
      >
        <span
          style={{
            fontSize: 26,
            fontWeight: 400,
            color: "#000000",
            letterSpacing: 0.75,
          }}
        >
          장소 상세
        </span>
      </div>

      {/* Content */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {!place ? (
          /* ── Empty state ────────────────────────────── */
          <div
            style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: 12,
              padding: 40,
            }}
          >
            <div
              style={{
                width: 64,
                height: 64,
                borderRadius: "50%",
                background: "#eef2ff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <MapPin style={{ width: 28, height: 28, color: "#4f46e5" }} />
            </div>
            <span
              style={{
                fontSize: 15,
                fontWeight: 400,
                color: "#94a3b8",
                textAlign: "center",
                lineHeight: 1.6,
              }}
            >
              AI가 추천한 장소를 선택해보세요
            </span>
            <span
              style={{
                fontSize: 13,
                color: "#cbd5e1",
                textAlign: "center",
                lineHeight: 1.5,
              }}
            >
              {"AI 어시스턴트 패널에서 장소 이름을\n클릭하면 상세 정보를 확인할 수 있어요"}
            </span>
          </div>
        ) : (
          <>
            {/* ── Kakao Map ────────────────────────────── */}
            <div
              ref={mapRef}
              style={{
                width: "100%",
                height: 220,
                background: "#e2e8f0",
                flexShrink: 0,
                position: "relative",
              }}
            >
              {(!place.x || !place.y) && (
                <div
                  style={{
                    position: "absolute",
                    inset: 0,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "#94a3b8",
                    fontSize: 14,
                  }}
                >
                  좌표 정보가 없어 지도를 표시할 수 없습니다
                </div>
              )}
            </div>

            {/* ── Info section ─────────────────────────── */}
            <div
              style={{
                padding: "20px 20px 0",
                display: "flex",
                flexDirection: "column",
                gap: 16,
              }}
            >
              {/* Name */}
              <h4
                style={{
                  fontSize: 22,
                  fontWeight: 600,
                  color: "#1e293b",
                  margin: 0,
                }}
              >
                {place.name}
              </h4>

              {/* Category */}
              {place.category && (
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span
                    style={{
                      fontSize: 12,
                      fontWeight: 500,
                      color: "#4f46e5",
                      backgroundColor: "#eef2ff",
                      padding: "3px 10px",
                      borderRadius: 6,
                    }}
                  >
                    {place.category.split(" > ").pop()}
                  </span>
                  {place.score != null && (
                    <span
                      style={{
                        fontSize: 12,
                        fontWeight: 600,
                        color: "#4f46e5",
                        backgroundColor: "#eef2ff",
                        padding: "3px 10px",
                        borderRadius: 6,
                      }}
                    >
                      추천 {Math.round(place.score * 100)}%
                    </span>
                  )}
                </div>
              )}

              {/* Divider */}
              <div style={{ height: 1, background: "#e2e8f0" }} />

              {/* Details list */}
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {/* Address */}
                <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                  <MapPin
                    style={{
                      width: 16,
                      height: 16,
                      color: "#94a3b8",
                      marginTop: 2,
                      flexShrink: 0,
                    }}
                  />
                  <span style={{ fontSize: 14, fontWeight: 400, color: "#475569", lineHeight: 1.5 }}>
                    {place.address}
                  </span>
                </div>

                {/* Phone */}
                {place.phone && (
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <Phone
                      style={{
                        width: 16,
                        height: 16,
                        color: "#94a3b8",
                        flexShrink: 0,
                      }}
                    />
                    <span style={{ fontSize: 14, fontWeight: 400, color: "#475569" }}>
                      {place.phone}
                    </span>
                  </div>
                )}

                {/* Kakao Map link */}
                {place.url && (
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <ExternalLink
                      style={{
                        width: 16,
                        height: 16,
                        color: "#94a3b8",
                        flexShrink: 0,
                      }}
                    />
                    <a
                      href={place.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        fontSize: 14,
                        fontWeight: 500,
                        color: "#4f46e5",
                        textDecoration: "none",
                      }}
                    >
                      카카오맵에서 보기
                    </a>
                  </div>
                )}

                {/* Distance */}
                {distanceLabel && (
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <Navigation
                      style={{
                        width: 16,
                        height: 16,
                        color: "#94a3b8",
                        flexShrink: 0,
                      }}
                    />
                    <span style={{ fontSize: 14, fontWeight: 400, color: "#475569" }}>
                      중심지에서 {distanceLabel}
                    </span>
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </div>

      {/* Bottom button */}
      <div style={{ padding: "16px 20px 20px" }}>
        {confirmed ? (
          <div
            style={{
              width: "100%",
              padding: "12px 20px",
              borderRadius: 12,
              background: "#ecfdf5",
              border: "1px solid #86efac",
              color: "#166534",
              fontSize: 14,
              fontWeight: 600,
              textAlign: "center",
            }}
          >
            이 장소가 확정되었습니다
          </div>
        ) : (
          <button
            onClick={handleSelect}
            disabled={!place || !hasValidRoom}
            style={{
              width: "100%",
              height: 44,
              background: place && hasValidRoom ? "#4f46e5" : "#cbd5e1",
              color: "#ffffff",
              fontSize: 14,
              fontWeight: 500,
              borderRadius: 12,
              border: "none",
              cursor: place ? "pointer" : "not-allowed",
              fontFamily: "Pretendard Variable, Pretendard, sans-serif",
            }}
          >
            이 장소로 확정
          </button>
        )}
      </div>
    </div>
  );
}
