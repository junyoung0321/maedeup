"use client";

import { useRouter, usePathname } from "next/navigation";
import { Users, House, Calendar, MessageCircle, User } from "lucide-react";

const tabs = [
  { label: "친구", icon: Users, href: "/m/friends" },
  { label: "홈", icon: House, href: "/m/explore" },
  { label: "캘린더", icon: Calendar, href: "/m/calendar" },
  { label: "채팅", icon: MessageCircle, href: "/m/chat" },
  { label: "프로필", icon: User, href: "/m/profile" },
] as const;

interface Props {
  /** Which tab is active. Defaults to auto-detect from pathname. */
  active?: "친구" | "홈" | "캘린더" | "채팅" | "프로필";
  /** "pill" for explore-style rounded bar, "flat" for standard bottom bar */
  variant?: "pill" | "flat";
}

export default function MobileTabBar({ active, variant = "flat" }: Props) {
  const router = useRouter();
  const pathname = usePathname();

  const getActive = () => {
    if (active) return active;
    if (pathname.startsWith("/m/friends")) return "친구";
    if (pathname.startsWith("/m/calendar")) return "캘린더";
    if (pathname.startsWith("/m/chat")) return "채팅";
    if (pathname.startsWith("/m/profile")) return "프로필";
    return "홈";
  };

  const currentActive = getActive();

  if (variant === "pill") {
    return (
      <div
        style={{
          background: "#ffffff",
          padding: "12px 21px 21px 21px",
        }}
      >
        <div
          style={{
            borderRadius: 36,
            background: "#ffffff",
            border: "1px solid #e5e7eb",
            height: 62,
            padding: 4,
            display: "flex",
            alignItems: "center",
          }}
        >
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = tab.label === currentActive;
            return (
              <div
                key={tab.label}
                onClick={() => router.push(tab.href)}
                style={{
                  flex: 1,
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 4,
                  borderRadius: isActive ? 26 : 0,
                  background: isActive ? "#4f46e5" : "transparent",
                  height: "100%",
                  cursor: "pointer",
                }}
              >
                <Icon size={18} color={isActive ? "#ffffff" : "#94a3b8"} />
                <span
                  style={{
                    fontFamily: "Pretendard, sans-serif",
                    fontSize: 10,
                    fontWeight: isActive ? 600 : 500,
                    color: isActive ? "#ffffff" : "#94a3b8",
                    letterSpacing: 0.5,
                  }}
                >
                  {tab.label}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        height: 80,
        minHeight: 80,
        background: "#ffffff",
        borderTop: "1px solid #e2e8f0",
        padding: "10px 0 26px 0",
        display: "flex",
        justifyContent: "space-around",
        alignItems: "center",
      }}
    >
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const isActive = tab.label === currentActive;
        const color = isActive ? "#4f46e5" : "#94a3b8";
        return (
          <div
            key={tab.label}
            onClick={() => router.push(tab.href)}
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 4,
              cursor: "pointer",
              flex: 1,
            }}
          >
            <Icon size={22} color={color} strokeWidth={2} />
            <span
              style={{
                fontFamily: "Inter, sans-serif",
                fontSize: 10,
                fontWeight: isActive ? 600 : 500,
                color,
              }}
            >
              {tab.label}
            </span>
          </div>
        );
      })}
    </div>
  );
}
