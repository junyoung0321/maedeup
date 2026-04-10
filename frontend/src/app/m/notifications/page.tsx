"use client";

import { useRouter } from "next/navigation";
import { ArrowLeft, Settings, Calendar, Users, Sparkles, Vote } from "lucide-react";

const notifications = [
  {
    section: "오늘",
    items: [
      {
        icon: Calendar,
        iconBg: "#4f46e5",
        title: "팀 프로젝트 회의 일정이 확정되었습니다",
        sub: "4월 10일 (금) 오후 3:00 · 강남역 스터디룸",
        time: "30분 전",
        unread: true,
      },
      {
        icon: Users,
        iconBg: "#22c55e",
        title: "이서연님이 주말 등산 모임에 참여했습니다",
        sub: null,
        time: "2시간 전",
        unread: true,
      },
      {
        icon: Sparkles,
        iconBg: "#7c3aed",
        title: "AI가 졸업 프로젝트 회의 장소를 추천했습니다",
        sub: "을지로 골목식당 외 2곳",
        time: "5시간 전",
        unread: false,
      },
    ],
  },
  {
    section: "이번 주",
    items: [
      {
        icon: Vote,
        iconBg: "#f59e0b",
        title: "영어 회화 모임 일정 투표가 시작되었습니다",
        sub: null,
        time: "어제",
        unread: false,
      },
    ],
  },
];

export default function NotificationsPage() {
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
          padding: "0 16px",
          display: "flex",
          alignItems: "center",
          borderBottom: "1px solid #e2e8f0",
        }}
      >
        <ArrowLeft
          size={24}
          color="#1e293b"
          style={{ cursor: "pointer" }}
          onClick={() => router.back()}
        />
        <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center" }}>
          <span style={{ fontSize: 17, fontWeight: 600, color: "#1e293b" }}>알림</span>
        </div>
        <Settings size={22} color="#64748b" style={{ cursor: "pointer" }} onClick={() => alert("알림 설정 기능은 준비 중입니다")} />
      </div>

      {/* Content */}
      <div
        style={{
          flex: 1,
          background: "#f8fafc",
          display: "flex",
          flexDirection: "column",
          overflowY: "auto",
        }}
      >
        {notifications.map((section) => (
          <div key={section.section}>
            {/* Section Label */}
            <div style={{ padding: "12px 20px" }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: "#94a3b8" }}>
                {section.section}
              </span>
            </div>

            {/* Items */}
            {section.items.map((item, i) => {
              const Icon = item.icon;
              return (
                <div
                  key={i}
                  onClick={() => router.push("/m/meeting/detail")}
                  style={{
                    display: "flex",
                    gap: 12,
                    padding: "14px 20px",
                    background: item.unread ? "#eef2ff" : "#ffffff",
                    borderBottom: "1px solid #f1f5f9",
                    cursor: "pointer",
                  }}
                >
                  <div
                    style={{
                      width: 36,
                      height: 36,
                      borderRadius: 18,
                      background: item.iconBg,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                    }}
                  >
                    <Icon size={18} color="#ffffff" />
                  </div>
                  <div
                    style={{
                      flex: 1,
                      display: "flex",
                      flexDirection: "column",
                      gap: 4,
                    }}
                  >
                    <span
                      style={{
                        fontSize: 14,
                        fontWeight: item.unread ? 600 : 500,
                        color: "#1e293b",
                        lineHeight: 1.4,
                      }}
                    >
                      {item.title}
                    </span>
                    {item.sub && (
                      <span style={{ fontSize: 12, color: "#64748b" }}>{item.sub}</span>
                    )}
                    <span style={{ fontSize: 11, color: "#94a3b8" }}>{item.time}</span>
                  </div>
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
