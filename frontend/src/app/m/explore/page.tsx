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
  ChevronRight,
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

interface MeetingListItem {
  id: number;
  room_id: number;
  title: string;
  scheduled_at: string;
  end_at?: string | null;
  location_name?: string | null;
}

function formatUpcomingDate(iso: string) {
  const d = new Date(iso);
  const days = ["일", "월", "화", "수", "목", "금", "토"];
  const month = d.getMonth() + 1;
  const day = d.getDate();
  const dow = days[d.getDay()];
  const h = d.getHours();
  const m = d.getMinutes();
  const period = h < 12 ? "오전" : "오후";
  const hh = h % 12 || 12;
  return `${month}월 ${day}일 (${dow}) ${period} ${hh}:${String(m).padStart(2, "0")}`;
}

function calcDDay(iso: string): string {
  const target = new Date(iso);
  const now = new Date();
  const diffDays = Math.ceil((target.setHours(0, 0, 0, 0) - now.setHours(0, 0, 0, 0)) / 86400000);
  if (diffDays === 0) return "D-DAY";
  if (diffDays > 0) return `D-${diffDays}`;
  return `D+${Math.abs(diffDays)}`;
}

export default function ExplorePage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [rooms, setRooms] = useState<Room[]>([]);
  const [roomsLoading, setRoomsLoading] = useState(false);
  const [upcomingMeeting, setUpcomingMeeting] = useState<MeetingListItem | null>(null);
  const [quickMatchOpen, setQuickMatchOpen] = useState(false);
  const [aiPlaceOpen, setAiPlaceOpen] = useState(false);

  useEffect(() => {
    if (authLoading || !user) return;
    setRoomsLoading(true);
    Promise.all([
      apiFetch<Room[]>("/api/v1/rooms/").catch(() => [] as Room[]),
      apiFetch<MeetingListItem[]>("/api/v1/meetings/").catch(() => [] as MeetingListItem[]),
    ]).then(([roomsData, meetingsData]) => {
      setRooms(roomsData);
      const now = new Date();
      const next = meetingsData
        .filter((m) => new Date(m.scheduled_at) >= now)
        .sort((a, b) => new Date(a.scheduled_at).getTime() - new Date(b.scheduled_at).getTime())[0] ?? null;
      setUpcomingMeeting(next);
    }).finally(() => setRoomsLoading(false));
  }, [authLoading, user]);
  return (
    <div
      style={{
        width: "100%",
        minHeight: "100svh",
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
                빠른 모임 합류
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

        {/* aiEntry — AI 일정 조율 진입 카드 */}
        <div
          onClick={() => router.push("/m/chat")}
          style={{
            borderRadius: 16,
            background: "linear-gradient(-225deg, #4f46e5 0%, #7c3aed 50%, #a855f7 100%)",
            padding: "14px 16px",
            display: "flex",
            alignItems: "center",
            gap: 12,
            cursor: "pointer",
            boxShadow: "0 4px 14px #4f46e520",
          }}
        >
          <div
            style={{
              width: 40,
              height: 40,
              minWidth: 40,
              borderRadius: 12,
              backgroundColor: "rgba(255,255,255,0.15)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Sparkles size={20} color="#ffffff" />
          </div>
          <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 2 }}>
            <span
              style={{
                fontFamily: "Pretendard, sans-serif",
                fontSize: 14,
                fontWeight: 700,
                color: "#ffffff",
              }}
            >
              AI 일정 조율 시작하기
            </span>
            <span
              style={{
                fontFamily: "Pretendard, sans-serif",
                fontSize: 11,
                fontWeight: 400,
                color: "#ffffffcc",
              }}
            >
              채팅방에서 AI가 최적 시간을 찾아드려요
            </span>
          </div>
          <ChevronRight size={20} color="#ffffffcc" />
        </div>

        {/* B) Upcoming Card */}
        <div
          onClick={() => upcomingMeeting && router.push(`/m/chat/schedule?roomId=${upcomingMeeting.room_id}`)}
          style={{
            borderRadius: 16,
            background: "#ffffff",
            border: "1px solid #e5e7eb",
            padding: 16,
            gap: 12,
            display: "flex",
            flexDirection: "column",
            cursor: upcomingMeeting ? "pointer" : "default",
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
          {upcomingMeeting ? (
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <span
                  style={{
                    fontFamily: "Pretendard, sans-serif",
                    fontSize: 16,
                    fontWeight: 700,
                    color: "#1e293b",
                  }}
                >
                  {upcomingMeeting.title}
                </span>
                <span
                  style={{
                    fontFamily: "Pretendard, sans-serif",
                    fontSize: 12,
                    fontWeight: 400,
                    color: "#64748b",
                  }}
                >
                  {formatUpcomingDate(upcomingMeeting.scheduled_at)}
                </span>
                {upcomingMeeting.location_name && (
                  <span
                    style={{
                      fontFamily: "Pretendard, sans-serif",
                      fontSize: 11,
                      fontWeight: 400,
                      color: "#94a3b8",
                    }}
                  >
                    {upcomingMeeting.location_name}
                  </span>
                )}
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
                  {calcDDay(upcomingMeeting.scheduled_at)}
                </span>
              </div>
            </div>
          ) : (
            <span
              style={{
                fontFamily: "Pretendard, sans-serif",
                fontSize: 13,
                color: "#94a3b8",
              }}
            >
              예정된 모임이 없습니다
            </span>
          )}
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
