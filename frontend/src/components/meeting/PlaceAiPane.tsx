"use client";

import { useState } from "react";
import { Sparkles, Send, UtensilsCrossed, MessageCircle } from "lucide-react";
import { API_BASE_URL } from "@/lib/api";

interface PlaceResult {
  id: string;
  name: string;
  address: string;
  phone: string;
  url: string;
  x: string;
  y: string;
  category: string;
}

interface Props {
  onSelectPlace: (place: PlaceResult) => void;
}

export default function PlaceAiPane({ onSelectPlace }: Props) {
  const [input, setInput] = useState("");
  const [results, setResults] = useState<PlaceResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const handleSend = async () => {
    const query = input.trim();
    if (!query) return;
    const token = localStorage.getItem("auth_token");
    if (!token) return;
    setLoading(true);
    setSearched(true);
    setInput("");
    try {
      const resp = await fetch(`${API_BASE_URL}/api/v1/places/search`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ query }),
      });
      if (resp.ok) {
        const data: PlaceResult[] = await resp.json();
        setResults(data);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        width: 414,
        height: 733,
        borderRadius: 20,
        border: "1px solid #e2e8f0",
        boxShadow: "0 4px 3.5px rgba(0,0,0,0.25)",
        background: "#fff",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        fontFamily: "Pretendard Variable, Pretendard, sans-serif",
      }}
    >
      {/* Header - gradient */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "16px 20px",
          background: "linear-gradient(135deg, #837cff, #6eb3ff)",
          borderBottom: "1px solid #e2e8f0",
        }}
      >
        <Sparkles style={{ width: 20, height: 20, color: "#ffffff" }} />
        <span
          style={{
            fontSize: 26,
            fontWeight: 400,
            color: "#ffffff",
            letterSpacing: 0.75,
          }}
        >
          AI 어시스턴트
        </span>
      </div>

      {/* Content */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "14px 20px",
          display: "flex",
          flexDirection: "column",
          gap: 14,
        }}
      >
        {/* Detect banner */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "8px 14px",
            background: "#eef2ff",
            borderRadius: 18,
          }}
        >
          <MessageCircle style={{ width: 16, height: 16, color: "#4f46e5" }} />
          <span style={{ fontSize: 15, fontWeight: 400, color: "#4f46e5", fontFamily: "Inter, sans-serif" }}>
            채팅방에서 장소 관련 대화가 감지되었습니다
          </span>
        </div>

        {/* AI Recommend Card */}
        <div
          style={{
            background: "linear-gradient(135deg, #4f46e5 0%, #7c3aed 50%, #a855f7 100%)",
            borderRadius: 16,
            padding: "16px 20px",
            display: "flex",
            flexDirection: "column",
            gap: 10,
            boxShadow: "0 4px 14px rgba(79, 70, 229, 0.13)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Sparkles style={{ width: 20, height: 20, color: "#ffffff" }} />
            <span style={{ fontSize: 12, fontWeight: 300, color: "#ffffff", fontFamily: "Inter, sans-serif" }}>
              AI 어시스턴트
            </span>
          </div>
          <span style={{ fontSize: 17, fontWeight: 300, color: "#ffffff" }}>
            모임 장소를 추천해드리겠습니다
          </span>
          <span style={{ fontSize: 12, fontWeight: 300, color: "#ffffff", lineHeight: 1.5, whiteSpace: "pre-wrap" }}>
            {"검색어를 입력하면 카카오맵에서\n모임 장소를 찾아드려요."}
          </span>
        </div>

        {/* List header */}
        {(searched || results.length > 0) && (
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <UtensilsCrossed style={{ width: 18, height: 18, color: "#1e293b" }} />
            <span style={{ fontSize: 14, fontWeight: 300, color: "#1e293b" }}>
              검색 결과
            </span>
            {!loading && (
              <span style={{ fontSize: 12, fontWeight: 300, color: "#94a3b8" }}>
                {results.length}곳
              </span>
            )}
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div style={{ textAlign: "center", padding: "20px 0", fontSize: 14, color: "#94a3b8" }}>
            검색 중...
          </div>
        )}

        {/* No results */}
        {searched && !loading && results.length === 0 && (
          <div style={{ textAlign: "center", padding: "20px 0", fontSize: 14, color: "#94a3b8" }}>
            검색 결과가 없습니다
          </div>
        )}

        {/* Place cards */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12, flex: 1 }}>
          {results.map((place) => (
            <div
              key={place.id}
              onClick={() => onSelectPlace(place)}
              style={{
                borderRadius: 14,
                background: "#ffffff",
                boxShadow: "0 2px 7px rgba(0,0,0,0.1)",
                overflow: "hidden",
                display: "flex",
                flexDirection: "column",
                cursor: "pointer",
              }}
            >
              {/* Image placeholder */}
              <div style={{ width: "100%", height: 120, background: "#d9d9de" }} />
              {/* Body */}
              <div style={{ padding: "12px 14px", display: "flex", flexDirection: "column", gap: 8 }}>
                {/* Name + category */}
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <span style={{ fontSize: 15, fontWeight: 300, color: "#0f172a" }}>
                    {place.name}
                  </span>
                  {place.category && (
                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 300,
                        color: "#4f46e5",
                        background: "#eef2ff",
                        borderRadius: 10,
                        padding: "3px 8px",
                        fontFamily: "Inter, sans-serif",
                      }}
                    >
                      {place.category.split(" > ").pop()}
                    </span>
                  )}
                </div>
                {/* Address */}
                <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <span style={{ fontSize: 11, fontWeight: 300, color: "#64748b" }}>{place.address}</span>
                </div>
                {/* Phone */}
                {place.phone && (
                  <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                    <span style={{ fontSize: 11, fontWeight: 300, color: "#94a3b8" }}>{place.phone}</span>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Input - gradient */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: 12,
          background: "linear-gradient(135deg, #837cff, #6eb3ff)",
          borderTop: "1px solid #e2e8f0",
        }}
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
          placeholder="장소를 검색하세요 (예: 강남 카페)"
          style={{
            flex: 1,
            padding: "10px 16px",
            background: "#ffffff",
            borderRadius: 60,
            border: "1.5px solid #a2f4fd",
            outline: "none",
            fontSize: 15,
            color: "#1e293b",
            fontFamily: "Pretendard Variable, Pretendard, sans-serif",
            boxShadow: "0 2px 3.5px rgba(0,0,0,0.15)",
          }}
        />
        <button
          onClick={handleSend}
          style={{
            width: 40,
            height: 40,
            borderRadius: "50%",
            background: "#ffffff",
            border: "none",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
            flexShrink: 0,
            boxShadow: "0 2px 3.5px rgba(0,0,0,0.15)",
          }}
        >
          <Send style={{ width: 16, height: 16, color: "#837cff" }} />
        </button>
      </div>
    </div>
  );
}
