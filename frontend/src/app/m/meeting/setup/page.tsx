"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  Calendar,
  Users,
  MapPin,
  ChevronRight,
  Wallet,
  Sparkles,
  Utensils,
  Fish,
  Beef,
  Soup,
  Cake,
  Ellipsis,
  CalendarCheck,
  Route,
  UsersRound,
  Search,
  UserPlus,
  X as XIcon,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import type { Room } from "@/types";

interface MeetingListItem {
  id: number;
  room_id: number;
  title: string;
  scheduled_at: string;
}

interface MemberInfo {
  user_id: number;
  user_name: string;
}

interface PreferenceStatusResponse {
  total_members: number;
  submitted_count: number;
  all_submitted: boolean;
  preferences: MemberInfo[];
}

const AVATAR_COLORS = ["#818cf8", "#f472b6", "#fb923c", "#34d399", "#60a5fa", "#a78bfa"];
function avatarColor(idx: number) { return AVATAR_COLORS[idx % AVATAR_COLORS.length]; }

const MEETING_TYPES = ["회식", "스터디", "회의", "카페", "기타"];

const FOOD_CATEGORIES = [
  { label: "한식", Icon: Utensils },
  { label: "일식", Icon: Fish },
  { label: "양식", Icon: Beef },
  { label: "중식", Icon: Soup },
  { label: "카페/디저트", Icon: Cake },
  { label: "기타", Icon: Ellipsis },
];

function formatDate(iso: string) {
  const d = new Date(iso);
  const days = ["일", "월", "화", "수", "목", "금", "토"];
  return `${d.getFullYear()}년 ${d.getMonth() + 1}월 ${d.getDate()}일 (${days[d.getDay()]})`;
}

function MeetingSetupContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const roomId = searchParams.get("roomId") ?? "";
  const { user, loading: authLoading } = useAuth();

  const [room, setRoom] = useState<Room | null>(null);
  const [upcomingDate, setUpcomingDate] = useState<string | null>(null);
  const [meetingType, setMeetingType] = useState("회식");
  const [foodCategory, setFoodCategory] = useState("한식");
  const [locationPath, setLocationPath] = useState("");
  const [allMembers, setAllMembers] = useState<MemberInfo[]>([]);
  const [selectedMemberIds, setSelectedMemberIds] = useState<Set<number>>(new Set());
  const [friendSearch, setFriendSearch] = useState("");

  useEffect(() => {
    try {
      const raw = sessionStorage.getItem("locationWizard");
      if (raw) {
        const { province, city, district } = JSON.parse(raw) as Record<string, string>;
        setLocationPath([province, city, district].filter(Boolean).join(" > "));
      }
    } catch {}
  }, []);

  useEffect(() => {
    if (authLoading || !user || !roomId) return;
    apiFetch<PreferenceStatusResponse>(`/api/v1/rooms/${roomId}/preferences`)
      .then((res) => setAllMembers(res.preferences ?? []))
      .catch(() => null);
  }, [authLoading, user, roomId]);

  useEffect(() => {
    if (authLoading || !user || !roomId) return;
    apiFetch<Room>(`/api/v1/rooms/${roomId}`).then(setRoom).catch(() => null);
    apiFetch<MeetingListItem[]>("/api/v1/meetings/")
      .then((meetings) => {
        const now = new Date();
        const next = meetings
          .filter((m) => m.room_id === Number(roomId) && new Date(m.scheduled_at) >= now)
          .sort((a, b) => new Date(a.scheduled_at).getTime() - new Date(b.scheduled_at).getTime())[0];
        if (next) setUpcomingDate(next.scheduled_at);
      })
      .catch(() => null);
  }, [authLoading, user, roomId]);

  useEffect(() => {
    if (room?.category && MEETING_TYPES.includes(room.category)) {
      setMeetingType(room.category);
    }
  }, [room]);

  const selectedMembers = allMembers.filter((m) => selectedMemberIds.has(m.user_id));
  const searchResults = friendSearch
    ? allMembers.filter((m) => m.user_name.includes(friendSearch) && !selectedMemberIds.has(m.user_id))
    : [];

  function toggleMember(id: number) {
    setSelectedMemberIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  function handleCta() {
    try {
      sessionStorage.setItem(
        "meetingWizard",
        JSON.stringify({
          meetingType,
          foodCategory,
          locationPath,
          selectedFriends: selectedMembers.map((m) => m.user_name),
        })
      );
    } catch {}
    router.push(`/m/place/ai-result?roomId=${roomId}`);
  }

  return (
    <div
      style={{
        width: "100%",
        height: "844px",
        background: "#f8fafc",
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
          padding: "0 16px",
          display: "flex",
          alignItems: "center",
          gap: 12,
        }}
      >
        <ArrowLeft
          size={24}
          color="#ffffff"
          style={{ cursor: "pointer" }}
          onClick={() => router.back()}
        />
        <span style={{ fontSize: 18, fontWeight: 700, color: "#ffffff" }}>
          모임 조건 설정
        </span>
      </div>

      {/* Body */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: 20,
          display: "flex",
          flexDirection: "column",
          gap: 16,
        }}
      >
        {/* Date row */}
        <div
          style={{
            borderRadius: 12,
            background: "#ffffff",
            border: "1px solid #e2e8f0",
            padding: "14px 16px",
            display: "flex",
            alignItems: "center",
            gap: 12,
          }}
        >
          <Calendar size={20} color="#4f46e5" />
          <span style={{ fontSize: 14, fontWeight: 600, color: "#1e293b" }}>
            {upcomingDate ? formatDate(upcomingDate) : "2025년 5월 15일 (목)"}
          </span>
        </div>

        {/* People row */}
        <div
          style={{
            borderRadius: 12,
            background: "#ffffff",
            border: "1px solid #e2e8f0",
            padding: "14px 16px",
            display: "flex",
            alignItems: "center",
            gap: 12,
          }}
        >
          <Users size={20} color="#4f46e5" />
          <span style={{ fontSize: 14, fontWeight: 600, color: "#1e293b" }}>
            4명
          </span>
        </div>

        {/* Location row */}
        <div
          onClick={() => router.push(`/m/place/region?roomId=${roomId}`)}
          style={{
            borderRadius: 12,
            background: "#ffffff",
            border: "1px solid #e2e8f0",
            padding: "14px 16px",
            display: "flex",
            alignItems: "center",
            gap: 12,
            cursor: "pointer",
          }}
        >
          <MapPin size={20} color="#4f46e5" style={{ flexShrink: 0 }} />
          <span style={{ fontSize: 14, fontWeight: 600, color: "#1e293b", flex: 1 }}>
            {locationPath || "지역 선택"}
          </span>
          <ChevronRight size={20} color="#94a3b8" style={{ flexShrink: 0 }} />
        </div>

        {/* Friends card */}
        <div
          style={{
            borderRadius: 12,
            background: "#ffffff",
            border: "1px solid #e2e8f0",
            padding: "12px 14px",
            display: "flex",
            flexDirection: "column",
            gap: 10,
          }}
        >
          {/* Header */}
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <UsersRound size={18} color="#4f46e5" style={{ flexShrink: 0 }} />
            <span style={{ fontSize: 13, fontWeight: 700, color: "#1e293b" }}>
              참여 친구
            </span>
            <div style={{ flex: 1 }} />
            <span style={{ fontSize: 11, fontWeight: 600, color: "#94a3b8" }}>
              {selectedMemberIds.size}명 선택됨
            </span>
          </div>

          {/* Search */}
          <div
            style={{
              borderRadius: 10,
              background: "#f8fafc",
              border: "1px solid #e2e8f0",
              padding: "10px 12px",
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            <Search size={16} color="#94a3b8" style={{ flexShrink: 0 }} />
            <input
              value={friendSearch}
              onChange={(e) => setFriendSearch(e.target.value)}
              placeholder="친구 이름으로 검색..."
              style={{
                flex: 1,
                border: "none",
                background: "transparent",
                fontSize: 12,
                color: "#1e293b",
                outline: "none",
              }}
            />
            <UserPlus size={18} color="#4f46e5" style={{ flexShrink: 0 }} />
          </div>

          {/* Search results dropdown */}
          {searchResults.length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {searchResults.map((m, idx) => (
                <div
                  key={m.user_id}
                  onClick={() => { toggleMember(m.user_id); setFriendSearch(""); }}
                  style={{
                    borderRadius: 8,
                    background: "#f1f5f9",
                    padding: "8px 12px",
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    cursor: "pointer",
                  }}
                >
                  <div
                    style={{
                      width: 24,
                      height: 24,
                      borderRadius: 12,
                      background: avatarColor(idx),
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    <span style={{ fontSize: 10, fontWeight: 700, color: "#ffffff" }}>
                      {m.user_name.charAt(0)}
                    </span>
                  </div>
                  <span style={{ fontSize: 12, fontWeight: 600, color: "#1e293b" }}>
                    {m.user_name}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Selected chips */}
          {selectedMembers.length > 0 && (
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {selectedMembers.map((m, idx) => (
                <div
                  key={m.user_id}
                  style={{
                    borderRadius: 18,
                    background: "#f1f5f9",
                    border: "1px solid #e2e8f0",
                    padding: "4px 10px 4px 4px",
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                  }}
                >
                  <div
                    style={{
                      width: 24,
                      height: 24,
                      borderRadius: 12,
                      background: avatarColor(idx),
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    <span style={{ fontSize: 10, fontWeight: 700, color: "#ffffff" }}>
                      {m.user_name.charAt(0)}
                    </span>
                  </div>
                  <span style={{ fontSize: 12, fontWeight: 600, color: "#1e293b" }}>
                    {m.user_name}
                  </span>
                  <XIcon
                    size={14}
                    color="#94a3b8"
                    style={{ cursor: "pointer" }}
                    onClick={() => toggleMember(m.user_id)}
                  />
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Meeting type */}
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: "#475569" }}>
            모임 종류
          </span>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {MEETING_TYPES.map((t) => {
              const sel = meetingType === t;
              return (
                <div
                  key={t}
                  onClick={() => setMeetingType(t)}
                  style={{
                    borderRadius: 18,
                    background: sel ? "#4f46e5" : "#f1f5f9",
                    border: sel ? "none" : "1px solid #e2e8f0",
                    padding: "8px 16px",
                    cursor: "pointer",
                  }}
                >
                  <span
                    style={{
                      fontSize: 12,
                      fontWeight: sel ? 600 : 400,
                      color: sel ? "#ffffff" : "#64748b",
                    }}
                  >
                    {t}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Food category */}
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: "#475569" }}>
            음식 카테고리
          </span>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {FOOD_CATEGORIES.map(({ label, Icon }) => {
              const sel = foodCategory === label;
              return (
                <div
                  key={label}
                  onClick={() => setFoodCategory(label)}
                  style={{
                    borderRadius: 20,
                    background: sel ? "#4f46e5" : "#f1f5f9",
                    border: sel ? "none" : "1px solid #e2e8f0",
                    padding: "8px 14px",
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    cursor: "pointer",
                  }}
                >
                  <Icon size={14} color={sel ? "#ffffff" : "#475569"} />
                  <span
                    style={{
                      fontSize: 12,
                      fontWeight: sel ? 600 : 500,
                      color: sel ? "#ffffff" : "#475569",
                    }}
                  >
                    {label}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Budget row */}
        <div
          style={{
            borderRadius: 12,
            background: "#ffffff",
            border: "1px solid #e2e8f0",
            padding: "14px 16px",
            display: "flex",
            alignItems: "center",
            gap: 12,
          }}
        >
          <Wallet size={20} color="#4f46e5" />
          <span style={{ fontSize: 14, fontWeight: 600, color: "#1e293b" }}>
            인당 25,000원
          </span>
        </div>

        {/* Divider */}
        <div style={{ height: 1, background: "#e2e8f0" }} />

        {/* Wait area */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 14,
            padding: "12px 0",
          }}
        >
          <div
            style={{
              width: 72,
              height: 72,
              borderRadius: 36,
              background: "radial-gradient(circle, #4f46e5, #a855f7)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Sparkles size={32} color="#ffffff" />
          </div>
          <span
            style={{
              fontSize: 17,
              fontWeight: 800,
              color: "#1e293b",
              textAlign: "center",
              whiteSpace: "pre-line",
            }}
          >
            {"AI가 최적의 장소를\n찾고 있어요"}
          </span>
          <span
            style={{ fontSize: 12, color: "#94a3b8", textAlign: "center" }}
          >
            모임 조건에 맞는 장소를 분석 중입니다
          </span>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 8,
              width: "100%",
            }}
          >
            <div
              style={{
                borderRadius: 12,
                background: "#f5f3ff",
                padding: "10px 12px",
                display: "flex",
                alignItems: "center",
                gap: 10,
              }}
            >
              <MapPin size={16} color="#4f46e5" />
              <span style={{ fontSize: 12, fontWeight: 700, color: "#1e293b" }}>
                맞춤 장소 추천
              </span>
            </div>
            <div
              style={{
                borderRadius: 12,
                background: "#f0fdf4",
                padding: "10px 12px",
                display: "flex",
                alignItems: "center",
                gap: 10,
              }}
            >
              <CalendarCheck size={16} color="#16a34a" />
              <span style={{ fontSize: 12, fontWeight: 700, color: "#1e293b" }}>
                실시간 예약 확인
              </span>
            </div>
            <div
              style={{
                borderRadius: 12,
                background: "#eff6ff",
                padding: "10px 12px",
                display: "flex",
                alignItems: "center",
                gap: 10,
              }}
            >
              <Route size={16} color="#2563eb" />
              <span style={{ fontSize: 12, fontWeight: 700, color: "#1e293b" }}>
                최적 경로 안내
              </span>
            </div>
          </div>
        </div>

        {/* CTA */}
        <button
          onClick={handleCta}
          style={{
            width: "100%",
            height: 52,
            borderRadius: 14,
            background: "linear-gradient(180deg, #4f46e5, #6366f1)",
            border: "none",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 8,
            cursor: "pointer",
          }}
        >
          <Sparkles size={18} color="#ffffff" />
          <span style={{ fontSize: 15, fontWeight: 700, color: "#ffffff" }}>
            AI 추천 시작하기
          </span>
        </button>
      </div>
    </div>
  );
}

export default function MeetingSetupPage() {
  return (
    <Suspense fallback={null}>
      <MeetingSetupContent />
    </Suspense>
  );
}
