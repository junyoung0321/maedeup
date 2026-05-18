"use client";

import { useEffect, useState } from "react";
import { MapPin, Sparkles, Loader2 } from "lucide-react";
import { apiFetch } from "@/lib/api";

interface Props {
  open: boolean;
  onClose: () => void;
}

const categories = [
  { label: "카페", icon: "☕" },
  { label: "식당", icon: "🍽️" },
  { label: "술집", icon: "🍺" },
  { label: "활동", icon: "🎯" },
];

interface Place {
  id: string;
  name: string;
  address: string;
  distance_label?: string | null;
  category: string;
  url: string;
}

interface NearbyPlacesResponse {
  home_base?: string | null;
  category: string;
  places: Place[];
  reason?: string | null;
}

export default function AiPlacePopup({ open, onClose }: Props) {
  const [selectedCat, setSelectedCat] = useState(0);
  const [data, setData] = useState<NearbyPlacesResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    const cat = categories[selectedCat].label;
    setLoading(true);
    const run = async () => {
      let district = "";
      try {
        const raw = sessionStorage.getItem("locationWizard");
        if (raw) {
          const parsed = JSON.parse(raw) as Record<string, string>;
          district = parsed.district ?? "";
        }
      } catch {}
      if (district) {
        await apiFetch("/api/v1/users/me/preferences", {
          method: "PATCH",
          body: JSON.stringify({ home_base: district }),
        }).catch(() => null);
      }
      const result = await apiFetch<NearbyPlacesResponse>(
        `/api/v1/recommendations/nearby-places?category=${encodeURIComponent(cat)}&limit=3`
      ).catch(() => null);
      setData(result);
    };
    run().finally(() => setLoading(false));
  }, [open, selectedCat]);

  if (!open) return null;

  const places = data?.places ?? [];
  const homeBase = data?.home_base;
  const reason = data?.reason;

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 100,
        background: "rgba(0,0,0,0.5)",
        display: "flex",
        flexDirection: "column",
        justifyContent: "flex-end",
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 390,
          maxWidth: "100%",
          alignSelf: "center",
          borderRadius: "24px 24px 0 0",
          background: "#ffffff",
          display: "flex",
          flexDirection: "column",
          fontFamily: "Pretendard, sans-serif",
          overflow: "hidden",
        }}
      >
        {/* Handle */}
        <div
          style={{
            height: 28,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <div style={{ width: 40, height: 4, borderRadius: 2, background: "#d1d5db" }} />
        </div>

        {/* Header */}
        <div style={{ padding: "0 24px 16px", display: "flex", flexDirection: "column", gap: 8 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <MapPin size={22} color="#0ea5e9" />
            <span style={{ fontSize: 20, fontWeight: 700, color: "#1e293b" }}>AI 장소 추천</span>
          </div>
          <span style={{ fontSize: 13, color: "#64748b" }}>
            모임 목적과 위치에 맞는 최적의 장소를 AI가 추천해드려요
          </span>
        </div>

        {/* Categories */}
        <div style={{ padding: "0 24px 16px", display: "flex", flexDirection: "column", gap: 12 }}>
          <span style={{ fontSize: 15, fontWeight: 600, color: "#1e293b" }}>모임 유형 선택</span>
          <div style={{ display: "flex", gap: 8 }}>
            {categories.map((cat, i) => (
              <button
                key={cat.label}
                onClick={() => setSelectedCat(i)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  height: 36,
                  padding: "0 16px",
                  borderRadius: 18,
                  border: selectedCat === i ? "none" : "1px solid #e2e8f0",
                  background: selectedCat === i ? "#4f46e5" : "#ffffff",
                  color: selectedCat === i ? "#ffffff" : "#1e293b",
                  fontSize: 13,
                  fontWeight: 500,
                  cursor: "pointer",
                  fontFamily: "Pretendard, sans-serif",
                }}
              >
                <span>{cat.icon}</span>
                {cat.label}
              </button>
            ))}
          </div>
        </div>

        {/* Places */}
        <div
          style={{
            padding: "0 24px",
            display: "flex",
            flexDirection: "column",
            gap: 12,
            flex: 1,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 15, fontWeight: 600, color: "#1e293b" }}>추천 장소</span>
            {homeBase && (
              <span style={{ fontSize: 12, fontWeight: 500, color: "#0ea5e9" }}>
                {homeBase} 근처
              </span>
            )}
          </div>

          {loading ? (
            <div style={{ display: "flex", justifyContent: "center", padding: "24px 0" }}>
              <Loader2 size={24} color="#0ea5e9" className="animate-spin" />
            </div>
          ) : places.length > 0 ? (
            places.map((p, idx) => (
              <div
                key={p.id}
                onClick={() => p.url && window.open(p.url, "_blank")}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 14,
                  padding: 14,
                  borderRadius: 14,
                  background: idx === 0 ? "#f0fdf4" : "#ffffff",
                  border: idx === 0 ? "1px solid #bbf7d0" : "1px solid #e2e8f0",
                  cursor: p.url ? "pointer" : "default",
                }}
              >
                <div
                  style={{
                    width: 56,
                    height: 56,
                    borderRadius: 12,
                    background: "#e2e8f0",
                    flexShrink: 0,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 24,
                  }}
                >
                  {categories[selectedCat].icon}
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 4, flex: 1 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <span style={{ fontSize: 14, fontWeight: 600, color: "#1e293b" }}>
                      {p.name}
                    </span>
                    {idx === 0 && (
                      <span
                        style={{
                          fontSize: 10,
                          fontWeight: 600,
                          color: "#16a34a",
                          background: "#dcfce7",
                          borderRadius: 10,
                          padding: "0 8px",
                          height: 20,
                          display: "flex",
                          alignItems: "center",
                        }}
                      >
                        AI 추천
                      </span>
                    )}
                  </div>
                  <span style={{ fontSize: 11, color: "#64748b" }}>
                    {p.address}
                    {p.distance_label ? ` · 도보 ${p.distance_label}` : ""}
                  </span>
                </div>
              </div>
            ))
          ) : reason ? (
            <div style={{ padding: "16px 0", textAlign: "center" }}>
              <span style={{ fontSize: 13, color: "#94a3b8" }}>{reason}</span>
            </div>
          ) : (
            <div style={{ padding: "16px 0", textAlign: "center" }}>
              <span style={{ fontSize: 13, color: "#94a3b8" }}>추천 장소를 찾을 수 없습니다</span>
            </div>
          )}
        </div>

        {/* Button */}
        <div style={{ padding: "16px 24px 34px" }}>
          <button
            onClick={onClose}
            style={{
              width: "100%",
              height: 50,
              borderRadius: 14,
              border: "none",
              background: "linear-gradient(160deg, #0ea5e9, #22c55e)",
              color: "#ffffff",
              fontSize: 16,
              fontWeight: 600,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 8,
              fontFamily: "Pretendard, sans-serif",
            }}
          >
            <Sparkles size={18} color="#ffffff" />
            확인
          </button>
        </div>
      </div>
    </div>
  );
}
