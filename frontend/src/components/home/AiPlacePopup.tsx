"use client";

import { useState } from "react";
import { MapPin, Star, Sparkles } from "lucide-react";

interface Props {
  open: boolean;
  onClose: () => void;
}

const categories = [
  { label: "카페", icon: "☕", active: true },
  { label: "식당", icon: "🍽️", active: false },
  { label: "술집", icon: "🍺", active: false },
  { label: "활동", icon: "🎯", active: false },
];

const places = [
  {
    name: "숲속 카페",
    badge: "AI 추천",
    detail: "강남역 3번출구 도보 5분 · 조용한 분위기",
    rating: "4.7",
    reviews: "리뷰 234개",
    highlight: true,
  },
  {
    name: "블루보틀 강남점",
    badge: null,
    detail: "강남역 1번출구 도보 3분 · 넓은 좌석",
    rating: "4.5",
    reviews: "리뷰 189개",
    highlight: false,
  },
  {
    name: "토즈 스터디센터",
    badge: null,
    detail: "강남역 5번출구 도보 7분 · 프라이빗룸",
    rating: "4.3",
    reviews: "리뷰 156개",
    highlight: false,
  },
];

export default function AiPlacePopup({ open, onClose }: Props) {
  const [selectedCat, setSelectedCat] = useState(0);
  if (!open) return null;

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
            <span style={{ fontSize: 12, fontWeight: 500, color: "#0ea5e9" }}>강남역 근처</span>
          </div>

          {places.map((p) => (
            <div
              key={p.name}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 14,
                padding: 14,
                borderRadius: 14,
                background: p.highlight ? "#f0fdf4" : "#ffffff",
                border: p.highlight ? "1px solid #bbf7d0" : "1px solid #e2e8f0",
                cursor: "pointer",
              }}
            >
              <div
                style={{
                  width: 56,
                  height: 56,
                  borderRadius: 12,
                  background: "#e2e8f0",
                  flexShrink: 0,
                }}
              />
              <div style={{ display: "flex", flexDirection: "column", gap: 4, flex: 1 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span style={{ fontSize: 14, fontWeight: 600, color: "#1e293b" }}>{p.name}</span>
                  {p.badge && (
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
                      {p.badge}
                    </span>
                  )}
                </div>
                <span style={{ fontSize: 11, color: "#64748b" }}>{p.detail}</span>
                <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <Star size={12} color="#f59e0b" fill="#f59e0b" />
                  <span style={{ fontSize: 11, color: "#94a3b8" }}>
                    {p.rating} · {p.reviews}
                  </span>
                </div>
              </div>
            </div>
          ))}
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
            장소 추천받기
          </button>
        </div>
      </div>
    </div>
  );
}
