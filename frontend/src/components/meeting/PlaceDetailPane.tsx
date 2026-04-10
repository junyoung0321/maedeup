"use client";

import { MapPin, Phone, ExternalLink } from "lucide-react";
import { apiFetch } from "@/lib/api";
import type { PlaceResult } from "@/types";

interface Props {
  place: PlaceResult | null;
}

export default function PlaceDetailPane({ place }: Props) {
  const handleSelect = async () => {
    if (!place) return;
    const now = new Date().toISOString();
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
      }),
    }).catch(() => { /* API unavailable */ });
  };

  return (
    <div
      className="w-[414px] h-[733px] bg-white rounded-[20px] flex flex-col overflow-hidden"
      style={{
        border: "1px solid #e2e8f0",
        boxShadow: "0 4px 3.5px rgba(0,0,0,0.25)",
        fontFamily: "Pretendard Variable, Pretendard, sans-serif",
      }}
    >
      {/* Header */}
      <div className="px-5 py-4 border-b border-slate-200" style={{ background: "#f2f4f7" }}>
        <h3
          style={{
            fontSize: 26,
            fontWeight: 400,
            color: "#000000",
            letterSpacing: 0.75,
          }}
        >
          세부 사항
        </h3>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-5">
        {!place ? (
          <div
            style={{
              flex: 1,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 15,
              fontWeight: 300,
              color: "#94a3b8",
            }}
          >
            장소를 선택해주세요
          </div>
        ) : (
          <>
            {/* Name */}
            <div>
              <h4
                style={{
                  fontSize: 22,
                  fontWeight: 300,
                  color: "#1e293b",
                  margin: 0,
                }}
              >
                {place.name}
              </h4>

              {/* Category */}
              {place.category && (
                <div className="flex items-center gap-1.5 mt-2">
                  <span
                    style={{
                      fontSize: 12,
                      fontWeight: 300,
                      color: "#4f46e5",
                      backgroundColor: "#eef2ff",
                      padding: "2px 8px",
                      borderRadius: 4,
                    }}
                  >
                    {place.category.split(" > ").pop()}
                  </span>
                </div>
              )}
            </div>

            {/* Address / Phone / URL */}
            <div className="flex flex-col gap-2">
              <div className="flex items-start gap-2">
                <MapPin className="w-4 h-4 mt-0.5 shrink-0" style={{ color: "#94a3b8" }} />
                <span style={{ fontSize: 13, fontWeight: 300, color: "#64748b" }}>
                  {place.address}
                </span>
              </div>
              {place.phone && (
                <div className="flex items-center gap-2">
                  <Phone className="w-4 h-4 shrink-0" style={{ color: "#94a3b8" }} />
                  <span style={{ fontSize: 13, fontWeight: 300, color: "#64748b" }}>
                    {place.phone}
                  </span>
                </div>
              )}
              {place.url && (
                <div className="flex items-center gap-2">
                  <ExternalLink className="w-4 h-4 shrink-0" style={{ color: "#94a3b8" }} />
                  <a
                    href={place.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ fontSize: 13, fontWeight: 300, color: "#4f46e5" }}
                  >
                    카카오맵에서 보기
                  </a>
                </div>
              )}
            </div>
          </>
        )}
      </div>

      {/* Bottom buttons */}
      <div className="p-5 flex gap-3">
        <button
          onClick={handleSelect}
          disabled={!place}
          className="flex-1 rounded-xl transition-colors hover:opacity-90"
          style={{
            fontSize: 14,
            fontWeight: 300,
            color: "#ffffff",
            backgroundColor: place ? "#4f46e5" : "#cbd5e1",
            padding: "10px 20px",
            cursor: place ? "pointer" : "not-allowed",
          }}
        >
          이 장소로 선택
        </button>
        <button
          className="flex-1 rounded-xl transition-colors hover:opacity-90"
          style={{
            fontSize: 14,
            fontWeight: 300,
            color: "#64748b",
            backgroundColor: "#ffffff",
            border: "1px solid #e2e8f0",
            padding: "10px 20px",
          }}
        >
          공유하기
        </button>
      </div>
    </div>
  );
}
