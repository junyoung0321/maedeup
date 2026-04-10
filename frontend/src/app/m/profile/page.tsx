"use client";

import { useRouter } from "next/navigation";
import {
  Bell,
  User,
  Settings,
  Calendar,
  Shield,
  Info,
  ChevronRight,
} from "lucide-react";
import MobileTabBar from "@/components/ui/MobileTabBar";

export default function ProfilePage() {
  const router = useRouter();
  return (
    <div
      style={{
        width: 390,
        height: 844,
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        background: "#ffffff",
        fontFamily: "Pretendard, sans-serif",
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
          justifyContent: "space-between",
          alignItems: "center",
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
          <Bell size={22} color="#ffffff" style={{ cursor: "pointer" }} onClick={() => router.push("/m/notifications")} />
          <User size={22} color="#ffffff" style={{ cursor: "pointer" }} onClick={() => router.push("/m/profile")} />
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
          gap: 24,
          overflowY: "auto",
          overflowX: "hidden",
        }}
      >
        {/* Profile Card */}
        <div
          style={{
            borderRadius: 16,
            background: "#ffffff",
            border: "1px solid #e5e7eb",
            padding: 24,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 16,
          }}
        >
          {/* Avatar */}
          <div
            style={{
              width: 72,
              height: 72,
              borderRadius: "50%",
              background: "#818cf8",
            }}
          />

          {/* Name */}
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
            <span
              style={{
                fontFamily: "Pretendard, sans-serif",
                fontSize: 20,
                fontWeight: 700,
                color: "#1e293b",
              }}
            >
              홍길동
            </span>
            <span
              style={{
                fontFamily: "Pretendard, sans-serif",
                fontSize: 13,
                fontWeight: 400,
                color: "#94a3b8",
              }}
            >
              hong@gmail.com
            </span>
          </div>

          {/* Stats Row */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-around",
              width: "100%",
            }}
          >
            {[
              { value: "12", label: "참여 모임" },
              { value: "28", label: "친구" },
              { value: "45", label: "일정 완료" },
            ].map((stat) => (
              <div
                key={stat.label}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: 4,
                }}
              >
                <span
                  style={{
                    fontFamily: "Inter, sans-serif",
                    fontSize: 20,
                    fontWeight: 700,
                    color: "#4f46e5",
                  }}
                >
                  {stat.value}
                </span>
                <span
                  style={{
                    fontFamily: "Pretendard, sans-serif",
                    fontSize: 11,
                    fontWeight: 400,
                    color: "#64748b",
                  }}
                >
                  {stat.label}
                </span>
              </div>
            ))}
          </div>

          {/* Edit Button */}
          <button
            onClick={() => alert("프로필 편집 기능은 준비 중입니다")}
            style={{
              borderRadius: 10,
              background: "#eef2ff",
              height: 36,
              width: "100%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              border: "none",
              cursor: "pointer",
            }}
          >
            <span
              style={{
                fontFamily: "Pretendard, sans-serif",
                fontSize: 13,
                fontWeight: 600,
                color: "#4f46e5",
              }}
            >
              프로필 편집
            </span>
          </button>
        </div>

        {/* Menu Section */}
        <div
          style={{
            borderRadius: 16,
            background: "#ffffff",
            border: "1px solid #e5e7eb",
            overflow: "hidden",
          }}
        >
          {[
            { icon: Settings, label: "계정 설정" },
            { icon: Bell, label: "알림 설정" },
            { icon: Calendar, label: "캘린더 연동" },
            { icon: Shield, label: "개인정보 관리" },
            { icon: Info, label: "도움말 및 문의" },
          ].map((item, index) => (
            <div
              key={item.label}
              onClick={() => alert(`${item.label} 기능은 준비 중입니다`)}
              style={{
                height: 52,
                padding: "0 16px",
                display: "flex",
                alignItems: "center",
                gap: 12,
                borderBottom:
                  index < 4 ? "1px solid #f1f5f9" : "none",
                cursor: "pointer",
              }}
            >
              <item.icon size={20} color="#64748b" />
              <span
                style={{
                  fontFamily: "Pretendard, sans-serif",
                  fontSize: 14,
                  fontWeight: 500,
                  color: "#1e293b",
                  flex: 1,
                }}
              >
                {item.label}
              </span>
              <ChevronRight size={16} color="#cbd5e1" />
            </div>
          ))}
        </div>

        {/* Logout Button */}
        <button
          onClick={() => router.push("/m/login")}
          style={{
            borderRadius: 12,
            background: "#ffffff",
            border: "1px solid #fecaca",
            height: 44,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
            width: "100%",
          }}
        >
          <span
            style={{
              fontFamily: "Pretendard, sans-serif",
              fontSize: 14,
              fontWeight: 500,
              color: "#ef4444",
            }}
          >
            로그아웃
          </span>
        </button>
      </div>

      {/* Tab Bar */}
      <MobileTabBar active="프로필" />
    </div>
  );
}
