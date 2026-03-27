"use client";

import { useState } from "react";
import { UserPlus, Search, X, Check } from "lucide-react";

type FriendStatus = "add" | "already" | "requested";

interface FriendResult {
  name: string;
  email: string;
  color: string;
  status: FriendStatus;
}

const mockResults: FriendResult[] = [
  { name: "한소희", email: "sohee.han@email.com", color: "#818cf8", status: "add" },
  { name: "박지민", email: "jimin.park@email.com", color: "#f472b6", status: "already" },
  { name: "윤도현", email: "dohyun.yoon@email.com", color: "#34d399", status: "add" },
  { name: "이승우", email: "seungwoo.lee@email.com", color: "#fb923c", status: "requested" },
  { name: "최유나", email: "yuna.choi@email.com", color: "#fbbf24", status: "add" },
];

type Tab = "search" | "recommend" | "code";

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function AddFriendModal({ open, onClose }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>("search");
  const [query, setQuery] = useState("");

  if (!open) return null;

  const tabs: { key: Tab; label: string }[] = [
    { key: "search", label: "검색 결과" },
    { key: "recommend", label: "추천 친구" },
    { key: "code", label: "초대 코드" },
  ];

  return (
    /* Backdrop */
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 100,
        background: "rgba(0,0,0,0.35)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {/* Modal */}
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 540,
          borderRadius: 24,
          background: "#ffffff",
          boxShadow: "0 20px 60px rgba(0,0,0,0.2)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          fontFamily: "Pretendard Variable, Pretendard, sans-serif",
        }}
      >
        {/* Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "24px 32px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <UserPlus style={{ width: 24, height: 24, color: "#4f46e5" }} />
            <span style={{ fontSize: 22, fontWeight: 600, color: "#111827" }}>
              친구 추가
            </span>
          </div>
          <button
            onClick={onClose}
            style={{
              width: 36,
              height: 36,
              borderRadius: "50%",
              border: "none",
              background: "#f1f5f9",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: "pointer",
            }}
          >
            <X style={{ width: 18, height: 18, color: "#64748b" }} />
          </button>
        </div>

        {/* Search bar */}
        <div style={{ padding: "0 32px" }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "0 16px",
              height: 48,
              borderRadius: 14,
              border: "1px solid #e2e8f0",
              background: "#ffffff",
            }}
          >
            <Search style={{ width: 18, height: 18, color: "#94a3b8" }} />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="이름, 이메일 또는 코드로 검색"
              style={{
                flex: 1,
                border: "none",
                outline: "none",
                fontSize: 14,
                fontWeight: 400,
                color: "#1e293b",
                fontFamily: "Pretendard Variable, Pretendard, sans-serif",
                background: "transparent",
              }}
            />
            <button
              style={{
                width: 36,
                height: 36,
                borderRadius: 10,
                border: "none",
                background: "#4f46e5",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                cursor: "pointer",
              }}
            >
              <Search style={{ width: 16, height: 16, color: "#ffffff" }} />
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div
          style={{
            display: "flex",
            padding: "0 32px",
            marginTop: 20,
            borderBottom: "1px solid #e2e8f0",
          }}
        >
          {tabs.map((tab) => {
            const isActive = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                style={{
                  flex: 1,
                  padding: "12px 0",
                  border: "none",
                  borderBottom: isActive ? "2px solid #4f46e5" : "2px solid transparent",
                  background: "transparent",
                  fontSize: 14,
                  fontWeight: isActive ? 600 : 400,
                  color: isActive ? "#4f46e5" : "#94a3b8",
                  cursor: "pointer",
                  fontFamily: "Pretendard Variable, Pretendard, sans-serif",
                }}
              >
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Results list */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            padding: "8px 32px",
            maxHeight: 400,
            overflowY: "auto",
          }}
        >
          {mockResults.map((friend) => (
            <div
              key={friend.email}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 14,
                padding: "16px 6px",
                borderBottom: "1px solid #f1f5f9",
              }}
            >
              {/* Avatar */}
              <div
                style={{
                  width: 44,
                  height: 44,
                  borderRadius: "50%",
                  background: friend.color,
                  flexShrink: 0,
                }}
              />
              {/* Info */}
              <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 4 }}>
                <span style={{ fontSize: 15, fontWeight: 600, color: "#111827" }}>
                  {friend.name}
                </span>
                <span style={{ fontSize: 12, fontWeight: 400, color: "#94a3b8" }}>
                  {friend.email}
                </span>
              </div>
              {/* Action button */}
              {friend.status === "add" && (
                <button
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 4,
                    width: 90,
                    padding: "8px 0",
                    borderRadius: 10,
                    border: "none",
                    background: "#4f46e5",
                    color: "#ffffff",
                    fontSize: 13,
                    fontWeight: 500,
                    cursor: "pointer",
                    fontFamily: "Pretendard Variable, Pretendard, sans-serif",
                  }}
                >
                  <UserPlus style={{ width: 14, height: 14, color: "#ffffff" }} />
                  추가
                </button>
              )}
              {friend.status === "already" && (
                <span
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    width: 90,
                    padding: "8px 0",
                    borderRadius: 10,
                    border: "1px solid #e2e8f0",
                    background: "#ffffff",
                    color: "#94a3b8",
                    fontSize: 13,
                    fontWeight: 500,
                  }}
                >
                  이미 친구
                </span>
              )}
              {friend.status === "requested" && (
                <button
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 4,
                    width: 90,
                    padding: "8px 0",
                    borderRadius: 10,
                    border: "none",
                    background: "#22c55e",
                    color: "#ffffff",
                    fontSize: 13,
                    fontWeight: 500,
                    cursor: "pointer",
                    fontFamily: "Pretendard Variable, Pretendard, sans-serif",
                  }}
                >
                  <Check style={{ width: 14, height: 14, color: "#ffffff" }} />
                  요청됨
                </button>
              )}
            </div>
          ))}
        </div>

        {/* Footer */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "16px 32px 24px",
          }}
        >
          <UserPlus style={{ width: 16, height: 16, color: "#94a3b8" }} />
          <span style={{ fontSize: 13, fontWeight: 400, color: "#94a3b8" }}>
            친구 추가 시 상대방에게 요청이 전송됩니다
          </span>
        </div>
      </div>
    </div>
  );
}
