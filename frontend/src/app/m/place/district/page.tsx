"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, MapPin } from "lucide-react";

const DISTRICTS_BY_CITY: Record<string, string[]> = {
  수원시: ["영통동", "매탄동", "원천동", "이의동", "하동", "광교동", "망포동", "태장동", "신동", "권선동", "인계동", "팔달로"],
  성남시: ["분당동", "정자동", "서현동", "야탑동", "이매동", "수내동", "금곡동", "운중동", "판교동", "중원동"],
  용인시: ["기흥동", "보정동", "죽전동", "동백동", "영덕동", "신갈동", "구성동", "마북동", "상현동", "수지동"],
  강남구: ["역삼동", "삼성동", "청담동", "논현동", "개포동", "수서동", "일원동", "도곡동", "대치동", "압구정동"],
  마포구: ["홍익동", "합정동", "망원동", "연남동", "상암동", "공덕동", "아현동", "도화동", "신수동", "용강동"],
};

const DEFAULT_DISTRICTS = ["영통동", "매탄동", "원천동", "이의동", "하동", "광교동", "망포동", "태장동", "신동", "권선동", "인계동", "팔달로"];

function DistrictPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const roomId = searchParams.get("roomId") ?? "";
  const from = searchParams.get("from") ?? "";

  const [province, setProvince] = useState("");
  const [city, setCity] = useState("");
  const [selected, setSelected] = useState("");
  const [query, setQuery] = useState("");

  useEffect(() => {
    try {
      const raw = sessionStorage.getItem("locationWizard");
      if (raw) {
        const { province: p, city: c } = JSON.parse(raw) as Record<string, string>;
        if (p) setProvince(p);
        if (c) setCity(c);
      }
    } catch {}
  }, []);

  const districts = DISTRICTS_BY_CITY[city] ?? DEFAULT_DISTRICTS;
  const filtered = districts.filter((d) => d.includes(query));

  function handleConfirm() {
    if (!selected) return;
    try {
      const prev = JSON.parse(sessionStorage.getItem("locationWizard") ?? "{}");
      sessionStorage.setItem(
        "locationWizard",
        JSON.stringify({ ...prev, district: selected })
      );
    } catch {}
    if (from === "ai-recommend") {
      router.push("/m/ai-recommend");
    } else {
      router.push(`/m/meeting/setup?roomId=${roomId}`);
    }
  }

  const pathLabel = [province, city].filter(Boolean).join(" > ");

  return (
    <div
      style={{
        width: "100%",
        height: "844px",
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
        <span style={{ fontSize: 17, fontWeight: 600, color: "#ffffff" }}>
          {city || "장소 선택"}
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
        {/* Breadcrumb */}
        <span style={{ fontSize: 12, color: "#94a3b8" }}>
          장소 선택 &gt; {province || "도/광역시"} &gt; {city || "시/군/구"} &gt; 동/읍/면
        </span>

        {/* Current path */}
        {pathLabel && (
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: "#475569" }}>
              현재 선택 경로
            </span>
            <div
              style={{
                borderRadius: 10,
                background: "#eef2ff",
                padding: "10px 14px",
                display: "flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              <MapPin size={14} color="#4f46e5" />
              <span style={{ fontSize: 13, fontWeight: 500, color: "#4f46e5" }}>
                {pathLabel}
              </span>
            </div>
          </div>
        )}

        {/* Search */}
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: "#475569" }}>
            검색
          </span>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="동/읍/면을 입력하세요"
            style={{
              height: 42,
              borderRadius: 10,
              background: "#f8fafc",
              border: "1px solid #e2e8f0",
              padding: "0 14px",
              fontSize: 14,
              color: "#1e293b",
              outline: "none",
            }}
          />
        </div>

        {/* 3-column grid */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr 1fr",
            gap: 8,
          }}
        >
          {filtered.map((d) => {
            const sel = selected === d;
            return (
              <div
                key={d}
                onClick={() => setSelected(d)}
                style={{
                  height: 44,
                  borderRadius: 12,
                  background: sel ? "#4f46e5" : "#f1f5f9",
                  border: sel ? "none" : "1px solid #e2e8f0",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  cursor: "pointer",
                  padding: "0 4px",
                }}
              >
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: sel ? 600 : 400,
                    color: sel ? "#ffffff" : "#374151",
                    textAlign: "center",
                  }}
                >
                  {d}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* CTA */}
      <div style={{ padding: "12px 20px", background: "#f8fafc" }}>
        <button
          onClick={handleConfirm}
          disabled={!selected}
          style={{
            width: "100%",
            height: 46,
            borderRadius: 12,
            background: selected ? "#4f46e5" : "#e2e8f0",
            border: "none",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: selected ? "pointer" : "default",
          }}
        >
          <span
            style={{
              fontSize: 15,
              fontWeight: 600,
              color: selected ? "#ffffff" : "#94a3b8",
            }}
          >
            이 장소로 선택하기
          </span>
        </button>
      </div>
    </div>
  );
}

export default function DistrictPage() {
  return (
    <Suspense fallback={null}>
      <DistrictPageContent />
    </Suspense>
  );
}
