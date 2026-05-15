"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Bell,
  User,
  Search,
  Calendar,
  MapPin,
  Users,
  Sparkles,
  MessageCircle,
} from "lucide-react";
import MobileTabBar from "@/components/ui/MobileTabBar";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import type { Room } from "@/types";

const CATEGORY_COLORS: Record<string, string> = {
  스터디: "#818cf8",
  식사: "#fb923c",
  운동: "#22c55e",
  여행: "#f472b6",
  회의: "#60a5fa",
  기타: "#94a3b8",
};

function roomColor(category: string | null): string {
  return CATEGORY_COLORS[category ?? ""] ?? "#818cf8";
}

function formatRelativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 60) return `${minutes}분 전`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}시간 전`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}일 전`;
  return new Date(iso).toLocaleDateString("ko-KR", { month: "numeric", day: "numeric" });
}

export default function ChatListPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [rooms, setRooms] = useState<Room[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      router.push("/m/login");
      return;
    }
    apiFetch<Room[]>("/api/v1/rooms/")
      .then(setRooms)
      .catch(() => setRooms([]))
      .finally(() => setLoading(false));
  }, [authLoading, user, router]);

  return (
    <div
      style={{
        width: "100%",
        height: "844px",
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
        <span style={{ fontSize: 20, fontWeight: 700, color: "#ffffff" }}>
          매듭
        </span>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <Bell
            size={22}
            color="#ffffff"
            style={{ cursor: "pointer" }}
            onClick={() => router.push("/m/notifications")}
          />
          <User
            size={22}
            color="#ffffff"
            style={{ cursor: "pointer" }}
            onClick={() => router.push("/m/profile")}
          />
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
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <Sparkles size={20} color="#ffffff" />
                <span style={{ fontSize: 16, fontWeight: 700, color: "#ffffff" }}>
                  AI 비서
                </span>
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
                { icon: Calendar, label: "일정 조율" },
                { icon: MapPin, label: "장소 추천" },
                { icon: Search, label: "모임 탐색" },
                { icon: Users, label: "모임 관리" },
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
                  <span style={{ fontSize: 11, color: "#ffffff" }}>
                    {chip.label}
                  </span>
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
        <div
          style={{
            padding: "4px 20px",
            display: "flex",
            alignItems: "center",
          }}
        >
          <span style={{ fontSize: 13, fontWeight: 600, color: "#94a3b8" }}>
            모임 채팅
          </span>
        </div>

        {/* Chat List */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
          {loading ? (
            <div
              style={{
                padding: 32,
                display: "flex",
                justifyContent: "center",
              }}
            >
              <span style={{ fontSize: 14, color: "#94a3b8" }}>
                불러오는 중…
              </span>
            </div>
          ) : rooms.length === 0 ? (
            <div
              style={{
                padding: 32,
                display: "flex",
                justifyContent: "center",
              }}
            >
              <span style={{ fontSize: 14, color: "#94a3b8" }}>
                참여 중인 모임이 없습니다
              </span>
            </div>
          ) : (
            rooms.map((room) => (
              <div
                key={room.id}
                onClick={() => router.push(`/m/chat/schedule?roomId=${room.id}`)}
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
                    background: roomColor(room.category),
                    flexShrink: 0,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "#ffffff",
                    fontSize: 18,
                    fontWeight: 700,
                  }}
                >
                  {room.name.charAt(0)}
                </div>
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
                    <span
                      style={{
                        fontSize: 15,
                        fontWeight: 600,
                        color: "#1e293b",
                      }}
                    >
                      {room.name}
                    </span>
                    <span style={{ fontSize: 11, color: "#94a3b8" }}>
                      {formatRelativeTime(room.created_at)}
                    </span>
                  </div>
                  <span
                    style={{
                      fontSize: 13,
                      color: "#64748b",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {room.description ?? room.category ?? "모임"}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Tab Bar */}
      <MobileTabBar active="채팅" />
    </div>
  );
}
