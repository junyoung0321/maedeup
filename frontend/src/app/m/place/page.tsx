"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  Menu,
  Sparkles,
  Radar,
  UtensilsCrossed,
  MapPin,
  Loader2,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import type { Room, NearbyPlacesResponse, NearbyPlace } from "@/types";

const GRADIENT_PALETTES = [
  "linear-gradient(135deg, #d4c5a9 0%, #c4b597 50%, #b8a98a 100%)",
  "linear-gradient(135deg, #8b7355 0%, #a0896d 50%, #6b5b45 100%)",
  "linear-gradient(135deg, #a8c5da 0%, #7fb3cc 50%, #5a9ab8 100%)",
  "linear-gradient(135deg, #c5dab0 0%, #a8c87d 50%, #8fb563 100%)",
  "linear-gradient(135deg, #dab0c5 0%, #c87da8 50%, #b5638f 100%)",
];

function PlaceRecommendPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const roomId = searchParams.get("roomId") ?? "";
  const { user, loading: authLoading } = useAuth();

  const [room, setRoom] = useState<Room | null>(null);
  const [placesData, setPlacesData] = useState<NearbyPlacesResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (authLoading || !user || !roomId) return;
    apiFetch<Room>(`/api/v1/rooms/${roomId}`)
      .then(setRoom)
      .catch(() => null);
    apiFetch<NearbyPlacesResponse>("/api/v1/recommendations/nearby-places?category=카페&limit=5")
      .then(setPlacesData)
      .catch(() => null)
      .finally(() => setLoading(false));
  }, [authLoading, user, roomId]);

  function handlePlaceClick(place: NearbyPlace) {
    sessionStorage.setItem("selectedPlace", JSON.stringify(place));
    router.push(`/m/place/detail?roomId=${roomId}`);
  }

  const roomName = room?.name ?? "모임";
  const places = placesData?.places ?? [];

  return (
    <div
      className="relative mx-auto flex flex-col bg-white"
      style={{ width: 390, height: 844, overflow: "clip" }}
    >
      {/* 1. Header */}
      <div
        className="flex items-center shrink-0"
        style={{ height: 56, padding: "0 16px", borderBottom: "1px solid #e2e8f0", backgroundColor: "#ffffff" }}
      >
        <ArrowLeft size={24} color="#1e293b" className="shrink-0 cursor-pointer" onClick={() => router.push(`/m/chat/place?roomId=${roomId}`)} />
        <div className="flex-1 flex flex-col items-center gap-[2px]">
          <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 17, fontWeight: 600, color: "#1e293b" }}>
            {roomName}
          </span>
          <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 12, fontWeight: 400, color: "#94a3b8" }}>
            {room?.category ?? "모임"}
          </span>
        </div>
        <Menu size={24} color="#64748b" className="shrink-0 cursor-pointer" onClick={() => router.push("/m/meeting/detail")} />
      </div>

      {/* 2. Tabs */}
      <div
        className="flex shrink-0"
        style={{ height: 44, backgroundColor: "#ffffff", borderBottom: "1px solid #e2e8f0" }}
      >
        <div
          className="flex-1 flex items-center justify-center cursor-pointer"
          onClick={() => router.push(`/m/chat/place?roomId=${roomId}`)}
          style={{ fontFamily: "Pretendard, sans-serif", fontSize: 14, fontWeight: 500, color: "#94a3b8" }}
        >
          채팅방
        </div>
        <div
          className="flex-1 flex items-center justify-center"
          style={{ fontFamily: "Pretendard, sans-serif", fontSize: 14, fontWeight: 600, color: "#4f46e5", borderBottom: "2px solid #4f46e5" }}
        >
          장소 선택
        </div>
      </div>

      {/* 3. Content */}
      <div
        className="flex-1 flex flex-col overflow-y-auto"
        style={{ padding: "14px 16px 16px 16px", gap: 14 }}
      >
        {/* Detect Banner */}
        <div
          className="flex items-center shrink-0"
          style={{ height: 32, borderRadius: 16, backgroundColor: "#eef2ff", padding: "0 12px", gap: 6 }}
        >
          <Radar size={14} color="#4f46e5" className="shrink-0" />
          <span style={{ fontFamily: "Inter, sans-serif", fontSize: 10, fontWeight: 600, color: "#4f46e5" }}>
            채팅방에서 장소 관련 대화가 감지되었습니다
          </span>
        </div>

        {/* AI Card */}
        <div
          style={{
            borderRadius: 14,
            background: "linear-gradient(-225deg, #4f46e5 0%, #7c3aed 50%, #a855f7 100%)",
            padding: "14px 16px",
            display: "flex",
            flexDirection: "column",
            gap: 8,
            boxShadow: "0 4px 14px #4f46e520",
          }}
        >
          <div className="flex items-center" style={{ gap: 6 }}>
            <Sparkles size={16} color="#ffffff" />
            <span style={{ fontFamily: "Inter, sans-serif", fontSize: 11, fontWeight: 600, color: "#ffffff" }}>AI 어시스턴트</span>
          </div>
          <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 15, fontWeight: 700, color: "#ffffff" }}>
            모임 장소를 추천해드리겠습니다
          </span>
          <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 11, fontWeight: 400, color: "#ffffffcc", lineHeight: 1.5 }}>
            {placesData?.reason ?? "채팅 내용을 분석하여 근처 맛집과 모임 장소를 찾아보았어요."}
          </span>
        </div>

        {/* List Header */}
        <div className="flex items-center" style={{ gap: 6 }}>
          <UtensilsCrossed size={16} color="#4f46e5" />
          <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 14, fontWeight: 700, color: "#1e293b" }}>
            추천 장소
          </span>
          {!loading && (
            <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 12, fontWeight: 500, color: "#94a3b8" }}>
              {places.length}곳
            </span>
          )}
        </div>

        {/* Place List */}
        {loading ? (
          <div className="flex-1 flex items-center justify-center" style={{ paddingTop: 40 }}>
            <Loader2 size={24} color="#4f46e5" className="animate-spin" />
          </div>
        ) : places.length === 0 ? (
          <div style={{ padding: "24px 0", textAlign: "center" }}>
            <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 14, color: "#94a3b8" }}>
              추천 장소를 불러올 수 없습니다
            </span>
          </div>
        ) : (
          <div className="flex flex-col" style={{ gap: 12, overflow: "hidden" }}>
            {places.map((place, i) => (
              <div
                key={place.id}
                onClick={() => handlePlaceClick(place)}
                style={{
                  borderRadius: 12,
                  backgroundColor: "#ffffff",
                  border: "1px solid #e2e8f0",
                  boxShadow: "0 2px 6px #0000001a",
                  overflow: "hidden",
                  cursor: "pointer",
                }}
              >
                {/* Image placeholder */}
                <div style={{ height: 100, width: "100%", background: GRADIENT_PALETTES[i % GRADIENT_PALETTES.length] }} />
                {/* Body */}
                <div className="flex flex-col" style={{ padding: "10px 12px", gap: 6 }}>
                  <div className="flex items-center justify-between">
                    <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 14, fontWeight: 700, color: "#1e293b" }}>
                      {place.name}
                    </span>
                    {place.distance_label && (
                      <span style={{ fontFamily: "Inter, sans-serif", fontSize: 11, fontWeight: 500, color: "#94a3b8" }}>
                        {place.distance_label}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center" style={{ gap: 6 }}>
                    <span
                      style={{
                        fontFamily: "Pretendard, sans-serif",
                        fontSize: 10,
                        fontWeight: 500,
                        color: "#4f46e5",
                        backgroundColor: "#eef2ff",
                        borderRadius: 10,
                        padding: "3px 8px",
                      }}
                    >
                      {place.category}
                    </span>
                  </div>
                  <div className="flex items-center" style={{ gap: 4 }}>
                    <MapPin size={12} color="#94a3b8" className="shrink-0" />
                    <span
                      style={{
                        fontFamily: "Pretendard, sans-serif",
                        fontSize: 11,
                        fontWeight: 400,
                        color: "#64748b",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {place.address}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default function PlaceRecommendPage() {
  return (
    <Suspense fallback={null}>
      <PlaceRecommendPageContent />
    </Suspense>
  );
}
