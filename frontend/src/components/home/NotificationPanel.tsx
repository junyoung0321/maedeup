"use client";

import { Bell } from "lucide-react";

interface Notification {
  id: number;
  icon: string;
  iconColor: string;
  title: string;
  description: string;
  time: string;
  isNew?: boolean;
}

const notifications: Notification[] = [
  { id: 1, icon: "📋", iconColor: "#4f46e5", title: "팀 프로젝트 일정이 확정되었습니다", description: "3월 23일(월) 오후 3시 ~ 오후 5시", time: "6 시간 전", isNew: true },
  { id: 2, icon: "💬", iconColor: "#f472b6", title: "임지수님이 만든 속소에 변경되었습니다", description: "AI가 근처에 핫는 장소 업데이트 완료", time: "어제" },
  { id: 3, icon: "👤", iconColor: "#fb923c", title: "새 친구 요청이 도착했습니다", description: "이승우님이 친구 요청을 보냈습니다", time: "2일 전", isNew: true },
  { id: 4, icon: "🔔", iconColor: "#ef4444", title: "미팅 알림: 곧 시작 되겠습니다", description: "10분 뒤에 팀 미팅 시작이니 서둘러주세요!", time: "3일 전" },
  { id: 5, icon: "📧", iconColor: "#64748b", title: "이서연님이 미팅노트 하나 파일을 보냈습니다", description: "", time: "그저께" },
];

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function NotificationPanel({ open, onClose }: Props) {
  if (!open) return null;

  return (
    <div
      onClick={onClose}
      style={{ position: "fixed", inset: 0, zIndex: 90 }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          position: "absolute",
          top: 79,
          right: 80,
          width: 380,
          borderRadius: 20,
          background: "#ffffff",
          boxShadow: "0 10px 40px rgba(0,0,0,0.15)",
          border: "1px solid #e2e8f0",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          fontFamily: "Pretendard Variable, Pretendard, sans-serif",
        }}
      >
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "18px 20px 12px" }}>
          <span style={{ fontSize: 18, fontWeight: 600, color: "#111827" }}>알림</span>
          <button style={{ padding: "6px 12px", borderRadius: 8, border: "none", background: "#4f46e5", color: "#ffffff", fontSize: 11, fontWeight: 500, cursor: "pointer", fontFamily: "Pretendard Variable, Pretendard, sans-serif" }}>
            모두 읽음
          </button>
        </div>

        {/* Notification list */}
        <div style={{ display: "flex", flexDirection: "column", maxHeight: 400, overflowY: "auto" }}>
          {notifications.map((notif) => (
            <div
              key={notif.id}
              style={{
                display: "flex",
                gap: 12,
                padding: "14px 20px",
                cursor: "pointer",
                borderBottom: "1px solid #f8fafc",
                background: notif.isNew ? "#fafbff" : "transparent",
              }}
            >
              {/* Icon dot */}
              <div style={{ width: 8, height: 8, borderRadius: "50%", background: notif.isNew ? "#4f46e5" : "#d1d5db", marginTop: 6, flexShrink: 0 }} />
              <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 3 }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: "#111827", lineHeight: 1.4 }}>
                  {notif.title}
                </span>
                {notif.description && (
                  <span style={{ fontSize: 12, fontWeight: 400, color: "#94a3b8", lineHeight: 1.3 }}>
                    {notif.description}
                  </span>
                )}
                <span style={{ fontSize: 11, fontWeight: 400, color: "#cbd5e1", marginTop: 2 }}>
                  {notif.time}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
