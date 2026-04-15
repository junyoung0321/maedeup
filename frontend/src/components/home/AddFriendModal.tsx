"use client";

import { useEffect, useRef, useState } from "react";
import { UserPlus, Search, X, Check } from "lucide-react";
import { apiFetch } from "@/lib/api";
import type { FriendInfo } from "@/types";

type RequestState = "idle" | "pending" | "sent" | "already" | "error";

interface SearchResult extends FriendInfo {
  state: RequestState;
  color: string;
}

const AVATAR_PALETTE = [
  "#c7d2fe", "#93c5fd", "#86efac", "#fca5a5",
  "#fde68a", "#fbcfe8", "#a5f3fc", "#d9f99d",
];

function colorFor(id: number): string {
  return AVATAR_PALETTE[id % AVATAR_PALETTE.length];
}

type Tab = "search" | "recommend" | "code";

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function AddFriendModal({ open, onClose }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>("search");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!open) return;
    const trimmed = query.trim();
    if (debounceRef.current) clearTimeout(debounceRef.current);

    if (trimmed.length === 0) {
      setResults([]);
      setSearchError(null);
      setSearching(false);
      return;
    }

    setSearching(true);
    setSearchError(null);
    debounceRef.current = setTimeout(() => {
      apiFetch<FriendInfo[]>(`/api/v1/users/search?q=${encodeURIComponent(trimmed)}`)
        .then((data) => {
          setResults(
            data.map((u) => ({
              ...u,
              state: "idle" as RequestState,
              color: colorFor(u.id),
            }))
          );
          setSearching(false);
        })
        .catch(() => {
          setSearchError("검색 중 오류가 발생했어요");
          setResults([]);
          setSearching(false);
        });
    }, 300);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query, open]);

  if (!open) return null;

  const tabs: { key: Tab; label: string }[] = [
    { key: "search", label: "검색 결과" },
    { key: "recommend", label: "추천 친구" },
    { key: "code", label: "초대 코드" },
  ];

  const sendRequest = async (addressee: SearchResult) => {
    setResults((prev) =>
      prev.map((r) => (r.id === addressee.id ? { ...r, state: "pending" } : r))
    );
    try {
      await apiFetch<{ id: number; status: string }>("/api/v1/users/friends", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ addressee_id: addressee.id }),
      });
      setResults((prev) =>
        prev.map((r) => (r.id === addressee.id ? { ...r, state: "sent" } : r))
      );
    } catch (e) {
      const msg = e instanceof Error ? e.message : "";
      const already = msg.includes("409") || msg.includes("이미");
      setResults((prev) =>
        prev.map((r) =>
          r.id === addressee.id
            ? { ...r, state: already ? "already" : "error" }
            : r
        )
      );
    }
  };

  return (
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
              placeholder="이름 또는 이메일로 검색"
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
          </div>
        </div>

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

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            padding: "8px 32px",
            minHeight: 200,
            maxHeight: 400,
            overflowY: "auto",
          }}
        >
          {activeTab !== "search" ? (
            <div
              style={{
                flex: 1,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                padding: "40px 0",
                color: "#94a3b8",
                fontSize: 14,
              }}
            >
              준비 중인 기능이에요
            </div>
          ) : query.trim().length === 0 ? (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                padding: "40px 0",
                color: "#94a3b8",
                fontSize: 14,
              }}
            >
              이름 또는 이메일을 입력해주세요
            </div>
          ) : searching ? (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                padding: "40px 0",
                color: "#94a3b8",
                fontSize: 14,
              }}
            >
              검색 중...
            </div>
          ) : searchError ? (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                padding: "40px 0",
                color: "#ef4444",
                fontSize: 14,
              }}
            >
              {searchError}
            </div>
          ) : results.length === 0 ? (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                padding: "40px 0",
                color: "#94a3b8",
                fontSize: 14,
              }}
            >
              일치하는 유저가 없어요
            </div>
          ) : (
            results.map((friend) => (
              <div
                key={friend.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 14,
                  padding: "16px 6px",
                  borderBottom: "1px solid #f1f5f9",
                }}
              >
                <div
                  style={{
                    width: 44,
                    height: 44,
                    borderRadius: "50%",
                    background: friend.color,
                    flexShrink: 0,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "#334155",
                    fontSize: 15,
                    fontWeight: 600,
                  }}
                >
                  {friend.name.charAt(0)}
                </div>
                <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 4, minWidth: 0 }}>
                  <span style={{ fontSize: 15, fontWeight: 600, color: "#111827" }}>
                    {friend.name}
                  </span>
                  <span
                    style={{
                      fontSize: 12,
                      fontWeight: 400,
                      color: "#94a3b8",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {friend.email}
                  </span>
                </div>

                {friend.state === "idle" && (
                  <button
                    onClick={() => sendRequest(friend)}
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
                    <UserPlus style={{ width: 14, height: 14 }} />
                    추가
                  </button>
                )}
                {friend.state === "pending" && (
                  <span
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      width: 90,
                      padding: "8px 0",
                      borderRadius: 10,
                      background: "#e0e7ff",
                      color: "#4f46e5",
                      fontSize: 13,
                      fontWeight: 500,
                    }}
                  >
                    전송 중...
                  </span>
                )}
                {friend.state === "sent" && (
                  <span
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: 4,
                      width: 90,
                      padding: "8px 0",
                      borderRadius: 10,
                      background: "#22c55e",
                      color: "#ffffff",
                      fontSize: 13,
                      fontWeight: 500,
                    }}
                  >
                    <Check style={{ width: 14, height: 14 }} />
                    요청됨
                  </span>
                )}
                {friend.state === "already" && (
                  <span
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      width: 90,
                      padding: "8px 0",
                      borderRadius: 10,
                      border: "1px solid #e2e8f0",
                      color: "#94a3b8",
                      fontSize: 13,
                      fontWeight: 500,
                    }}
                  >
                    이미 친구
                  </span>
                )}
                {friend.state === "error" && (
                  <button
                    onClick={() => sendRequest(friend)}
                    style={{
                      width: 90,
                      padding: "8px 0",
                      borderRadius: 10,
                      border: "1px solid #ef4444",
                      background: "#ffffff",
                      color: "#ef4444",
                      fontSize: 13,
                      fontWeight: 500,
                      cursor: "pointer",
                    }}
                  >
                    재시도
                  </button>
                )}
              </div>
            ))
          )}
        </div>

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
