"use client";

import { useRouter } from "next/navigation";
import { Bell, User, Search, Calendar, MapPin, Users, Sparkles, MessageCircle } from "lucide-react";
import MobileTabBar from "@/components/ui/MobileTabBar";

const chatRooms = [
  {
    name: "졸업 프로젝트 회의",
    message: "김민준: 다음 주 회의 언제 할까요?",
    time: "오후 2:30",
    unread: 3,
    color: "#818cf8",
  },
  {
    name: "주말 등산 모임",
    message: "AI: 등산 장소를 추천해드릴게요",
    time: "어제",
    unread: 1,
    color: "#22c55e",
  },
  {
    name: "영어 회화 모임",
    message: "박지호: 이번 주 주제는 여행이에요",
    time: "어제",
    unread: 0,
    color: "#f59e0b",
  },
  {
    name: "기획 스터디",
    message: "이서연: 자료 공유합니다",
    time: "월요일",
    unread: 0,
    color: "#f472b6",
  },
  {
    name: "런닝 크루",
    message: "최수아: 다음 런닝 코스 정했어요!",
    time: "3/28",
    unread: 0,
    color: "#60a5fa",
  },
];

export default function ChatListPage() {
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
          background: "#4f46e5",
          padding: "0 20px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <span style={{ fontSize: 20, fontWeight: 700, color: "#ffffff" }}>매듭</span>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <Bell size={22} color="#ffffff" style={{ cursor: "pointer" }} onClick={() => router.push("/m/notifications")} />
          <User size={22} color="#ffffff" style={{ cursor: "pointer" }} onClick={() => router.push("/m/profile")} />
        </div>
      </div>

      {/* Content */}
      <div
        style={{
          flex: 1,
          background: "#f8fafc",
          padding: "16px 0",
          display: "flex",
          flexDirection: "column",
          overflowY: "auto",
        }}
      >
        {/* Search */}
        <div style={{ padding: "0 20px 12px" }}>
          <div
            style={{
              height: 40,
              borderRadius: 20,
              background: "#ffffff",
              border: "1px solid #e2e8f0",
              padding: "0 14px",
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            <Search size={16} color="#94a3b8" />
            <span style={{ fontSize: 13, color: "#94a3b8" }}>채팅방 검색</span>
          </div>
        </div>

        {/* AI Assistant Card */}
        <div style={{ padding: "0 16px 8px" }}>
          <div
            onClick={() => router.push("/m/chat/ai")}
            style={{
              borderRadius: 16,
              background: "linear-gradient(135deg, #4f46e5, #7c3aed)",
              padding: 18,
              display: "flex",
              flexDirection: "column",
              gap: 14,
              cursor: "pointer",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <Sparkles size={20} color="#ffffff" />
                <span style={{ fontSize: 16, fontWeight: 700, color: "#ffffff" }}>AI 비서</span>
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 600,
                    color: "#ffffff",
                    background: "rgba(255,255,255,0.2)",
                    borderRadius: 10,
                    padding: "2px 8px",
                  }}
                >
                  Beta
                </span>
              </div>
            </div>
            <span style={{ fontSize: 14, color: "rgba(255,255,255,0.8)" }}>
              일정 조율, 장소 추천 등 모임의 모든 것을 도와드려요
            </span>
            <div style={{ display: "flex", gap: 8 }}>
              {[
                { icon: Calendar, label: "일정 관리" },
                { icon: MapPin, label: "장소 추천" },
                { icon: Users, label: "모임 매칭" },
              ].map((chip) => (
                <div
                  key={chip.label}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 4,
                    padding: "4px 10px",
                    borderRadius: 20,
                    background: "rgba(255,255,255,0.15)",
                  }}
                >
                  <chip.icon size={12} color="#ffffff" />
                  <span style={{ fontSize: 11, color: "#ffffff" }}>{chip.label}</span>
                </div>
              ))}
            </div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 8,
                padding: "12px 0",
                borderRadius: 12,
                background: "#ffffff",
              }}
            >
              <MessageCircle size={16} color="#4f46e5" />
              <span style={{ fontSize: 14, fontWeight: 600, color: "#4f46e5" }}>
                AI 비서와 대화하기
              </span>
            </div>
          </div>
        </div>

        {/* Section Label */}
        <div style={{ padding: "4px 20px", display: "flex", alignItems: "center" }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: "#94a3b8" }}>모임 채팅</span>
        </div>

        {/* Chat List */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
          {chatRooms.map((room) => (
            <div
              key={room.name}
              onClick={() => router.push("/m/chat/schedule")}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                padding: "14px 20px",
                borderBottom: "1px solid #f1f5f9",
                cursor: "pointer",
              }}
            >
              <div
                style={{
                  width: 48,
                  height: 48,
                  borderRadius: "50%",
                  background: room.color,
                  flexShrink: 0,
                }}
              />
              <div
                style={{
                  flex: 1,
                  display: "flex",
                  flexDirection: "column",
                  gap: 4,
                  minWidth: 0,
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <span style={{ fontSize: 15, fontWeight: 600, color: "#1e293b" }}>
                    {room.name}
                  </span>
                  <span style={{ fontSize: 11, color: "#94a3b8" }}>{room.time}</span>
                </div>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    gap: 8,
                  }}
                >
                  <span
                    style={{
                      fontSize: 13,
                      color: "#64748b",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                      flex: 1,
                    }}
                  >
                    {room.message}
                  </span>
                  {room.unread > 0 && (
                    <div
                      style={{
                        width: 20,
                        height: 20,
                        borderRadius: 10,
                        background: "#4f46e5",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        flexShrink: 0,
                      }}
                    >
                      <span
                        style={{ fontSize: 10, fontWeight: 600, color: "#ffffff" }}
                      >
                        {room.unread}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Tab Bar */}
      <MobileTabBar active="채팅" />
    </div>
  );
}
