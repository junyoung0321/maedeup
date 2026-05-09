"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Bell, User, UserPlus, Search } from "lucide-react";
import MobileTabBar from "@/components/ui/MobileTabBar";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";

interface FriendInfo {
  id: number;
  name: string;
  email: string;
  picture?: string | null;
}

const AVATAR_COLORS = [
  "#818cf8",
  "#f472b6",
  "#fb923c",
  "#34d399",
  "#60a5fa",
  "#a78bfa",
  "#fbbf24",
];

export default function FriendsPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [friends, setFriends] = useState<FriendInfo[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      router.push("/m/login");
      return;
    }
    apiFetch<FriendInfo[]>("/api/v1/users/friends")
      .then(setFriends)
      .catch(() => setFriends([]))
      .finally(() => setLoading(false));
  }, [authLoading, user, router]);

  const filtered = query.trim()
    ? friends.filter(
        (f) =>
          f.name.toLowerCase().includes(query.toLowerCase()) ||
          f.email.toLowerCase().includes(query.toLowerCase())
      )
    : friends;

  return (
    <div
      style={{
        width: 390,
        height: 844,
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        background: "#ffffffff",
        fontFamily: "Pretendard, Inter, sans-serif",
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
          alignItems: "center",
          justifyContent: "space-between",
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
          <Bell
            size={22}
            color="#ffffffcc"
            style={{ cursor: "pointer" }}
            onClick={() => router.push("/m/notifications")}
          />
          <User
            size={22}
            color="#ffffffcc"
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
          padding: 20,
          display: "flex",
          flexDirection: "column",
          gap: 16,
          overflow: "hidden",
        }}
      >
        {/* Title row */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <span
            style={{
              fontFamily: "Pretendard, sans-serif",
              fontSize: 22,
              fontWeight: 700,
              color: "#0f172a",
            }}
          >
            친구 목록
          </span>
          <button
            onClick={() => alert("친구 추가 기능은 준비 중입니다")}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 4,
              background: "#4f46e5",
              borderRadius: 20,
              padding: "6px 12px",
              border: "none",
              cursor: "pointer",
            }}
          >
            <UserPlus size={14} color="#ffffff" />
            <span
              style={{
                fontFamily: "Pretendard, sans-serif",
                fontSize: 12,
                fontWeight: 600,
                color: "#ffffff",
              }}
            >
              추가
            </span>
          </button>
        </div>

        {/* Search bar */}
        <div
          style={{
            height: 40,
            minHeight: 40,
            borderRadius: 12,
            background: "#ffffff",
            border: "1px solid #e2e8f0",
            padding: "0 14px",
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          <Search size={16} color="#94a3b8" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="이름으로 검색"
            style={{
              flex: 1,
              border: "none",
              outline: "none",
              background: "transparent",
              fontFamily: "Pretendard, sans-serif",
              fontSize: 13,
              fontWeight: 400,
              color: "#1e293b",
            }}
          />
        </div>

        {/* Friend list */}
        {loading ? (
          <div
            style={{
              flex: 1,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <span style={{ fontSize: 14, color: "#94a3b8" }}>
              불러오는 중…
            </span>
          </div>
        ) : filtered.length === 0 ? (
          <div
            style={{
              flex: 1,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <span style={{ fontSize: 14, color: "#94a3b8" }}>
              {friends.length === 0 ? "아직 친구가 없습니다" : "검색 결과가 없습니다"}
            </span>
          </div>
        ) : (
          <div style={{ padding: "8px 20px 0 20px", overflowY: "auto" }}>
            {filtered.map((friend, i) => (
              <div key={friend.id}>
                <div
                  style={{
                    height: 64,
                    padding: "0 4px",
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                  }}
                >
                  {/* Avatar */}
                  <div
                    style={{
                      width: 42,
                      height: 42,
                      minWidth: 42,
                      borderRadius: "50%",
                      background: AVATAR_COLORS[i % AVATAR_COLORS.length],
                      overflow: "hidden",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      color: "#ffffff",
                      fontFamily: "Pretendard, sans-serif",
                      fontSize: 16,
                      fontWeight: 600,
                    }}
                  >
                    {friend.picture ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={friend.picture}
                        alt=""
                        style={{
                          width: "100%",
                          height: "100%",
                          objectFit: "cover",
                        }}
                      />
                    ) : (
                      friend.name.charAt(0)
                    )}
                  </div>

                  {/* Name + email */}
                  <div
                    style={{
                      flex: 1,
                      display: "flex",
                      flexDirection: "column",
                      justifyContent: "center",
                      gap: 2,
                    }}
                  >
                    <span
                      style={{
                        fontFamily: "Inter, sans-serif",
                        fontSize: 15,
                        fontWeight: 600,
                        color: "#111827",
                      }}
                    >
                      {friend.name}
                    </span>
                    <span
                      style={{
                        fontFamily: "Inter, sans-serif",
                        fontSize: 12,
                        fontWeight: 400,
                        color: "#94a3b8",
                      }}
                    >
                      {friend.email}
                    </span>
                  </div>
                </div>

                {/* Divider */}
                {i < filtered.length - 1 && (
                  <div style={{ height: 1, background: "#f1f5f9" }} />
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Tab bar */}
      <MobileTabBar active="친구" />
    </div>
  );
}
