"use client";

import { useRouter } from "next/navigation";

interface Props {
  open: boolean;
  onClose: () => void;
}

const friends = [
  { name: "민지", status: "지금 가능", color: "#818cf8", active: true },
  { name: "준호", status: "30분 후 가능", color: "#fb923c", active: false },
  { name: "서연", status: "지금 가능", color: "#34d399", active: true },
  { name: "현우", status: "1시간 후 가능", color: "#f472b6", active: false },
];

const times = [
  { icon: "🕐", label: "오늘 오후 3:00", selected: true },
  { icon: "🌙", label: "오늘 저녁 7:00", selected: false },
];

export default function QuickMatchPopup({ open, onClose }: Props) {
  const router = useRouter();
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
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            {friends.map((f) => (
              <div
                key={f.name}
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
                      background: f.color,
                      border: f.active ? "2.5px solid #4f46e5" : "none",
                    }}
                  />
                  {f.active && (
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
                <span style={{ fontSize: 13, fontWeight: 500, color: "#1e293b" }}>{f.name}</span>
                <span
                  style={{
                    fontSize: 11,
                    color: f.active ? "#4f46e5" : "#64748b",
                  }}
                >
                  {f.status}
                </span>
              </div>
            ))}
          </div>
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

        {/* Spacer + CTA */}
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
