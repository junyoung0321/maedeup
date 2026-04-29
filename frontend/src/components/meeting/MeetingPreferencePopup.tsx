"use client";

import { useState } from "react";
import { X } from "lucide-react";
import { apiFetch } from "@/lib/api";

const TIME_OPTIONS = [
  { value: "평일오전", label: "평일 오전" },
  { value: "평일오후", label: "평일 오후" },
  { value: "평일저녁", label: "평일 저녁" },
  { value: "주말오전", label: "주말 오전" },
  { value: "주말오후", label: "주말 오후" },
  { value: "주말저녁", label: "주말 저녁" },
];

const FOOD_OPTIONS = ["한식", "양식", "일식", "중식", "카페", "술집"];

interface MeetingPreferencePopupProps {
  roomId: string;
  onClose: () => void;
  onSubmitted: () => void;
}

export default function MeetingPreferencePopup({
  roomId,
  onClose,
  onSubmitted,
}: MeetingPreferencePopupProps) {
  const [selectedTimes, setSelectedTimes] = useState<Set<string>>(new Set());
  const [location, setLocation] = useState("");
  const [selectedFoods, setSelectedFoods] = useState<Set<string>>(new Set());
  const [dislikedFoods, setDislikedFoods] = useState<Set<string>>(new Set());
  const [note, setNote] = useState("");
  const [showOptional, setShowOptional] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toggleTime = (value: string) => {
    setSelectedTimes((prev) => {
      const next = new Set(prev);
      if (next.has(value)) next.delete(value);
      else next.add(value);
      return next;
    });
  };

  const toggleFood = (value: string) => {
    setSelectedFoods((prev) => {
      const next = new Set(prev);
      if (next.has(value)) next.delete(value);
      else next.add(value);
      return next;
    });
  };

  const toggleDisliked = (value: string) => {
    setDislikedFoods((prev) => {
      const next = new Set(prev);
      if (next.has(value)) next.delete(value);
      else next.add(value);
      return next;
    });
  };

  const handleSubmit = async () => {
    if (selectedTimes.size === 0) {
      setError("가능한 시간대를 1개 이상 선택해주세요");
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      await apiFetch(`/api/v1/rooms/${roomId}/preferences`, {
        method: "POST",
        body: JSON.stringify({
          preferred_times: Array.from(selectedTimes),
          preferred_location: location.trim() || null,
          preferred_foods: Array.from(selectedFoods),
          disliked_foods: Array.from(dislikedFoods),
          note: note.trim() || null,
        }),
      });
      onSubmitted();
    } catch (err) {
      setError(err instanceof Error ? err.message : "저장에 실패했습니다");
    } finally {
      setIsSubmitting(false);
    }
  };

  const pillStyle = (active: boolean) => ({
    padding: "8px 16px",
    borderRadius: 20,
    border: active ? "none" : "1px solid #cbd5e1",
    background: active ? "#4f46e5" : "#ffffff",
    color: active ? "#ffffff" : "#334155",
    fontSize: 14,
    fontWeight: active ? 600 : 400,
    cursor: "pointer",
    fontFamily: "Pretendard Variable, Pretendard, sans-serif",
    minHeight: 44,
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
  });

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 1000,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "rgba(0,0,0,0.5)",
      }}
    >
      <div
        style={{
          width: 400,
          maxHeight: "85vh",
          overflowY: "auto",
          borderRadius: 20,
          background: "#ffffff",
          boxShadow: "0 20px 60px rgba(0,0,0,0.3)",
          fontFamily: "Pretendard Variable, Pretendard, sans-serif",
        }}
      >
        {/* Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "20px 24px 0",
          }}
        >
          <span style={{ fontSize: 20, fontWeight: 700, color: "#1e293b" }}>
            이번 모임 선호 정보
          </span>
          <button
            onClick={onClose}
            style={{
              width: 36,
              height: 36,
              borderRadius: 10,
              border: "none",
              background: "#f1f5f9",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <X style={{ width: 18, height: 18, color: "#64748b" }} />
          </button>
        </div>
        <p style={{ padding: "8px 24px 0", fontSize: 14, color: "#64748b", margin: 0 }}>
          모두 입력하면 AI가 최적안을 추천해드려요
        </p>

        <div style={{ padding: "16px 24px 24px", display: "flex", flexDirection: "column", gap: 20 }}>
          {/* 시간대 (필수) */}
          <div>
            <label style={{ fontSize: 14, fontWeight: 600, color: "#1e293b", marginBottom: 8, display: "block" }}>
              가능한 시간대 *
            </label>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {TIME_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => toggleTime(opt.value)}
                  style={pillStyle(selectedTimes.has(opt.value)) as React.CSSProperties}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* 장소 (필수) */}
          <div>
            <label style={{ fontSize: 14, fontWeight: 600, color: "#1e293b", marginBottom: 8, display: "block" }}>
              선호 장소
            </label>
            <input
              type="text"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="예: 건대입구역 근처"
              style={{
                width: "100%",
                padding: "10px 14px",
                borderRadius: 12,
                border: "1px solid #e2e8f0",
                fontSize: 14,
                fontFamily: "Pretendard Variable, Pretendard, sans-serif",
                outline: "none",
                boxSizing: "border-box",
                minHeight: 44,
              }}
            />
          </div>

          {/* 선택 필드 토글 */}
          {!showOptional && (
            <button
              onClick={() => setShowOptional(true)}
              style={{
                padding: "10px 0",
                border: "none",
                background: "transparent",
                color: "#4f46e5",
                fontSize: 14,
                fontWeight: 500,
                cursor: "pointer",
                textAlign: "left",
                fontFamily: "Pretendard Variable, Pretendard, sans-serif",
              }}
            >
              + 음식 선호/메모 더 입력하기
            </button>
          )}

          {showOptional && (
            <>
              {/* 선호 음식 */}
              <div>
                <label style={{ fontSize: 14, fontWeight: 600, color: "#1e293b", marginBottom: 8, display: "block" }}>
                  선호 음식
                </label>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                  {FOOD_OPTIONS.map((food) => (
                    <button
                      key={food}
                      onClick={() => toggleFood(food)}
                      style={pillStyle(selectedFoods.has(food)) as React.CSSProperties}
                    >
                      {food}
                    </button>
                  ))}
                </div>
              </div>

              {/* 비선호 음식 */}
              <div>
                <label style={{ fontSize: 14, fontWeight: 600, color: "#1e293b", marginBottom: 8, display: "block" }}>
                  비선호 음식
                </label>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                  {FOOD_OPTIONS.map((food) => (
                    <button
                      key={food}
                      onClick={() => toggleDisliked(food)}
                      style={{
                        ...pillStyle(dislikedFoods.has(food)),
                        background: dislikedFoods.has(food) ? "#ef4444" : "#ffffff",
                      } as React.CSSProperties}
                    >
                      {food}
                    </button>
                  ))}
                </div>
              </div>

              {/* 메모 */}
              <div>
                <label style={{ fontSize: 14, fontWeight: 600, color: "#1e293b", marginBottom: 8, display: "block" }}>
                  한 줄 메모
                </label>
                <input
                  type="text"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="예: 8시 이후만 가능해요"
                  style={{
                    width: "100%",
                    padding: "10px 14px",
                    borderRadius: 12,
                    border: "1px solid #e2e8f0",
                    fontSize: 14,
                    fontFamily: "Pretendard Variable, Pretendard, sans-serif",
                    outline: "none",
                    boxSizing: "border-box",
                    minHeight: 44,
                  }}
                />
              </div>
            </>
          )}

          {/* Error */}
          {error && (
            <p style={{ fontSize: 13, color: "#dc2626", margin: 0 }}>{error}</p>
          )}

          {/* Submit */}
          <button
            onClick={handleSubmit}
            disabled={isSubmitting}
            style={{
              width: "100%",
              padding: "14px 0",
              borderRadius: 14,
              border: "none",
              background: isSubmitting ? "#cbd5e1" : "#4f46e5",
              color: "#ffffff",
              fontSize: 16,
              fontWeight: 700,
              cursor: isSubmitting ? "not-allowed" : "pointer",
              fontFamily: "Pretendard Variable, Pretendard, sans-serif",
              minHeight: 48,
            }}
          >
            {isSubmitting ? "제출 중..." : "제출하기"}
          </button>

          {/* Skip */}
          <button
            onClick={onClose}
            style={{
              width: "100%",
              padding: "10px 0",
              border: "none",
              background: "transparent",
              color: "#94a3b8",
              fontSize: 14,
              cursor: "pointer",
              fontFamily: "Pretendard Variable, Pretendard, sans-serif",
            }}
          >
            나중에 입력할게요
          </button>
        </div>
      </div>
    </div>
  );
}
