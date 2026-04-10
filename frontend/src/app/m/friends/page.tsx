"use client";

import { useRouter } from "next/navigation";
import {
  Bell,
  User,
  UserPlus,
  Search,
} from "lucide-react";
import MobileTabBar from "@/components/ui/MobileTabBar";

const friends = [
  { name: "김민준", avatar: "#818cf8", status: "오늘 저녁 가능", dot: "#22c55e" },
  { name: "이서연", avatar: "#f472b6", status: "이번 주 바빠요", dot: "#94a3b8" },
  { name: "박지호", avatar: "#fb923c", status: "언제든 연락주세요", dot: "#22c55e" },
  { name: "최수아", avatar: "#34d399", status: "주말에 만나요!", dot: "#22c55e" },
  { name: "정우진", avatar: "#60a5fa", status: "다음 주 시간 있어요", dot: "#94a3b8" },
];


export default function FriendsPage() {
  const router = useRouter();
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
          <Bell size={22} color="#ffffffcc" style={{ cursor: "pointer" }} onClick={() => router.push("/m/notifications")} />
          <User size={22} color="#ffffffcc" style={{ cursor: "pointer" }} onClick={() => router.push("/m/profile")} />
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
          <span
            style={{
              fontFamily: "Pretendard, sans-serif",
              fontSize: 13,
              fontWeight: 400,
              color: "#94a3b8",
            }}
          >
            이름으로 검색
          </span>
        </div>

        {/* Friend list */}
        <div style={{ padding: "8px 20px 0 20px" }}>
          {friends.map((friend, i) => (
            <div key={friend.name}>
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
                    background: friend.avatar,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "#ffffff",
                    fontFamily: "Pretendard, sans-serif",
                    fontSize: 16,
                    fontWeight: 600,
                  }}
                >
                  {friend.name.charAt(0)}
                </div>

                {/* Name + status */}
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
                    {friend.status}
                  </span>
                </div>

                {/* Online dot */}
                <div
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: "50%",
                    background: friend.dot,
                  }}
                />
              </div>

              {/* Divider */}
              {i < friends.length - 1 && (
                <div style={{ height: 1, background: "#f1f5f9" }} />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Tab bar */}
      <MobileTabBar active="친구" />
    </div>
  );
}
