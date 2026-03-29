"use client";

import { useRouter } from "next/navigation";
import { X, Sparkles, CalendarDays } from "lucide-react";

interface Props {
  open: boolean;
  onClose: () => void;
}

function getNextWednesday(): string {
  const d = new Date();
  const daysUntilWed = ((3 - d.getDay() + 7) % 7) || 7;
  d.setDate(d.getDate() + daysUntilWed);
  const m = d.getMonth() + 1;
  const day = d.getDate();
  return `${m}월 ${day}일(수) 오전 09 ~ 13:00`;
}

export default function AiRecommendDetailModal({ open, onClose }: Props) {
  const router = useRouter();

  if (!open) return null;

  return (
    <div
      onClick={onClose}
      style={{ position: "fixed", inset: 0, zIndex: 100, background: "rgba(0,0,0,0.35)", display: "flex", alignItems: "center", justifyContent: "center" }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{ width: 480, borderRadius: 24, background: "#ffffff", boxShadow: "0 20px 60px rgba(0,0,0,0.2)", display: "flex", flexDirection: "column", overflow: "hidden", fontFamily: "Pretendard Variable, Pretendard, sans-serif" }}
      >
        {/* Top gradient */}
        <div
          style={{
            padding: "24px 28px",
            background: "linear-gradient(135deg, #4f46e5 0%, #7c3aed 50%, #a855f7 100%)",
            display: "flex",
            flexDirection: "column",
            gap: 6,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Sparkles style={{ width: 18, height: 18, color: "#ffffff" }} />
            <span style={{ fontSize: 12, fontWeight: 500, color: "#e0e7ff" }}>AI 추천</span>
          </div>
          <h2 style={{ fontSize: 22, fontWeight: 700, color: "#ffffff", margin: 0 }}>번개 점심 모임</h2>
          <span style={{ fontSize: 13, fontWeight: 400, color: "#c7d2fe" }}>가까운 친구 3인과 반나절 편하게 만들어보세요</span>
        </div>

        {/* AI 분석 */}
        <div style={{ padding: "20px 28px", background: "#f0fdf4", borderBottom: "1px solid #e2e8f0" }}>
          <span style={{ fontSize: 12, fontWeight: 400, color: "#16a34a", lineHeight: 1.6 }}>
            AI가 분석한 결과, 이번 주 수요일 점심시간대에 3명의 친구가 모두 가능할 확률이 높기 때문에, 간단한 점심 교류 모임을 추천드립니다.
          </span>
        </div>

        {/* 추천 일정 */}
        <div style={{ padding: "20px 28px", display: "flex", flexDirection: "column", gap: 12 }}>
          <span style={{ fontSize: 14, fontWeight: 600, color: "#111827" }}>추천 일정</span>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              padding: "14px 16px",
              borderRadius: 14,
              border: "2px solid #22c55e",
              background: "#f0fdf4",
            }}
          >
            <CalendarDays style={{ width: 20, height: 20, color: "#16a34a" }} />
            <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
              <span style={{ fontSize: 15, fontWeight: 600, color: "#16a34a" }}>{getNextWednesday()}</span>
              <span style={{ fontSize: 12, fontWeight: 400, color: "#64748b" }}>참여 가능 · 김예지 외 2명</span>
            </div>
          </div>
        </div>

        {/* Buttons */}
        <div style={{ display: "flex", justifyContent: "center", gap: 12, padding: "8px 28px 24px" }}>
          <button onClick={onClose} style={{ padding: "12px 28px", borderRadius: 14, border: "1px solid #e2e8f0", background: "#ffffff", color: "#64748b", fontSize: 14, fontWeight: 500, cursor: "pointer", fontFamily: "Pretendard Variable, Pretendard, sans-serif" }}>
            닫기
          </button>
          <button
            onClick={() => { onClose(); router.push("/meeting/new"); }}
            style={{ display: "flex", alignItems: "center", gap: 6, padding: "12px 28px", borderRadius: 14, border: "none", background: "linear-gradient(135deg, #4338ca, #4f46e5)", color: "#ffffff", fontSize: 14, fontWeight: 500, cursor: "pointer", fontFamily: "Pretendard Variable, Pretendard, sans-serif" }}
          >
            <Sparkles style={{ width: 16, height: 16, color: "#ffffff" }} />
            바로 모임 만들기
          </button>
        </div>
      </div>
    </div>
  );
}
