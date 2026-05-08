"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  Share2,
  MapPin,
  ExternalLink,
  Sparkles,
} from "lucide-react";
import type { NearbyPlace } from "@/types";

function PlaceDetailPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const roomId = searchParams.get("roomId") ?? "";
  const [place, setPlace] = useState<NearbyPlace | null>(null);

  useEffect(() => {
    try {
      const raw = sessionStorage.getItem("selectedPlace");
      if (raw) setPlace(JSON.parse(raw) as NearbyPlace);
    } catch {
      // sessionStorage unavailable or invalid JSON
    }
  }, []);

  function handleShare() {
    if (place?.url) {
      navigator.clipboard?.writeText(place.url);
    }
    alert("링크가 복사되었습니다!");
  }

  return (
    <div
      className="relative flex flex-col bg-white overflow-hidden"
      style={{ width: 390, height: 844 }}
    >
      {/* Header */}
      <div
        className="flex items-center shrink-0"
        style={{ height: 56, padding: "0 16px", borderBottom: "1px solid #e2e8f0", backgroundColor: "#ffffff" }}
      >
        <ArrowLeft size={24} color="#1e293b" className="shrink-0 cursor-pointer" onClick={() => router.push(`/m/place?roomId=${roomId}`)} />
        <div className="flex flex-col items-center flex-1 gap-[2px]">
          <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 17, fontWeight: 600, color: "#1e293b" }}>
            장소 상세
          </span>
        </div>
        <Share2 size={22} color="#64748b" className="shrink-0 cursor-pointer" onClick={handleShare} />
      </div>

      {/* Hero Image placeholder */}
      <div
        className="shrink-0 w-full"
        style={{
          height: 220,
          background: "linear-gradient(135deg, #b8976a 0%, #8b7355 50%, #6b5842 100%)",
        }}
      />

      {/* Content */}
      <div
        className="flex flex-col flex-1 overflow-y-auto"
        style={{ backgroundColor: "#ffffff", padding: 20, gap: 16 }}
      >
        {!place ? (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", paddingTop: 40 }}>
            <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 14, color: "#94a3b8" }}>
              장소 정보를 불러올 수 없습니다
            </span>
          </div>
        ) : (
          <>
            {/* Name row */}
            <div className="flex items-center justify-between">
              <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 22, fontWeight: 700, color: "#1e293b" }}>
                {place.name}
              </span>
              {place.distance_label && (
                <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 13, fontWeight: 400, color: "#94a3b8" }}>
                  {place.distance_label}
                </span>
              )}
            </div>

            {/* Tag row */}
            <div className="flex items-center" style={{ gap: 8 }}>
              <span
                style={{
                  fontFamily: "Pretendard, sans-serif",
                  fontSize: 12,
                  fontWeight: 500,
                  color: "#4f46e5",
                  backgroundColor: "#eef2ff",
                  borderRadius: 999,
                  padding: "4px 10px",
                }}
              >
                {place.category}
              </span>
            </div>

            {/* Divider */}
            <div style={{ height: 1, backgroundColor: "#f1f5f9" }} />

            {/* Info section */}
            <div className="flex flex-col" style={{ gap: 12 }}>
              <div className="flex items-start" style={{ gap: 10 }}>
                <MapPin size={16} color="#94a3b8" className="shrink-0" style={{ marginTop: 2 }} />
                <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 14, fontWeight: 400, color: "#374151", lineHeight: 1.5 }}>
                  {place.address}
                </span>
              </div>
              {place.url && (
                <a
                  href={place.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center"
                  style={{ gap: 10, textDecoration: "none" }}
                >
                  <ExternalLink size={16} color="#94a3b8" className="shrink-0" />
                  <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 14, fontWeight: 400, color: "#4f46e5" }}>
                    카카오맵에서 보기
                  </span>
                </a>
              )}
            </div>

            {/* Divider */}
            <div style={{ height: 1, backgroundColor: "#f1f5f9" }} />

            {/* AI Recommend card */}
            <div
              className="flex flex-col"
              style={{ borderRadius: 12, backgroundColor: "#f5f3ff", border: "1px solid #e0e7ff", padding: 16, gap: 8 }}
            >
              <div className="flex items-center" style={{ gap: 6 }}>
                <Sparkles size={16} color="#4f46e5" />
                <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 13, fontWeight: 600, color: "#4f46e5" }}>
                  AI 추천 이유
                </span>
              </div>
              <span
                style={{ fontFamily: "Pretendard, sans-serif", fontSize: 13, fontWeight: 400, color: "#374151", lineHeight: 1.6 }}
              >
                모임 인원에 적합한 장소로, 접근성이 좋고 분위기가 쾌적합니다.
              </span>
            </div>
          </>
        )}
      </div>

      {/* Button area */}
      <div
        className="shrink-0"
        style={{ backgroundColor: "#ffffff", padding: "12px 20px", borderTop: "1px solid #e2e8f0" }}
      >
        <button
          className="flex items-center justify-center w-full cursor-pointer"
          onClick={() => router.push(`/m/meeting/confirm?roomId=${roomId}`)}
          style={{ borderRadius: 12, backgroundColor: "#4f46e5", height: 48, gap: 8, border: "none" }}
        >
          <MapPin size={18} color="#ffffff" />
          <span style={{ fontFamily: "Pretendard, sans-serif", fontSize: 15, fontWeight: 600, color: "#ffffff" }}>
            이 장소로 선택하기
          </span>
        </button>
      </div>

      {/* Home bar */}
      <div className="flex items-center justify-center shrink-0" style={{ height: 20, backgroundColor: "#ffffff" }}>
        <div style={{ width: 134, height: 5, borderRadius: 999, backgroundColor: "#000000" }} />
      </div>
    </div>
  );
}

export default function PlaceDetailPage() {
  return (
    <Suspense fallback={null}>
      <PlaceDetailPageContent />
    </Suspense>
  );
}
