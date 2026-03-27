"use client";

import { User, Users, Settings, CreditCard, Clock, LogOut } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";

interface Props {
  open: boolean;
  onClose: () => void;
}

const menuItems = [
  { icon: Users, label: "내 프로필", color: "#374151" },
  { icon: Settings, label: "설정", color: "#374151" },
  { icon: CreditCard, label: "선호도 관리", color: "#374151" },
  { icon: Clock, label: "도움말", color: "#374151" },
  { icon: LogOut, label: "로그아웃", color: "#ef4444" },
];

export default function ProfileDropdown({ open, onClose }: Props) {
  const { user, logout } = useAuth();

  if (!open) return null;

  return (
    <div
      onClick={onClose}
      style={{ position: "fixed", inset: 0, zIndex: 90 }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          position: "absolute",
          top: 79,
          right: 28,
          width: 220,
          borderRadius: 16,
          background: "#ffffff",
          boxShadow: "0 10px 40px rgba(0,0,0,0.15)",
          border: "1px solid #e2e8f0",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          fontFamily: "Pretendard Variable, Pretendard, sans-serif",
        }}
      >
        {/* User info */}
        <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "16px 18px", borderBottom: "1px solid #f1f5f9" }}>
          <div style={{ width: 40, height: 40, borderRadius: "50%", background: "#4f46e5", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, overflow: "hidden" }}>
            {user?.picture ? (
              <img src={user.picture} alt="profile" style={{ width: 40, height: 40, objectFit: "cover" }} />
            ) : (
              <User style={{ width: 20, height: 20, color: "#ffffff" }} />
            )}
          </div>
          <div style={{ display: "flex", flexDirection: "column" }}>
            <span style={{ fontSize: 14, fontWeight: 600, color: "#111827" }}>{user?.name ?? ""}</span>
            <span style={{ fontSize: 11, fontWeight: 400, color: "#94a3b8" }}>{user?.email ?? ""}</span>
          </div>
        </div>

        {/* Menu items */}
        <div style={{ display: "flex", flexDirection: "column", padding: "6px 0" }}>
          {menuItems.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.label}
                onClick={item.label === "로그아웃" ? logout : undefined}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "10px 18px",
                  border: "none",
                  background: "transparent",
                  cursor: "pointer",
                  fontFamily: "Pretendard Variable, Pretendard, sans-serif",
                }}
              >
                <Icon style={{ width: 16, height: 16, color: item.color }} />
                <span style={{ fontSize: 13, fontWeight: 500, color: item.color }}>{item.label}</span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
