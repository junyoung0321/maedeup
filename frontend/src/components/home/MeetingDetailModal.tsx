"use client";

import { useRouter } from "next/navigation";
import { X, CalendarDays, MapPin, Users } from "lucide-react";

interface Props {
  open: boolean;
  onClose: () => void;
  meeting?: {
    id: string;
    name: string;
    badge: string;
    schedule: string;
    location: string;
    members: string;
  };
}

function getDefaultSchedule(): string {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  const y = d.getFullYear();
  const m = d.getMonth() + 1;
  const day = d.getDate();
  const names = ["일", "월", "화", "수", "목", "금", "토"];
  return `${y}년 ${m}월 ${day}일 (${names[d.getDay()]}) 14:00 ~ 17:00`;
}

const defaultMeeting = {
  id: "1",
  name: "봄 프로젝트 킥오프 미팅",
  badge: "프로젝트 · 스터디",
  schedule: getDefaultSchedule(),
  location: "스타포크퍼블릭스 강남점",
  members: "참여자 3명",
};

interface ProgressItem {
  label: string;
  status: "done" | "progress" | "pending";
  detail?: string;
  percent?: number;
}

const progressItems: ProgressItem[] = [
  { label: "일정 확정 완료", status: "done", percent: 100 },
  { label: "장소 투표 진행중", status: "progress", detail: "1/3 완료" },
  { label: "분류 완료", status: "pending" },
];

export default function MeetingDetailModal({ open, onClose, meeting }: Props) {
  const router = useRouter();
  const m = meeting || defaultMeeting;

  if (!open) return null;

  return (
    <div
      onClick={onClose}
      style={{ position: "fixed", inset: 0, zIndex: 100, background: "rgba(0,0,0,0.35)", display: "flex", alignItems: "center", justifyContent: "center" }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{ width: 500, borderRadius: 24, background: "#ffffff", boxShadow: "0 20px 60px rgba(0,0,0,0.2)", display: "flex", flexDirection: "column", overflow: "hidden", fontFamily: "Pretendard Variable, Pretendard, sans-serif" }}
      >
        {/* Top gradient bar */}
        <div style={{ height: 6, background: "linear-gradient(90deg, #4f46e5, #7c3aed, #a855f7)" }} />

        {/* Header */}
        <div style={{ padding: "24px 28px 16px" }}>
          <h2 style={{ fontSize: 22, fontWeight: 700, color: "#111827", margin: 0 }}>{m.name}</h2>
          <span style={{ fontSize: 13, fontWeight: 400, color: "#94a3b8", marginTop: 4, display: "block" }}>{m.badge}</span>
        </div>

        {/* Info rows */}
        <div style={{ padding: "0 28px", display: "flex", flexDirection: "column", gap: 10 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <CalendarDays style={{ width: 16, height: 16, color: "#4f46e5" }} />
            <span style={{ fontSize: 13, fontWeight: 400, color: "#374151" }}>{m.schedule}</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <MapPin style={{ width: 16, height: 16, color: "#4f46e5" }} />
            <span style={{ fontSize: 13, fontWeight: 400, color: "#374151" }}>{m.location}</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <Users style={{ width: 16, height: 16, color: "#4f46e5" }} />
            <span style={{ fontSize: 13, fontWeight: 400, color: "#374151" }}>{m.members}</span>
          </div>
        </div>

        {/* 진행 현황 */}
        <div style={{ padding: "20px 28px 0" }}>
          <span style={{ fontSize: 14, fontWeight: 600, color: "#111827", marginBottom: 12, display: "block" }}>진행 현황</span>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {progressItems.map((item) => (
              <div
                key={item.label}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  padding: "12px 16px",
                  borderRadius: 12,
                  border: "1px solid #e2e8f0",
                  background: item.status === "done" ? "#f0fdf4" : item.status === "progress" ? "#eef2ff" : "#f8fafc",
                }}
              >
                <div style={{ width: 10, height: 10, borderRadius: "50%", background: item.status === "done" ? "#22c55e" : item.status === "progress" ? "#4f46e5" : "#d1d5db", flexShrink: 0 }} />
                <span style={{ flex: 1, fontSize: 13, fontWeight: 500, color: item.status === "done" ? "#16a34a" : item.status === "progress" ? "#4f46e5" : "#94a3b8" }}>
                  {item.label}
                </span>
                {item.percent && (
                  <span style={{ fontSize: 12, fontWeight: 600, color: "#16a34a" }}>{item.percent}%</span>
                )}
                {item.detail && (
                  <span style={{ fontSize: 12, fontWeight: 500, color: "#4f46e5" }}>{item.detail}</span>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Button */}
        <div style={{ padding: "24px 28px", display: "flex", justifyContent: "center" }}>
          <button
            onClick={() => { onClose(); router.push(`/meeting/${m.id}`); }}
            style={{ padding: "12px 32px", borderRadius: 14, border: "none", background: "linear-gradient(135deg, #4338ca, #4f46e5)", color: "#ffffff", fontSize: 14, fontWeight: 600, cursor: "pointer", fontFamily: "Pretendard Variable, Pretendard, sans-serif" }}
          >
            모임 상세보기
          </button>
        </div>
      </div>
    </div>
  );
}
