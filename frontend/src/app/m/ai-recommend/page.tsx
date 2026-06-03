"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Calendar,
  Users,
  MapPin,
  Wallet,
  ChevronRight,
  Sparkles,
  Minus,
  Plus,
} from "lucide-react";

const MEETING_TYPES = ["회식", "스터디", "운동", "여행", "기타"] as const;
const FOOD_CATS_ROW1 = ["한식", "일식", "양식"] as const;
const FOOD_CATS_ROW2 = ["중식", "카페", "기타"] as const;
const BUDGETS = ["인당 1만원", "인당 2만원", "인당 3만원", "인당 5만원"] as const;

export default function AiRecommendPage() {
  const router = useRouter();

  const [meetingType, setMeetingType] = useState<string>("회식");
  const [foodCat, setFoodCat] = useState<string>("한식");
  const [budget, setBudget] = useState<string>("인당 2만원");
  const [count, setCount] = useState(4);
  const [locationPath, setLocationPath] = useState<string>("");
  const [loading, setLoading] = useState(false);

  // Read location back from session when returning from wizard
  useEffect(() => {
    try {
      const raw = sessionStorage.getItem("locationWizard");
      if (raw) {
        const { province, city, district } = JSON.parse(raw) as Record<string, string>;
        const parts = [province, city, district].filter(Boolean);
        if (parts.length > 0) setLocationPath(parts.join(" > "));
      }
    } catch {}
  }, []);

  const decrement = () => setCount((c) => Math.max(2, c - 1));
  const increment = () => setCount((c) => Math.min(20, c + 1));

  const handleStart = () => {
    setLoading(true);
    try {
      sessionStorage.setItem(
        "meetingWizard",
        JSON.stringify({ meetingType, foodCategory: foodCat, locationPath, count })
      );
    } catch {}
    router.push("/m/place/ai-result");
  };

  return (
    <div
      style={{
        width: "100%",
        height: "var(--m-screen-h)",
        background: "#ffffff",
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
          모임 조건 설정
        </span>
      </div>

      {/* Body */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: 20,
          display: "flex",
          flexDirection: "column",
          gap: 16,
        }}
      >
        {/* Date row */}
        <div
          style={{
            borderRadius: 12,
            background: "#ffffff",
            border: "1px solid #e2e8f0",
            padding: "14px 16px",
            display: "flex",
            alignItems: "center",
            gap: 12,
          }}
        >
          <Calendar size={18} color="#4f46e5" style={{ flexShrink: 0 }} />
          <span style={{ fontSize: 14, fontWeight: 500, color: "#1e293b" }}>
            가능한 날짜를 선택하세요
          </span>
        </div>

        {/* People count row */}
        <div
          style={{
            borderRadius: 12,
            background: "#ffffff",
            border: "1px solid #e2e8f0",
            padding: "12px 16px",
            display: "flex",
            alignItems: "center",
            gap: 12,
          }}
        >
          <Users size={18} color="#4f46e5" style={{ flexShrink: 0 }} />
          <span style={{ fontSize: 14, fontWeight: 500, color: "#1e293b", flex: 1 }}>
            {count}명
          </span>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <button
              onClick={decrement}
              style={{
                width: 32,
                height: 32,
                borderRadius: 16,
                background: "#f1f5f9",
                border: "1px solid #e2e8f0",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                cursor: "pointer",
              }}
            >
              <Minus size={14} color="#64748b" />
            </button>
            <button
              onClick={increment}
              style={{
                width: 32,
                height: 32,
                borderRadius: 16,
                background: "#eef2ff",
                border: "1px solid #c7d2fe",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                cursor: "pointer",
              }}
            >
              <Plus size={14} color="#4f46e5" />
            </button>
          </div>
        </div>

        {/* Location row */}
        <div
          onClick={() => router.push("/m/place/region?from=ai-recommend")}
          style={{
            borderRadius: 12,
            background: "#ffffff",
            border: "1px solid #e2e8f0",
            padding: "14px 16px",
            display: "flex",
            alignItems: "center",
            gap: 12,
            cursor: "pointer",
          }}
        >
          <MapPin size={18} color="#4f46e5" style={{ flexShrink: 0 }} />
          <span
            style={{
              fontSize: 14,
              fontWeight: 500,
              color: locationPath ? "#1e293b" : "#94a3b8",
              flex: 1,
            }}
          >
            {locationPath || "지역을 선택하세요"}
          </span>
          <ChevronRight size={16} color="#94a3b8" style={{ flexShrink: 0 }} />
        </div>

        {/* Meeting type */}
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <span style={{ fontSize: 14, fontWeight: 700, color: "#1e293b" }}>
            모임 종류
          </span>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {MEETING_TYPES.map((t) => {
              const sel = meetingType === t;
              return (
                <button
                  key={t}
                  onClick={() => setMeetingType(t)}
                  style={{
                    borderRadius: 20,
                    background: sel ? "#4f46e5" : "#f8fafc",
                    border: sel ? "none" : "1px solid #e2e8f0",
                    padding: "8px 16px",
                    fontSize: 13,
                    fontWeight: sel ? 600 : 500,
                    color: sel ? "#ffffff" : "#64748b",
                    cursor: "pointer",
                    fontFamily: "Pretendard, sans-serif",
                  }}
                >
                  {t}
                </button>
              );
            })}
          </div>
        </div>

        {/* Food category */}
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <span style={{ fontSize: 14, fontWeight: 700, color: "#1e293b" }}>
            음식 카테고리
          </span>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <div style={{ display: "flex", gap: 8 }}>
              {FOOD_CATS_ROW1.map((f) => {
                const sel = foodCat === f;
                return (
                  <button
                    key={f}
                    onClick={() => setFoodCat(f)}
                    style={{
                      flex: 1,
                      borderRadius: 10,
                      background: sel ? "#4f46e5" : "#f8fafc",
                      border: sel ? "none" : "1px solid #e2e8f0",
                      padding: "10px 0",
                      fontSize: 13,
                      fontWeight: sel ? 600 : 500,
                      color: sel ? "#ffffff" : "#64748b",
                      cursor: "pointer",
                      fontFamily: "Pretendard, sans-serif",
                    }}
                  >
                    {f}
                  </button>
                );
              })}
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              {FOOD_CATS_ROW2.map((f) => {
                const sel = foodCat === f;
                return (
                  <button
                    key={f}
                    onClick={() => setFoodCat(f)}
                    style={{
                      flex: 1,
                      borderRadius: 10,
                      background: sel ? "#4f46e5" : "#f8fafc",
                      border: sel ? "none" : "1px solid #e2e8f0",
                      padding: "10px 0",
                      fontSize: 13,
                      fontWeight: sel ? 600 : 500,
                      color: sel ? "#ffffff" : "#64748b",
                      cursor: "pointer",
                      fontFamily: "Pretendard, sans-serif",
                    }}
                  >
                    {f}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Budget row */}
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <span style={{ fontSize: 14, fontWeight: 700, color: "#1e293b" }}>
            예산
          </span>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {BUDGETS.map((b) => {
              const sel = budget === b;
              return (
                <button
                  key={b}
                  onClick={() => setBudget(b)}
                  style={{
                    borderRadius: 20,
                    background: sel ? "#4f46e5" : "#f8fafc",
                    border: sel ? "none" : "1px solid #e2e8f0",
                    padding: "8px 16px",
                    fontSize: 13,
                    fontWeight: sel ? 600 : 500,
                    color: sel ? "#ffffff" : "#64748b",
                    cursor: "pointer",
                    fontFamily: "Pretendard, sans-serif",
                  }}
                >
                  <Wallet size={12} style={{ display: "inline", marginRight: 4, verticalAlign: "middle" }} />
                  {b}
                </button>
              );
            })}
          </div>
        </div>

        {/* Divider */}
        <div style={{ height: 1, background: "#f1f5f9" }} />

        {/* AI waiting area */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 12,
            padding: "8px 0",
          }}
        >
          <div
            style={{
              width: 64,
              height: 64,
              borderRadius: 32,
              background: "radial-gradient(circle, #4f46e5, #a855f7)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Sparkles size={28} color="#ffffff" />
          </div>
          <span style={{ fontSize: 15, fontWeight: 700, color: "#1e293b" }}>
            AI가 최적의 장소를 찾고 있어요
          </span>
          <span style={{ fontSize: 12, color: "#64748b", textAlign: "center", lineHeight: 1.6 }}>
            조건을 입력하면 AI가 모임에 딱 맞는<br />장소를 추천해드려요
          </span>

          {/* Tip cards */}
          <div style={{ display: "flex", gap: 8, width: "100%" }}>
            {[
              { bg: "#eef2ff", border: "#c7d2fe", text: "맛집 평점 반영", color: "#4f46e5" },
              { bg: "#f0fdf4", border: "#bbf7d0", text: "이동 거리 최적화", color: "#16a34a" },
              { bg: "#fef3c7", border: "#fde68a", text: "분위기 매칭", color: "#b45309" },
            ].map(({ bg, border, text, color }) => (
              <div
                key={text}
                style={{
                  flex: 1,
                  borderRadius: 10,
                  background: bg,
                  border: `1px solid ${border}`,
                  padding: "10px 8px",
                  textAlign: "center",
                }}
              >
                <span style={{ fontSize: 11, fontWeight: 600, color }}>{text}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* CTA */}
      <div style={{ padding: "12px 20px 24px", background: "#ffffff" }}>
        <button
          onClick={handleStart}
          disabled={loading}
          style={{
            width: "100%",
            height: 52,
            borderRadius: 14,
            background: loading
              ? "#a5b4fc"
              : "linear-gradient(90deg, #4f46e5, #6366f1)",
            border: "none",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 8,
            cursor: loading ? "not-allowed" : "pointer",
            fontFamily: "Pretendard, sans-serif",
          }}
        >
          <Sparkles size={18} color="#ffffff" />
          <span style={{ fontSize: 16, fontWeight: 700, color: "#ffffff" }}>
            {loading ? "AI 분석 중…" : "AI 추천 시작하기"}
          </span>
        </button>
      </div>
    </div>
  );
}
