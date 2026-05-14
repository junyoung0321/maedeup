"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, MapPin } from "lucide-react";

const CITIES_BY_PROVINCE: Record<string, string[]> = {
  서울특별시: ["강남구", "강동구", "강북구", "강서구", "관악구", "광진구", "구로구", "금천구", "노원구", "도봉구", "동대문구", "동작구", "마포구", "서대문구", "서초구", "성동구", "성북구", "송파구", "양천구", "영등포구", "용산구", "은평구", "종로구", "중구", "중랑구"],
  부산광역시: ["강서구", "금정구", "기장군", "남구", "동구", "동래구", "부산진구", "북구", "사상구", "사하구", "서구", "수영구", "연제구", "영도구", "중구", "해운대구"],
  대구광역시: ["남구", "달서구", "달성군", "동구", "북구", "서구", "수성구", "중구"],
  인천광역시: ["강화군", "계양구", "남동구", "동구", "미추홀구", "부평구", "서구", "연수구", "옹진군", "중구"],
  광주광역시: ["광산구", "남구", "동구", "북구", "서구"],
  경기도: ["수원시", "성남시", "용인시", "안양시", "안산시", "고양시", "부천시", "화성시", "평택시", "시흥시", "파주시", "김포시", "의정부시", "광명시", "하남시", "남양주시", "포천시", "여주시", "이천시", "광주시", "양주시", "동두천시", "구리시", "오산시", "과천시", "의왕시", "군포시", "안성시", "양평군", "연천군", "가평군"],
  충청남도: ["천안시", "공주시", "보령시", "아산시", "서산시", "논산시", "계룡시", "당진시", "금산군", "부여군", "서천군", "청양군", "홍성군", "예산군", "태안군"],
  충청북도: ["청주시", "충주시", "제천시", "보은군", "옥천군", "영동군", "증평군", "진천군", "괴산군", "음성군", "단양군"],
  전라남도: ["목포시", "여수시", "순천시", "나주시", "광양시", "담양군", "곡성군", "구례군", "고흥군", "보성군", "화순군", "장흥군", "강진군", "해남군", "영암군", "무안군", "함평군", "영광군", "장성군", "완도군", "진도군", "신안군"],
  전라북도: ["전주시", "군산시", "익산시", "정읍시", "남원시", "김제시", "완주군", "진안군", "무주군", "장수군", "임실군", "순창군", "고창군", "부안군"],
  경상남도: ["창원시", "진주시", "통영시", "사천시", "김해시", "밀양시", "거제시", "양산시", "의령군", "함안군", "창녕군", "고성군", "남해군", "하동군", "산청군", "함양군", "거창군", "합천군"],
  경상북도: ["포항시", "경주시", "김천시", "안동시", "구미시", "영주시", "영천시", "상주시", "문경시", "경산시", "군위군", "의성군", "청송군", "영양군", "영덕군", "청도군", "고령군", "성주군", "칠곡군", "예천군", "봉화군", "울진군", "울릉군"],
};

const DEFAULT_CITIES = ["수원시", "성남시", "용인시", "안양시", "안산시", "고양시", "부천시", "화성시", "평택시", "시흥시", "파주시", "김포시"];

function CityPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const roomId = searchParams.get("roomId") ?? "";

  const [province, setProvince] = useState("");
  const [selected, setSelected] = useState("");
  const [query, setQuery] = useState("");

  useEffect(() => {
    try {
      const raw = sessionStorage.getItem("locationWizard");
      if (raw) {
        const { province: p } = JSON.parse(raw) as Record<string, string>;
        if (p) setProvince(p);
      }
    } catch {}
  }, []);

  const cities = CITIES_BY_PROVINCE[province] ?? DEFAULT_CITIES;
  const filtered = cities.filter((c) => c.includes(query));

  function handleNext() {
    if (!selected) return;
    try {
      const prev = JSON.parse(sessionStorage.getItem("locationWizard") ?? "{}");
      sessionStorage.setItem(
        "locationWizard",
        JSON.stringify({ ...prev, city: selected, district: "" })
      );
    } catch {}
    router.push(`/m/place/district?roomId=${roomId}`);
  }

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
        <span style={{ fontSize: 17, fontWeight: 600, color: "#ffffff" }}>
          {province || "장소 선택"}
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
          장소 선택 &gt; {province || "도/광역시"} &gt; 시/군/구
        </span>

        {/* Current path */}
        {province && (
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
                {province}
              </span>
            </div>
          </div>
        )}

        {/* Search */}
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: "#475569" }}>
            시/군/구 검색
          </span>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="시/군/구를 입력하세요"
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
          {filtered.map((c) => {
            const sel = selected === c;
            return (
              <div
                key={c}
                onClick={() => setSelected(c)}
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
                  {c}
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

export default function CityPage() {
  return (
    <Suspense fallback={null}>
      <CityPageContent />
    </Suspense>
  );
}
