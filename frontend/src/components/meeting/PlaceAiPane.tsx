"use client";

import { useState } from "react";
import { Sparkles, Send, Star, UtensilsCrossed, CreditCard, MessageCircle } from "lucide-react";

interface Restaurant {
  name: string;
  tag: string;
  tagColor: string;
  tagBg: string;
  rating: string;
  address: string;
  price: string;
}

const restaurants: Restaurant[] = [
  { name: "을지로 골목식당", tag: "한식", tagColor: "#4f46e5", tagBg: "#eef2ff", rating: "4.5", address: "강남구 역삼동", price: "1~2만원대" },
  { name: "모모스커피", tag: "카페", tagColor: "#d97706", tagBg: "#fef3c7", rating: "4.3", address: "강남구 논현동", price: "1만원대" },
  { name: "오스테리아 오르조", tag: "이탈리안", tagColor: "#db2777", tagBg: "#fce7f3", rating: "4.7", address: "강남구 신사동", price: "3~4만원대" },
  { name: "명동교자", tag: "한식", tagColor: "#4f46e5", tagBg: "#eef2ff", rating: "4.2", address: "중구 명동", price: "1만원대" },
];

export default function PlaceAiPane() {
  const [input, setInput] = useState("");

  const handleSend = () => {
    if (!input.trim()) return;
    console.log("agent:", input.trim());
    setInput("");
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
            {"채팅 내용을 분석하여 근처 맛집과\n모임 장소를 찾아보았어요."}
          </span>
        </div>

        {/* List header */}
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <UtensilsCrossed style={{ width: 18, height: 18, color: "#1e293b" }} />
          <span style={{ fontSize: 14, fontWeight: 300, color: "#1e293b" }}>
            추천 장소
          </span>
          <span style={{ fontSize: 12, fontWeight: 300, color: "#94a3b8" }}>
            {restaurants.length}곳
          </span>
        </div>

        {/* Restaurant cards */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12, flex: 1 }}>
          {restaurants.map((r, i) => (
            <div
              key={i}
              style={{
                borderRadius: 14,
                background: "#ffffff",
                boxShadow: "0 2px 7px rgba(0,0,0,0.1)",
                overflow: "hidden",
                display: "flex",
                flexDirection: "column",
              }}
            >
              {/* Image placeholder */}
              <div style={{ width: "100%", height: 120, background: "#d9d9de" }} />
              {/* Body */}
              <div style={{ padding: "12px 14px", display: "flex", flexDirection: "column", gap: 8 }}>
                {/* Name + tag */}
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <span style={{ fontSize: 15, fontWeight: 300, color: "#0f172a" }}>
                    {r.name}
                  </span>
                  <span
                    style={{
                      fontSize: 10,
                      fontWeight: 300,
                      color: r.tagColor,
                      background: r.tagBg,
                      borderRadius: 10,
                      padding: "3px 8px",
                      fontFamily: "Inter, sans-serif",
                    }}
                  >
                    {r.tag}
                  </span>
                </div>
                {/* Rating + address */}
                <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <Star style={{ width: 14, height: 14, color: "#eab308", fill: "#eab308" }} />
                  <span style={{ fontSize: 12, fontWeight: 300, color: "#0f172a" }}>{r.rating}</span>
                  <span style={{ fontSize: 12, fontWeight: 300, color: "#94a3b8" }}>·</span>
                  <span style={{ fontSize: 11, fontWeight: 300, color: "#64748b" }}>{r.address}</span>
                </div>
                {/* Price */}
                <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <CreditCard style={{ width: 14, height: 14, color: "#64748b" }} />
                  <span style={{ fontSize: 11, fontWeight: 300, color: "#64748b" }}>{r.price}</span>
                </div>
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
          placeholder="AI에게 질문하세요"
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
