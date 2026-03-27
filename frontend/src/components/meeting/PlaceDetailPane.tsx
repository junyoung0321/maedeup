"use client";

import { Clock, MapPin, Phone, Star } from "lucide-react";
import { mockPlaces } from "@/mocks/places";

export default function PlaceDetailPane() {
  const place = mockPlaces[0];

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

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-5">
        {/* Name + Tags + Rating + Price */}
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

          {/* Tags */}
          <div className="flex items-center gap-1.5 mt-2">
            {place.tags.map((tag, i) => (
              <span
                key={tag}
                style={{
                  fontSize: 12,
                  fontWeight: 300,
                  color: place.tagColors[i].text,
                  backgroundColor: place.tagColors[i].bg,
                  padding: "2px 8px",
                  borderRadius: 4,
                }}
              >
                {tag}
              </span>
            ))}
          </div>

          {/* Rating + Price */}
          <div className="flex items-center gap-1.5 mt-2">
            <Star className="w-4 h-4 text-yellow-400 fill-yellow-400" />
            <span style={{ fontSize: 15, fontWeight: 300, color: "#1e293b" }}>
              {place.rating}
            </span>
            <span style={{ fontSize: 13, fontWeight: 300, color: "#94a3b8" }}>
              ({place.reviewCount})
            </span>
            <span style={{ fontSize: 13, color: "#94a3b8", margin: "0 2px" }}>
              ·
            </span>
            <span style={{ fontSize: 13, fontWeight: 300, color: "#64748b" }}>
              {place.priceRange}
            </span>
          </div>
        </div>

        {/* Address / Hours / Phone */}
        <div className="flex flex-col gap-2">
          <div className="flex items-start gap-2">
            <MapPin className="w-4 h-4 mt-0.5 shrink-0" style={{ color: "#94a3b8" }} />
            <span style={{ fontSize: 13, fontWeight: 300, color: "#64748b" }}>
              {place.address}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 shrink-0" style={{ color: "#94a3b8" }} />
            <span style={{ fontSize: 13, fontWeight: 300, color: "#64748b" }}>
              영업시간: {place.hours}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Phone className="w-4 h-4 shrink-0" style={{ color: "#94a3b8" }} />
            <span style={{ fontSize: 13, fontWeight: 300, color: "#64748b" }}>
              {place.phone}
            </span>
          </div>
        </div>

        {/* Menu */}
        <div>
          <h5
            style={{
              fontSize: 16,
              fontWeight: 300,
              color: "#1e293b",
              margin: "0 0 12px 0",
            }}
          >
            대표 메뉴
          </h5>
          <div className="flex flex-col gap-2">
            {place.menu.map((item) => (
              <div
                key={item.name}
                className="flex items-center justify-between py-2 border-b border-slate-100 last:border-0"
              >
                <span style={{ fontSize: 14, fontWeight: 300, color: "#334155" }}>
                  {item.name}
                </span>
                <span style={{ fontSize: 14, fontWeight: 300, color: "#4f46e5" }}>
                  {item.price.toLocaleString()}원
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Bottom buttons */}
      <div className="p-5 flex gap-3">
        <button
          className="flex-1 rounded-xl transition-colors hover:opacity-90"
          style={{
            fontSize: 14,
            fontWeight: 300,
            color: "#ffffff",
            backgroundColor: "#4f46e5",
            padding: "10px 20px",
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
