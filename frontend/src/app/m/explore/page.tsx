"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Bell,
  User,
  Sparkles,
  Clock3,
  MapPin,
  Plus,
} from "lucide-react";
import MobileTabBar from "@/components/ui/MobileTabBar";
import QuickMatchPopup from "@/components/home/QuickMatchPopup";
import AiPlacePopup from "@/components/home/AiPlacePopup";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import type { Room } from "@/types";

const CATEGORY_COLORS: Record<string, string> = {
  스터디: "#4f46e5",
  식사: "#fb923c",
  운동: "#22c55e",
  여행: "#f472b6",
  회의: "#60a5fa",
  기타: "#94a3b8",
};

export default function ExplorePage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [rooms, setRooms] = useState<Room[]>([]);
  const [roomsLoading, setRoomsLoading] = useState(false);
  const [quickMatchOpen, setQuickMatchOpen] = useState(false);
  const [aiPlaceOpen, setAiPlaceOpen] = useState(false);

  useEffect(() => {
    if (authLoading || !user) return;
    setRoomsLoading(true);
    apiFetch<Room[]>("/api/v1/rooms/")
      .then(setRooms)
      .catch(() => setRooms([]))
      .finally(() => setRoomsLoading(false));
  }, [authLoading, user]);
  return (
    <div
      style={{
        width: 390,
        height: 1090,
        overflow: "clip",
        background: "#ffffffff",
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
        <span
          style={{
            fontFamily: "Pretendard, sans-serif",
            fontSize: 20,
            fontWeight: 700,
            color: "#ffffff",
          }}
        >
          매듭
        </span>
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
          padding: 20,
          gap: 20,
          display: "flex",
          flexDirection: "column",
          overflowY: "auto",
        }}
      >
        {/* A) AI Recommend Card */}
        <div
          style={{
            borderRadius: 16,
            background: "#ffffff",
            border: "1px solid #e5e7eb",
            padding: 16,
            gap: 12,
            display: "flex",
            flexDirection: "column",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Sparkles size={18} color="#4f46e5" />
            <span
              style={{
                fontFamily: "Pretendard, sans-serif",
                fontSize: 16,
                fontWeight: 700,
                color: "#1e293b",
              }}
            >
              AI 추천 모임
            </span>
          </div>
          <span
            style={{
              fontFamily: "Pretendard, sans-serif",
              fontSize: 12,
              fontWeight: 400,
              color: "#64748b",
            }}
          >
            관심사와 일정에 맞는 모임을 추천해드려요
          </span>
          <div style={{ display: "flex", gap: 10 }}>
            {/* Card 1 - 빠른 모임 매칭 */}
            <div
              onClick={() => setQuickMatchOpen(true)}
              style={{
                flex: 1,
                borderRadius: 12,
                background: "linear-gradient(-220deg, #4f46e5, #7c3aed)",
                padding: 12,
                gap: 8,
                display: "flex",
                flexDirection: "column",
                cursor: "pointer",
              }}
            >
              <Clock3 size={20} color="#ffffff" />
              <span
                style={{
                  fontFamily: "Pretendard, sans-serif",
                  fontSize: 13,
                  fontWeight: 600,
                  color: "#ffffff",
                }}
              >
                빠른 모임 매칭
              </span>
              <span
                style={{
                  fontFamily: "Pretendard, sans-serif",
                  fontSize: 11,
                  fontWeight: 400,
                  color: "#ffffffcc",
                }}
              >
                지금 가능한 친구와 바로 만나기
              </span>
            </div>
            {/* Card 2 - AI 장소 추천 */}
            <div
              onClick={() => setAiPlaceOpen(true)}
              style={{
                flex: 1,
                borderRadius: 12,
                background: "linear-gradient(-215deg, #0ea5e9, #22c55e)",
                padding: 12,
                gap: 8,
                display: "flex",
                flexDirection: "column",
                cursor: "pointer",
              }}
            >
              <MapPin size={20} color="#ffffff" />
              <span
                style={{
                  fontFamily: "Pretendard, sans-serif",
                  fontSize: 13,
                  fontWeight: 600,
                  color: "#ffffff",
                }}
              >
                AI 장소 추천
              </span>
              <span
                style={{
                  fontFamily: "Pretendard, sans-serif",
                  fontSize: 11,
                  fontWeight: 400,
                  color: "#ffffffcc",
                }}
              >
                모임에 딱 맞는 장소 찾기
              </span>
            </div>
          </div>
        </div>

        {/* B) Upcoming Card */}
        <div
          onClick={() => router.push("/m/chat/schedule")}
          style={{
            borderRadius: 16,
            background: "#ffffff",
            border: "1px solid #e5e7eb",
            padding: 16,
            gap: 12,
            display: "flex",
            flexDirection: "column",
            cursor: "pointer",
          }}
        >
          <span
            style={{
              fontFamily: "Pretendard, sans-serif",
              fontSize: 14,
              fontWeight: 700,
              color: "#1e293b",
            }}
          >
            가장 임박한 모임
          </span>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 4,
              }}
            >
              <span
                style={{
                  fontFamily: "Pretendard, sans-serif",
                  fontSize: 16,
                  fontWeight: 700,
                  color: "#1e293b",
                }}
              >
                팀 프로젝트 회의
              </span>
              <span
                style={{
                  fontFamily: "Pretendard, sans-serif",
                  fontSize: 12,
                  fontWeight: 400,
                  color: "#64748b",
                }}
              >
                4월 6일 (일) 오후 3:00
              </span>
            </div>
            <div
              style={{
                borderRadius: 20,
                background: "#4f46e5",
                padding: "6px 12px",
              }}
            >
              <span
                style={{
                  fontFamily: "Pretendard, sans-serif",
                  fontSize: 12,
                  fontWeight: 700,
                  color: "#ffffff",
                }}
              >
                D-2
              </span>
            </div>
          </div>
          {/* Avatar row */}
          <div style={{ display: "flex", alignItems: "center" }}>
            {[
              { bg: "#818cf8" },
              { bg: "#f472b6" },
              { bg: "#fb923c" },
            ].map((avatar, i) => (
              <div
                key={i}
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: "50%",
                  background: avatar.bg,
                  border: "2px solid #ffffff",
                  marginLeft: i === 0 ? 0 : -8,
                  zIndex: 3 - i,
                }}
              />
            ))}
            <div
              style={{
                width: 28,
                height: 28,
                borderRadius: "50%",
                background: "#e2e8f0",
                border: "2px solid #ffffff",
                marginLeft: -8,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                zIndex: 0,
              }}
            >
              <span
                style={{
                  fontFamily: "Pretendard, sans-serif",
                  fontSize: 10,
                  fontWeight: 600,
                  color: "#64748b",
                }}
              >
                +2
              </span>
            </div>
          </div>
        </div>

        {/* C) Joined Meetings Section */}
        <div
          style={{
            borderRadius: 16,
            background: "#ffffff",
            border: "1px solid #e5e7eb",
            padding: 16,
            gap: 12,
            display: "flex",
            flexDirection: "column",
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
                fontFamily: "Pretendard, sans-serif",
                fontSize: 14,
                fontWeight: 700,
                color: "#1e293b",
              }}
            >
              참여중인 모임
            </span>
            <span
              onClick={() => router.push("/m/chat")}
              style={{
                fontFamily: "Pretendard, sans-serif",
                fontSize: 12,
                fontWeight: 500,
                color: "#4f46e5",
                cursor: "pointer",
              }}
            >
              전체보기
            </span>
          </div>

          {/* Meeting Items */}
          {roomsLoading ? (
            <span style={{ fontSize: 13, color: "#94a3b8", padding: "8px 0" }}>
              불러오는 중…
            </span>
          ) : rooms.length === 0 ? (
            <span style={{ fontSize: 13, color: "#94a3b8", padding: "8px 0" }}>
              {user ? "참여 중인 모임이 없습니다" : "로그인 후 모임을 확인하세요"}
            </span>
          ) : (
            rooms.slice(0, 3).map((room) => {
              const color = CATEGORY_COLORS[room.category ?? ""] ?? "#94a3b8";
              return (
                <div
                  key={room.id}
                  onClick={() => router.push(`/m/chat/schedule?roomId=${room.id}`)}
                  style={{
                    borderRadius: 12,
                    background: "#f9fafb",
                    border: "1px solid #e5e7eb",
                    padding: 12,
                    gap: 8,
                    display: "flex",
                    flexDirection: "column",
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
                    <span
                      style={{
                        fontFamily: "Pretendard, sans-serif",
                        fontSize: 15,
                        fontWeight: 600,
                        color: "#111827",
                      }}
                    >
                      {room.name}
                    </span>
                    {room.category && (
                      <span
                        style={{
                          fontFamily: "Pretendard, sans-serif",
                          fontSize: 11,
                          fontWeight: 500,
                          color,
                          background: `${color}20`,
                          borderRadius: 999,
                          padding: "3px 8px",
                        }}
                      >
                        {room.category}
                      </span>
                    )}
                  </div>
                  {room.description && (
                    <span
                      style={{
                        fontFamily: "Pretendard, sans-serif",
                        fontSize: 11,
                        fontWeight: 400,
                        color: "#6b7280",
                      }}
                    >
                      {room.description}
                    </span>
                  )}
                </div>
              );
            })
          )}

          {/* Create Button */}
          <button
            onClick={() => router.push("/m/meeting/new")}
            style={{
              borderRadius: 10,
              background: "#4f46e5",
              height: 40,
              width: "100%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 6,
              border: "none",
              cursor: "pointer",
            }}
          >
            <Plus size={16} color="#ffffff" />
            <span
              style={{
                fontFamily: "Pretendard, sans-serif",
                fontSize: 13,
                fontWeight: 600,
                color: "#ffffff",
              }}
            >
              새 모임 만들기
            </span>
          </button>
        </div>
      </div>

      {/* Tab Bar */}
      <MobileTabBar active="홈" variant="pill" />

      {/* Popups */}
      <QuickMatchPopup open={quickMatchOpen} onClose={() => setQuickMatchOpen(false)} />
      <AiPlacePopup open={aiPlaceOpen} onClose={() => setAiPlaceOpen(false)} />
    </div>
  );
}
