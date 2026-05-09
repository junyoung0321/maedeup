"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { apiFetch } from "@/lib/api";

interface Props {
  open: boolean;
  onClose: () => void;
}

interface AvailableFriend {
  user: { id: number; name: string; email: string; picture?: string | null };
  state: "free" | "busy_now" | "free_in" | "unknown";
  available_at?: string | null;
}

const AVATAR_COLORS = ["#818cf8", "#fb923c", "#34d399", "#f472b6", "#60a5fa", "#a78bfa"];

function stateLabel(f: AvailableFriend): string {
  if (f.state === "free") return "지금 가능";
  if (f.state === "free_in" && f.available_at) {
    const mins = Math.round((new Date(f.available_at).getTime() - Date.now()) / 60000);
    return mins > 0 ? `${mins}분 후 가능` : "곧 가능";
  }
  if (f.state === "busy_now") return "지금 바쁨";
  return "캘린더 미연동";
}

const times = [
  { icon: "🕐", label: "오늘 오후 3:00", selected: true },
  { icon: "🌙", label: "오늘 저녁 7:00", selected: false },
];

export default function QuickMatchPopup({ open, onClose }: Props) {
  const router = useRouter();
  const [friends, setFriends] = useState<AvailableFriend[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    apiFetch<{ friends: AvailableFriend[] }>("/api/v1/recommendations/available-friends?window_minutes=120")
      .then((data) => setFriends(data.friends.slice(0, 4)))
      .catch(() => setFriends([]))
      .finally(() => setLoading(false));
  }, [open]);

  if (!open) return null;

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 100,
        background: "rgba(0,0,0,0.5)",
        display: "flex",
        flexDirection: "column",
        justifyContent: "flex-end",
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 390,
          maxWidth: "100%",
          alignSelf: "center",
          borderRadius: "20px 20px 0 0",
          background: "#ffffff",
          padding: "12px 24px 24px",
          display: "flex",
          flexDirection: "column",
          gap: 22,
          fontFamily: "Pretendard Variable, Pretendard, sans-serif",
        }}
      >
        {/* Handle */}
        <div style={{ display: "flex", justifyContent: "center" }}>
          <div style={{ width: 40, height: 4, borderRadius: 2, background: "#CBD5E1" }} />
        </div>

        {/* Header */}
        <div style={{ display: "flex", flexDirection: "column", gap: 6, paddingTop: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 24 }}>✨</span>
            <span style={{ fontSize: 24, fontWeight: 800, color: "#1e293b" }}>빠른 모임 매칭</span>
          </div>
          <span style={{ fontSize: 14, color: "#64748b", lineHeight: 1.6 }}>
            지금 만날 수 있는 친구를 찾아 빠르게 모임을 만들어보세요
          </span>
          <div
            style={{
              width: 60,
              height: 3,
              borderRadius: 2,
              background: "linear-gradient(90deg, #4f46e5, #8B5CF6)",
            }}
          />
        </div>

        {/* Friends */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12, paddingTop: 20 }}>
          <span style={{ fontSize: 15, fontWeight: 600, color: "#1e293b" }}>지금 가능한 친구</span>
          {loading ? (
            <div style={{ display: "flex", justifyContent: "center", padding: "16px 0" }}>
              <Loader2 size={24} color="#4f46e5" className="animate-spin" />
            </div>
          ) : friends.length === 0 ? (
            <span style={{ fontSize: 13, color: "#94a3b8", textAlign: "center", padding: "12px 0" }}>
              친구 가용성 정보를 불러올 수 없습니다
            </span>
          ) : (
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              {friends.map((f, i) => {
                const active = f.state === "free";
                return (
                  <div
                    key={f.user.id}
                    style={{
                      width: 76,
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      gap: 6,
                    }}
                  >
                    <div style={{ position: "relative" }}>
                      <div
                        style={{
                          width: 48,
                          height: 48,
                          borderRadius: "50%",
                          background: AVATAR_COLORS[i % AVATAR_COLORS.length],
                          border: active ? "2.5px solid #4f46e5" : "none",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          color: "#fff",
                          fontSize: 18,
                          fontWeight: 600,
                        }}
                      >
                        {f.user.name.charAt(0)}
                      </div>
                      {active && (
                        <div
                          style={{
                            position: "absolute",
                            top: 0,
                            right: -6,
                            width: 16,
                            height: 16,
                            borderRadius: "50%",
                            background: "#4f46e5",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                          }}
                        >
                          <span style={{ fontSize: 9, fontWeight: 700, color: "#fff" }}>✓</span>
                        </div>
                      )}
                    </div>
                    <span style={{ fontSize: 13, fontWeight: 500, color: "#1e293b" }}>
                      {f.user.name}
                    </span>
                    <span
                      style={{
                        fontSize: 11,
                        color: active ? "#4f46e5" : "#64748b",
                        textAlign: "center",
                      }}
                    >
                      {stateLabel(f)}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Times */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12, paddingTop: 24 }}>
          <span style={{ fontSize: 15, fontWeight: 600, color: "#1e293b" }}>추천 시간</span>
          <div style={{ display: "flex", gap: 10 }}>
            {times.map((t) => (
              <div
                key={t.label}
                style={{
                  flex: 1,
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "14px 16px",
                  borderRadius: 12,
                  background: t.selected ? "#f0f0ff" : "#f8fafc",
                  border: t.selected ? "1.5px solid #4f46e5" : "1px solid #e2e8f0",
                  cursor: "pointer",
                }}
              >
                <span style={{ fontSize: 16 }}>{t.icon}</span>
                <span
                  style={{
                    fontSize: 14,
                    fontWeight: 500,
                    color: t.selected ? "#4f46e5" : "#1e293b",
                  }}
                >
                  {t.label}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div style={{ flex: 1 }} />

        <button
          onClick={() => {
            onClose();
            router.push("/m/meeting/new");
          }}
          style={{
            width: "100%",
            padding: "16px 0",
            borderRadius: 14,
            border: "none",
            background: "#4f46e5",
            color: "#ffffff",
            fontSize: 16,
            fontWeight: 600,
            cursor: "pointer",
            fontFamily: "Pretendard Variable, Pretendard, sans-serif",
          }}
        >
          모임 만들기
        </button>
      </div>
    </div>
  );
}
