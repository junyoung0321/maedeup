"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  Sparkles,
  MapPin,
  Star,
  Lightbulb,
  CircleCheck,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import type { NearbyPlacesResponse, NearbyPlace } from "@/types";

interface WizardState {
  meetingType?: string;
  foodCategory?: string;
  locationPath?: string;
}

const TAG_COLORS = [
  { color: "#2563eb", background: "#dbeafe" },
  { color: "#16a34a", background: "#dcfce7" },
  { color: "#b45309", background: "#fef3c7" },
  { color: "#7c3aed", background: "#ede9fe" },
];

function AiResultPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const roomId = searchParams.get("roomId") ?? "";
  const { user, loading: authLoading } = useAuth();

  const [wizard, setWizard] = useState<WizardState>({});
  const [placesData, setPlacesData] = useState<NearbyPlacesResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    try {
      const raw = sessionStorage.getItem("meetingWizard");
      if (raw) setWizard(JSON.parse(raw) as WizardState);
    } catch {}
  }, []);

  useEffect(() => {
    if (authLoading || !user) return;
    const cat = encodeURIComponent(wizard.foodCategory ?? "한식");
    apiFetch<NearbyPlacesResponse>(`/api/v1/recommendations/nearby-places?category=${cat}&limit=5`)
      .then(setPlacesData)
      .catch(() => null)
      .finally(() => setLoading(false));
  }, [authLoading, user, wizard.foodCategory]);

  function handleSelect(place: NearbyPlace) {
    const withReason: NearbyPlace = placesData?.reason
      ? { ...place, ai_reason: placesData.reason }
      : place;
    try {
      sessionStorage.setItem("selectedPlace", JSON.stringify(withReason));
    } catch {}
    router.push(`/m/place/detail?roomId=${roomId}`);
  }

  const places = placesData?.places ?? [];
  const top = places[0] ?? null;
  const rest = places.slice(1, 2);

  const sumItems = [
    { label: "종류", value: wizard.meetingType ?? "회식" },
    { label: "인원", value: "4명" },
    { label: "장소", value: wizard.locationPath?.split(" > ").pop() ?? "미정" },
    { label: "예산", value: "~2.5만" },
    { label: "일시", value: "5/15 목" },
  ];

  return (
    <div
      style={{
        width: "100%",
        height: "100dvh",
        background: "#f8fafc",
        display: "flex",
        flexDirection: "column",
        fontFamily: "Pretendard, sans-serif",
      }}
    >
      {/* Header */}
      <div
        style={{
          height: 56,
          minHeight: 56,
          background: "#4f46e5",
          padding: "0 16px",
          display: "flex",
          alignItems: "center",
          gap: 12,
        }}
      >
        <ArrowLeft
          size={24}
          color="#ffffff"
          style={{ cursor: "pointer" }}
          onClick={() => router.back()}
        />
        <span style={{ fontSize: 18, fontWeight: 700, color: "#ffffff" }}>
          AI 추천 결과
        </span>
      </div>

      {/* Body */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: 16,
          display: "flex",
          flexDirection: "column",
          gap: 14,
        }}
      >
        {/* Summary bar */}
        <div
          style={{
            borderRadius: 12,
            background: "#f5f3ff",
            border: "1px solid #e9d5ff",
            padding: "12px 14px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: 6,
          }}
        >
          {sumItems.map(({ label, value }) => (
            <div
              key={label}
              style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 2, flex: 1, minWidth: 0 }}
            >
              <span style={{ fontSize: 10, fontWeight: 500, color: "#94a3b8" }}>
                {label}
              </span>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  color: "#1e293b",
                  textAlign: "center",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                  width: "100%",
                }}
              >
                {value}
              </span>
            </div>
          ))}
        </div>

        {loading ? (
          <div
            style={{
              flex: 1,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              paddingTop: 40,
            }}
          >
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
              <div
                style={{
                  width: 56,
                  height: 56,
                  borderRadius: 28,
                  background: "radial-gradient(circle, #4f46e5, #a855f7)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <Sparkles size={24} color="#ffffff" />
              </div>
              <span style={{ fontSize: 14, color: "#64748b" }}>AI가 장소를 분석 중입니다…</span>
            </div>
          </div>
        ) : places.length === 0 ? (
          <div style={{ padding: "32px 0", textAlign: "center" }}>
            <span style={{ fontSize: 14, color: "#94a3b8" }}>
              추천 장소를 불러올 수 없습니다
            </span>
          </div>
        ) : (
          <>
            {/* Card 1 — top pick */}
            {top && (
              <div
                onClick={() => handleSelect(top)}
                style={{
                  borderRadius: 14,
                  background: "#eef2ff",
                  border: "1.5px solid #4f46e5",
                  overflow: "hidden",
                  cursor: "pointer",
                }}
              >
                {/* Image */}
                <div
                  style={{
                    height: 100,
                    background: "linear-gradient(135deg, #d4c5a9 0%, #c4b597 50%, #b8a98a 100%)",
                  }}
                />
                {/* Content */}
                <div style={{ padding: "12px 14px", display: "flex", flexDirection: "column", gap: 8 }}>
                  {/* Name row */}
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 700,
                        color: "#ffffff",
                        background: "#4f46e5",
                        borderRadius: 6,
                        padding: "2px 7px",
                      }}
                    >
                      1위
                    </span>
                    <span style={{ fontSize: 15, fontWeight: 700, color: "#1e293b", flex: 1 }}>
                      {top.name}
                    </span>
                    {top.rating != null && (
                      <div style={{ display: "flex", alignItems: "center", gap: 3 }}>
                        <Star size={12} color="#f59e0b" fill="#f59e0b" />
                        <span style={{ fontSize: 12, fontWeight: 600, color: "#1e293b" }}>
                          {top.rating.toFixed(1)}
                        </span>
                      </div>
                    )}
                  </div>
                  {/* Tags */}
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                    {[top.category, top.distance_label].filter(Boolean).map((tag, i) => (
                      <span
                        key={String(tag)}
                        style={{
                          fontSize: 10,
                          fontWeight: 600,
                          color: TAG_COLORS[i % TAG_COLORS.length].color,
                          background: TAG_COLORS[i % TAG_COLORS.length].background,
                          borderRadius: 10,
                          padding: "3px 8px",
                        }}
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                  {/* Address */}
                  <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                    <MapPin size={12} color="#94a3b8" style={{ flexShrink: 0 }} />
                    <span
                      style={{
                        fontSize: 11,
                        color: "#64748b",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {top.address}
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* Card 2+ — secondary picks */}
            {rest.map((place, idx) => (
              <div
                key={place.id}
                onClick={() => handleSelect(place)}
                style={{
                  borderRadius: 14,
                  background: "#ffffff",
                  border: "1px solid #e2e8f0",
                  boxShadow: "0 2px 6px #0000001a",
                  overflow: "hidden",
                  cursor: "pointer",
                }}
              >
                <div
                  style={{
                    height: 100,
                    background: "linear-gradient(135deg, #8b7355 0%, #a0896d 50%, #6b5b45 100%)",
                  }}
                />
                <div style={{ padding: "12px 14px", display: "flex", flexDirection: "column", gap: 8 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 700,
                        color: "#64748b",
                        background: "#f1f5f9",
                        borderRadius: 6,
                        padding: "2px 7px",
                      }}
                    >
                      {idx + 2}위
                    </span>
                    <span style={{ fontSize: 15, fontWeight: 700, color: "#1e293b", flex: 1 }}>
                      {place.name}
                    </span>
                    {place.rating != null && (
                      <div style={{ display: "flex", alignItems: "center", gap: 3 }}>
                        <Star size={12} color="#f59e0b" fill="#f59e0b" />
                        <span style={{ fontSize: 12, fontWeight: 600, color: "#1e293b" }}>
                          {place.rating.toFixed(1)}
                        </span>
                      </div>
                    )}
                  </div>
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                    {[place.category, place.distance_label].filter(Boolean).map((tag, i) => (
                      <span
                        key={String(tag)}
                        style={{
                          fontSize: 10,
                          fontWeight: 600,
                          color: TAG_COLORS[i % TAG_COLORS.length].color,
                          background: TAG_COLORS[i % TAG_COLORS.length].background,
                          borderRadius: 10,
                          padding: "3px 8px",
                        }}
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                    <MapPin size={12} color="#94a3b8" style={{ flexShrink: 0 }} />
                    <span
                      style={{
                        fontSize: 11,
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

            {/* AI reason section */}
            {placesData?.reason && (
              <div
                style={{
                  borderRadius: 12,
                  background: "#f5f3ff",
                  border: "1px solid #e9d5ff",
                  padding: "14px 16px",
                  display: "flex",
                  flexDirection: "column",
                  gap: 8,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <Lightbulb size={14} color="#eab308" />
                  <span style={{ fontSize: 13, fontWeight: 700, color: "#1e293b" }}>
                    AI 추천 이유
                  </span>
                </div>
                <span style={{ fontSize: 12, color: "#374151", lineHeight: 1.7 }}>
                  {placesData.reason}
                </span>
              </div>
            )}
          </>
        )}
      </div>

      {/* CTA */}
      <div style={{ padding: "12px 20px", background: "#f8fafc" }}>
        <button
          onClick={() => top && handleSelect(top)}
          disabled={!top}
          style={{
            width: "100%",
            height: 50,
            borderRadius: 14,
            background: top
              ? "linear-gradient(180deg, #4f46e5, #6366f1)"
              : "#e2e8f0",
            border: "none",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 8,
            cursor: top ? "pointer" : "default",
          }}
        >
          <CircleCheck size={18} color={top ? "#ffffff" : "#94a3b8"} />
          <span
            style={{
              fontSize: 15,
              fontWeight: 700,
              color: top ? "#ffffff" : "#94a3b8",
            }}
          >
            이 장소로 제안하기
          </span>
        </button>
      </div>
    </div>
  );
}

export default function AiResultPage() {
  return (
    <Suspense fallback={null}>
      <AiResultPageContent />
    </Suspense>
  );
}
