"use client";

import { useState } from "react";
import { X, Clock, MapPin, UtensilsCrossed, Car } from "lucide-react";

type Category = "선호 시간" | "선호 장소" | "음식 취향" | "이동 수단";

const categories: { key: Category; label: string; icon: typeof Clock; color: string; bgColor: string; borderColor: string }[] = [
  { key: "선호 시간", label: "선호 시간", icon: Clock, color: "#4f46e5", bgColor: "#eef2ff", borderColor: "#4f46e5" },
  { key: "선호 장소", label: "선호 장소", icon: MapPin, color: "#16a34a", bgColor: "#f0fdf4", borderColor: "#22c55e" },
  { key: "음식 취향", label: "음식 취향", icon: UtensilsCrossed, color: "#eab308", bgColor: "#fefce8", borderColor: "#eab308" },
  { key: "이동 수단", label: "이동 수단", icon: Car, color: "#64748b", bgColor: "#f8fafc", borderColor: "#94a3b8" },
];

const days = ["월", "화", "수", "목", "금", "토", "일"];

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function PersonalDataModal({ open, onClose }: Props) {
  const [activeCategory, setActiveCategory] = useState<Category>("선호 시간");
  const [selectedDays, setSelectedDays] = useState<Set<string>>(new Set(["월", "수", "금"]));
  const [startTime, setStartTime] = useState("오후 2:00");
  const [endTime, setEndTime] = useState("오후 6:00");
  const [memo, setMemo] = useState("");

  if (!open) return null;

  const toggleDay = (day: string) => {
    setSelectedDays((prev) => {
      const next = new Set(prev);
      if (next.has(day)) next.delete(day);
      else next.add(day);
      return next;
    });
  };

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 100,
        background: "rgba(0,0,0,0.35)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 520,
          borderRadius: 24,
          background: "#ffffff",
          boxShadow: "0 20px 60px rgba(0,0,0,0.2)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          fontFamily: "Pretendard Variable, Pretendard, sans-serif",
        }}
      >
        {/* Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "20px 24px",
            borderBottom: "1px solid #f1f5f9",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <Clock style={{ width: 22, height: 22, color: "#4f46e5" }} />
            <span style={{ fontSize: 20, fontWeight: 600, color: "#111827" }}>개인 데이터 추가</span>
          </div>
          <button
            onClick={onClose}
            style={{
              width: 32,
              height: 32,
              borderRadius: "50%",
              border: "none",
              background: "#f1f5f9",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: "pointer",
            }}
          >
            <X style={{ width: 16, height: 16, color: "#64748b" }} />
          </button>
        </div>

        {/* Content */}
        <div style={{ padding: "24px", display: "flex", flexDirection: "column", gap: 24 }}>
          {/* 카테고리 선택 */}
          <div>
            <span style={{ fontSize: 14, fontWeight: 700, color: "#111827", marginBottom: 12, display: "block" }}>
              카테고리 선택
            </span>
            <div style={{ display: "flex", gap: 10 }}>
              {categories.map((cat) => {
                const isActive = activeCategory === cat.key;
                const Icon = cat.icon;
                return (
                  <button
                    key={cat.key}
                    onClick={() => setActiveCategory(cat.key)}
                    style={{
                      flex: 1,
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: 6,
                      padding: "12px 0",
                      borderRadius: 14,
                      border: isActive ? `2px solid ${cat.borderColor}` : "1px solid #e2e8f0",
                      background: isActive ? cat.bgColor : "#ffffff",
                      cursor: "pointer",
                      fontFamily: "Pretendard Variable, Pretendard, sans-serif",
                    }}
                  >
                    <Icon style={{ width: 24, height: 24, color: cat.color }} />
                    <span style={{ fontSize: 13, fontWeight: 500, color: cat.color }}>
                      {cat.label}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* 선호 시간 추가 */}
          <div>
            <span style={{ fontSize: 14, fontWeight: 700, color: "#111827", marginBottom: 12, display: "block" }}>
              선호 시간 추가
            </span>

            {/* 요일 선택 */}
            <div style={{ marginBottom: 16 }}>
              <span style={{ fontSize: 12, fontWeight: 500, color: "#94a3b8", marginBottom: 8, display: "block" }}>
                요일 선택
              </span>
              <div style={{ display: "flex", gap: 8 }}>
                {days.map((day) => {
                  const isSelected = selectedDays.has(day);
                  return (
                    <button
                      key={day}
                      onClick={() => toggleDay(day)}
                      style={{
                        flex: 1,
                        height: 36,
                        borderRadius: 20,
                        border: "none",
                        background: isSelected ? "#4f46e5" : "#f1f5f9",
                        color: isSelected ? "#ffffff" : "#64748b",
                        fontSize: 13,
                        fontWeight: 500,
                        cursor: "pointer",
                        fontFamily: "Pretendard Variable, Pretendard, sans-serif",
                      }}
                    >
                      {day}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* 시간대 선택 */}
            <div style={{ marginBottom: 16 }}>
              <span style={{ fontSize: 12, fontWeight: 500, color: "#94a3b8", marginBottom: 8, display: "block" }}>
                시간대 선택
              </span>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <input
                  value={startTime}
                  onChange={(e) => setStartTime(e.target.value)}
                  style={{
                    flex: 1,
                    padding: "10px 14px",
                    borderRadius: 12,
                    border: "1px solid #e2e8f0",
                    outline: "none",
                    fontSize: 14,
                    fontWeight: 500,
                    color: "#111827",
                    fontFamily: "Pretendard Variable, Pretendard, sans-serif",
                  }}
                />
                <span style={{ fontSize: 14, color: "#94a3b8" }}>~</span>
                <input
                  value={endTime}
                  onChange={(e) => setEndTime(e.target.value)}
                  style={{
                    flex: 1,
                    padding: "10px 14px",
                    borderRadius: 12,
                    border: "1px solid #e2e8f0",
                    outline: "none",
                    fontSize: 14,
                    fontWeight: 500,
                    color: "#111827",
                    fontFamily: "Pretendard Variable, Pretendard, sans-serif",
                  }}
                />
              </div>
            </div>

            {/* 메모 */}
            <div>
              <span style={{ fontSize: 12, fontWeight: 500, color: "#94a3b8", marginBottom: 8, display: "block" }}>
                메모 (선택)
              </span>
              <input
                value={memo}
                onChange={(e) => setMemo(e.target.value)}
                placeholder="예: 점심시간 이후 선호"
                style={{
                  width: "100%",
                  padding: "10px 14px",
                  borderRadius: 12,
                  border: "1px solid #e2e8f0",
                  outline: "none",
                  fontSize: 14,
                  color: "#374151",
                  fontFamily: "Pretendard Variable, Pretendard, sans-serif",
                  boxSizing: "border-box",
                }}
              />
            </div>
          </div>
        </div>

        {/* Footer buttons */}
        <div
          style={{
            display: "flex",
            justifyContent: "flex-end",
            gap: 12,
            padding: "16px 24px 24px",
            borderTop: "1px solid #f1f5f9",
          }}
        >
          <button
            onClick={onClose}
            style={{
              padding: "10px 20px",
              borderRadius: 12,
              border: "1px solid #e2e8f0",
              background: "#ffffff",
              color: "#64748b",
              fontSize: 14,
              fontWeight: 500,
              cursor: "pointer",
              fontFamily: "Pretendard Variable, Pretendard, sans-serif",
            }}
          >
            취소
          </button>
          <button
            style={{
              padding: "10px 24px",
              borderRadius: 12,
              border: "none",
              background: "#4f46e5",
              color: "#ffffff",
              fontSize: 14,
              fontWeight: 500,
              cursor: "pointer",
              fontFamily: "Pretendard Variable, Pretendard, sans-serif",
            }}
          >
            저장하기
          </button>
        </div>
      </div>
    </div>
  );
}
