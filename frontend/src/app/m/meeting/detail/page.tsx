"use client";

import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  EllipsisVertical,
  CalendarDays,
  MapPin,
  Users,
  MessageCircle,
  LogOut,
} from "lucide-react";

const members = [
  { name: "김민준 (방장)", role: "모임장", roleColor: "#4f46e5", color: "#4f46e5" },
  { name: "이서연", role: "멤버", roleColor: "#94a3b8", color: "#f59e0b" },
  { name: "박지호", role: "멤버", roleColor: "#94a3b8", color: "#10b981" },
  { name: "최수아", role: "멤버", roleColor: "#94a3b8", color: "#ec4899" },
  { name: "정다은", role: "멤버", roleColor: "#94a3b8", color: "#6366f1" },
];

export default function MeetingDetailPage() {
  const router = useRouter();

  return (
    <div
      style={{
        width: 390,
        height: 844,
        overflow: "clip",
        background: "#ffffff",
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
          background: "#ffffff",
          padding: "0 20px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          borderBottom: "0.5px solid #e2e8f0",
        }}
      >
        <ArrowLeft
          size={24}
          color="#1e293b"
          style={{ cursor: "pointer" }}
          onClick={() => router.back()}
        />
        <span style={{ fontSize: 17, fontWeight: 600, color: "#1e293b" }}>졸업 프로젝트 회의</span>
        <EllipsisVertical size={24} color="#64748b" style={{ cursor: "pointer" }} onClick={() => alert("모임 설정 기능은 준비 중입니다")} />
      </div>

      {/* Content */}
      <div
        style={{
          flex: 1,
          background: "#f8fafc",
          padding: 20,
          gap: 20,
          display: "flex",
          flexDirection: "column",
          overflowY: "auto",
        }}
      >
        {/* Cover Image */}
        <div
          style={{
            width: "100%",
            height: 180,
            borderRadius: 16,
            background: "linear-gradient(135deg, #e0e7ff, #c7d2fe)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            overflow: "hidden",
          }}
        >
          <span style={{ fontSize: 48 }}>📋</span>
        </div>

        {/* Info Card */}
        <div
          style={{
            borderRadius: 16,
            background: "#ffffff",
            border: "1px solid #e2e8f0",
            padding: 20,
            display: "flex",
            flexDirection: "column",
            gap: 16,
          }}
        >
          <span style={{ fontSize: 20, fontWeight: 700, color: "#1e293b" }}>졸업 프로젝트 회의</span>
          <span style={{ fontSize: 14, color: "#64748b" }}>
            다음 주 회의 안건과 장소를 정해봐요
          </span>
          <div style={{ height: 1, background: "#e2e8f0" }} />
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <CalendarDays size={20} color="#4f46e5" />
            <span style={{ fontSize: 14, color: "#1e293b" }}>4월 12일 (토) 오후 3:00</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <MapPin size={20} color="#4f46e5" />
            <span style={{ fontSize: 14, color: "#1e293b" }}>강남역 스터디룸 A</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <Users size={20} color="#4f46e5" />
            <span style={{ fontSize: 14, color: "#1e293b" }}>참여 멤버 5명</span>
          </div>
        </div>

        {/* Members Card */}
        <div
          style={{
            borderRadius: 16,
            background: "#ffffff",
            border: "1px solid #e2e8f0",
            padding: 20,
            display: "flex",
            flexDirection: "column",
            gap: 14,
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <span style={{ fontSize: 16, fontWeight: 600, color: "#1e293b" }}>참여 멤버</span>
            <span style={{ fontSize: 14, fontWeight: 600, color: "#4f46e5" }}>5명</span>
          </div>

          {members.map((m) => (
            <div key={m.name} style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <div
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: "50%",
                  background: m.color,
                  flexShrink: 0,
                }}
              />
              <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                <span style={{ fontSize: 14, fontWeight: m.role === "모임장" ? 600 : 500, color: "#1e293b" }}>
                  {m.name}
                </span>
                <span style={{ fontSize: 12, color: m.roleColor }}>{m.role}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Bottom Bar */}
      <div
        style={{
          background: "#ffffff",
          padding: "16px 20px 34px",
          display: "flex",
          gap: 12,
          borderTop: "0.5px solid #e2e8f0",
        }}
      >
        <button
          onClick={() => router.push("/m/chat/schedule")}
          style={{
            flex: 1,
            height: 48,
            borderRadius: 12,
            border: "none",
            background: "#4f46e5",
            color: "#ffffff",
            fontSize: 15,
            fontWeight: 600,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 8,
            fontFamily: "Pretendard, sans-serif",
          }}
        >
          <MessageCircle size={20} color="#ffffff" />
          채팅방 입장
        </button>
        <button
          onClick={() => { if (confirm("모임에서 나가시겠습니까?")) router.push("/m/explore"); }}
          style={{
            width: 48,
            height: 48,
            borderRadius: 12,
            border: "1px solid #e2e8f0",
            background: "#ffffff",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <LogOut size={20} color="#ef4444" />
        </button>
      </div>
    </div>
  );
}
