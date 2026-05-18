"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, MapPin } from "lucide-react";

const PROVINCES = [
  "서울특별시",
  "부산광역시",
  "대구광역시",
  "인천광역시",
  "광주광역시",
  "경기도",
  "충청남도",
  "충청북도",
  "전라남도",
  "전라북도",
  "경상남도",
  "경상북도",
];

function RegionPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const roomId = searchParams.get("roomId") ?? "";
  const from = searchParams.get("from") ?? "";

  const [selected, setSelected] = useState("");
  const [query, setQuery] = useState("");

  const filtered = PROVINCES.filter((p) => p.includes(query));

  function handleNext() {
    if (!selected) return;
    try {
      const prev = JSON.parse(sessionStorage.getItem("locationWizard") ?? "{}");
      sessionStorage.setItem(
        "locationWizard",
        JSON.stringify({ ...prev, province: selected, city: "", district: "" })
      );
    } catch {}
    const fromParam = from ? `&from=${from}` : "";
    router.push(`/m/place/city?roomId=${roomId}${fromParam}`);
  }

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
          장소 선택
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
          장소 선택 &gt; 도/광역시
        </span>

        {/* Desc row */}
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <MapPin size={18} color="#4f46e5" />
          <span style={{ fontSize: 14, fontWeight: 600, color: "#1e293b" }}>
            모임 장소의 지역을 선택해주세요
          </span>
        </div>

        {/* Search */}
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: "#475569" }}>
            지역 검색
          </span>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="지역명을 입력하세요"
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

        {/* 2-column grid */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 8,
          }}
        >
          {filtered.map((p) => {
            const sel = selected === p;
            return (
              <div
                key={p}
                onClick={() => setSelected(p)}
                style={{
                  height: 44,
                  borderRadius: 12,
                  background: sel ? "#4f46e5" : "#f1f5f9",
                  border: sel ? "none" : "1px solid #e2e8f0",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  cursor: "pointer",
                }}
              >
                <span
                  style={{
                    fontSize: 13,
                    fontWeight: sel ? 600 : 400,
                    color: sel ? "#ffffff" : "#374151",
                  }}
                >
                  {p}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* CTA */}
      <div style={{ padding: "12px 20px", background: "#f8fafc" }}>
        <button
          onClick={handleNext}
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
            다음 단계로
          </span>
        </button>
      </div>
    </div>
  );
}

export default function RegionPage() {
  return (
    <Suspense fallback={null}>
      <RegionPageContent />
    </Suspense>
  );
}
