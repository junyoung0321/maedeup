"use client";

import { useRouter } from "next/navigation";
import {
  LayoutDashboard,
  Users,
  CalendarDays,
  MessageSquare,
  Sparkles,
  MapPin,
  Settings,
  HelpCircle,
  LogOut,
} from "lucide-react";
import { useAuth } from "@/hooks/useAuth";

interface Props {
  open: boolean;
  onClose: () => void;
}

const menuItems = [
  { icon: LayoutDashboard, label: "대시보드", href: "/" },
  { icon: Users, label: "모임 관리", href: "/meetings" },
  { icon: CalendarDays, label: "일정 관리", href: "/schedule" },
  { icon: MessageSquare, label: "채팅", href: "/chat" },
  { icon: Sparkles, label: "AI 어시스턴트", href: "/assistant" },
  { icon: MapPin, label: "장소 탐색", href: "/ai-recommend" },
  { icon: Settings, label: "설정", href: "/settings" },
  { icon: HelpCircle, label: "도움말", href: "/help" },
];

export default function MenuPanel({ open, onClose }: Props) {
  const router = useRouter();
  const { logout } = useAuth();

  if (!open) return null;

  const handleNav = (href: string) => {
    onClose();
    router.push(href);
  };

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
          width: 200,
          borderRadius: 16,
          background: "#ffffff",
          boxShadow: "0 10px 40px rgba(0,0,0,0.15)",
          border: "1px solid #e2e8f0",
          overflow: "hidden",
          fontFamily: "Pretendard Variable, Pretendard, sans-serif",
        }}
      >
        {/* Header */}
        <div style={{ padding: "14px 18px 10px", borderBottom: "1px solid #f1f5f9" }}>
          <span style={{ fontSize: 15, fontWeight: 700, color: "#111827" }}>메뉴</span>
        </div>

        {/* Nav items */}
        <div style={{ display: "flex", flexDirection: "column", padding: "6px 0" }}>
          {menuItems.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.label}
                onClick={() => handleNav(item.href)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "10px 18px",
                  border: "none",
                  background: "transparent",
                  cursor: "pointer",
                  textAlign: "left",
                  fontFamily: "Pretendard Variable, Pretendard, sans-serif",
                  transition: "background 0.1s",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "#f8fafc")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
              >
                <Icon style={{ width: 15, height: 15, color: "#374151", flexShrink: 0 }} />
                <span style={{ fontSize: 13, fontWeight: 500, color: "#374151" }}>{item.label}</span>
              </button>
            );
          })}

          {/* Divider */}
          <div style={{ height: 1, background: "#f1f5f9", margin: "6px 0" }} />

          {/* Logout */}
          <button
            onClick={() => { onClose(); logout(); }}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "10px 18px",
              border: "none",
              background: "transparent",
              cursor: "pointer",
              textAlign: "left",
              fontFamily: "Pretendard Variable, Pretendard, sans-serif",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "#fff5f5")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
          >
            <LogOut style={{ width: 15, height: 15, color: "#ef4444", flexShrink: 0 }} />
            <span style={{ fontSize: 13, fontWeight: 500, color: "#ef4444" }}>로그아웃</span>
          </button>
        </div>
      </div>
    </div>
  );
}
